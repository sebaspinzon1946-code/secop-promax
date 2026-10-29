"""
Módulo Único Definitivo: Centro de Comando SECOP II (Buscador, Alertas, Editor de Adendas, Evaluador y PDF)
"""

import os
import re
import datetime
from dotenv import load_dotenv
load_dotenv()

import pandas as pd
import streamlit as st
import requests
from typing import Dict, Any, List, Optional, Tuple

from generador_pdf import generar_informe_ejecutivo_pdf, formatear_moneda_cop, formatear_indicador

# =====================================================================
# LISTAS OFICIALES EXTRAÍDAS DEL EXCEL MAESTRO
# =====================================================================
LISTA_MODALIDADES = [
    "Licitacion Pública",
    "Concurso de Meritos",
    "Seleccion Abreviada de Subasta Inversa",
    "Seleccion Abreviada Menor Cuantia",
    "Acuerdo Macro de Precios",
    "Minima Cuantia",
    "Tienda Virtual",
    "Contratación Directa",
    "Regimen Especial"
]

LISTA_ETAPAS = [
    "Borrador",
    "Observacion Proyecto de Pliego",
    "Observaciones Pliego Definitivo",
    "Manifestacion de Interés",
    "Ofertas",
    "Evaluación",
    "Desierto",
    "Rechazada por Sorteo",
    "Seleccionada",
    "Sorteo"
]

LISTA_ESTADOS_REVISION = [
    "Rev. preliminar",
    "Previabilidad",
    "Viable",
    "Inviable",
    "Alistamiento",
    "Presentacion",
    "Presentada"
]

LISTA_METODOS_ECONOMICOS = [
    "1. Mediana Valor Absoluto",
    "2. Media Geometrica",
    "3. Media Aritmetica",
    "4. Media Aritmetica Baja",
    "5. Media Aritmetica Alta",
    "6. Menor Valor",
    "7. Media Podada",
    "8. Media Armonica",
    "9. Media Aritmetica Presupuesto Oficial",
    "10. Media Geometrica presupuesto oficial",
    "11. Porcentaje de Convenio"
]

LISTA_RESPONSABLES = [
    "Valerie Carvajal",
    "Sebastian Caraballo",
    "Edward Roa",
    "Marcela Cortes",
    "Fernanda"
]

LISTA_POLIZA = ["Por definir", "Sí", "No"]
LISTA_ESTADO_POLIZA = ["Pendiente", "Solicitada", "Expedida", "Aprobada", "Rechazada", "No aplica"]

# =====================================================================
# 1. CONEXIÓN A SUPABASE Y UTILIDADES DE FORMATO
# =====================================================================
def obtener_cliente_supabase():
    url = "https://mqcjmrdznbgfhpmnmvns.supabase.co"
    key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1xY2ptcmR6bmJnZmhwbW5tdm5zIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTI3MDc2NzksImV4cCI6MjEwODI4MzY3OX0.oihDE7Za6nZDrpNl2SSPIgdaGVy716nTVw-UZzAWUX0"
    if url and key:
        try:
            from supabase import create_client
            return create_client(url, key)
        except Exception:
            return None
    return None

def cargar_datos_base() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    cliente = obtener_cliente_supabase()
    if cliente:
        try:
            emp_res = cliente.table("empresas_proponentes").select("*").execute()
            lic_res = cliente.table("licitaciones_secop").select("*").order("numero_interno").execute()
            return (emp_res.data if isinstance(emp_res.data, list) else [], 
                    lic_res.data if isinstance(lic_res.data, list) else [])
        except Exception as e:
            st.sidebar.error(f"Error de lectura: {e}")
    return [], []

def formatear_miles_input(valor: Any) -> str:
    if isinstance(valor, (int, float)):
        return f"$ {int(round(valor)):,}".replace(",", ".")
    try:
        s = str(valor).strip()
        if "." in s and len(s.split(".")[-1]) <= 2 and s.count(".") == 1:
            val = float(s)
        else:
            limpio = re.sub(r'[^\d]', '', s.split(',')[0])
            val = float(limpio) if limpio else 0.0
        return f"$ {int(round(val)):,}".replace(",", ".")
    except Exception:
        return "$ 0"

def limpiar_moneda_input(texto: Any) -> int:
    if isinstance(texto, (int, float)):
        return int(round(float(texto)))
    if not texto:
        return 0
    s = str(texto).strip().replace("$", "").strip()
    if "," in s:
        s = s.split(",")[0]
    limpio = re.sub(r'[^\d]', '', s)
    try:
        return int(limpio)
    except Exception:
        return 0

def limpiar_codigos_unspsc(texto_crudo: Any) -> str:
    if texto_crudo is None:
        return ""
    s = str(texto_crudo).replace(".0", "")
    codigos_8 = list(dict.fromkeys(re.findall(r'\b(\d{8})\b', s)))
    if codigos_8:
        return "; ".join(codigos_8)
    codigos_6 = list(dict.fromkeys([c + "00" for c in re.findall(r'\b(\d{6})\b', s)]))
    if codigos_6:
        return "; ".join(codigos_6)
    return ""

def parsear_fecha_hora_secop(valor_str: Any) -> Tuple[Optional[datetime.date], Optional[datetime.time]]:
    if not valor_str or str(valor_str).strip() in ["", "N/A", "None", "nan"]:
        return None, None
    s = str(valor_str).strip()
    try:
        dt = datetime.datetime.fromisoformat(s.replace("Z", ""))
        hora = dt.time() if (dt.hour != 0 or dt.minute != 0) else None
        return dt.date(), hora
    except Exception:
        pass
    m = re.search(r'(\d{2})/(\d{2})/(\d{4})(?:\s+(\d{1,2}):(\d{2}))?', s)
    if m:
        try:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            fecha = datetime.date(y, mo, d)
            if m.group(4) and m.group(5):
                h, mi = int(m.group(4)), int(m.group(5))
                if "p." in s.lower() and h < 12: h += 12
                return fecha, datetime.time(h, mi)
            return fecha, None
        except Exception:
            pass
    return None, None

def parsear_fecha_hora_db(valor_str: Any) -> Tuple[Optional[datetime.date], Optional[datetime.time]]:
    """Extrae fecha y hora desde la base de datos de Supabase para pre-cargar el formulario de Edición."""
    if not valor_str or str(valor_str).strip() in ["", "N/A", "None", "nan", "NULL"]:
        return None, None
    s = str(valor_str).strip()
    try:
        partes = s.split(" ")
        f_obj = datetime.datetime.strptime(partes[0], "%Y-%m-%d").date()
        h_obj = None
        if len(partes) > 1:
            time_str = partes[1]
            if len(time_str.split(":")) == 3:
                h_obj = datetime.datetime.strptime(time_str, "%H:%M:%S").time()
            elif len(time_str.split(":")) == 2:
                h_obj = datetime.datetime.strptime(time_str, "%H:%M").time()
        return f_obj, h_obj
    except Exception:
        return None, None

def homologar_modalidad(mod_api: str) -> str:
    m = str(mod_api).lower()
    if "licitac" in m: return "Licitacion Pública"
    if "concurso" in m: return "Concurso de Meritos"
    if "subasta" in m: return "Seleccion Abreviada de Subasta Inversa"
    if "menor" in m or "abreviada" in m: return "Seleccion Abreviada Menor Cuantia"
    if "acuerdo" in m: return "Acuerdo Macro de Precios"
    if "minima" in m or "mínima" in m: return "Minima Cuantia"
    if "tienda" in m: return "Tienda Virtual"
    if "directa" in m: return "Contratación Directa"
    if "especial" in m or "regimen" in m or "régimen" in m: return "Regimen Especial"
    return "Licitacion Pública"

def homologar_etapa(fase_api: str) -> str:
    f = str(fase_api).lower()
    if "borrador" in f or "previo" in f: return "Borrador"
    if "proyecto" in f: return "Observacion Proyecto de Pliego"
    if "definitivo" in f: return "Observaciones Pliego Definitivo"
    if "inter" in f: return "Manifestacion de Interés"
    if "sorteo" in f: return "Sorteo"
    if "evaluac" in f: return "Evaluación"
    if "desiert" in f: return "Desierto"
    if "seleccion" in f or "adjudic" in f or "celebr" in f: return "Seleccionada"
    if "oferta" in f or "presentaci" in f or "abierto" in f or "publicad" in f: return "Ofertas"
    return "Borrador"

def get_index_safe(lista: List[str], valor: str) -> int:
    return lista.index(valor) if valor in lista else 0

# =====================================================================
# RASTREADOR MIXTO: API DATOS ABIERTOS + RASTREO WEB
# =====================================================================
def rastrear_web_secop(url_secop: str) -> Dict[str, Any]:
    extra = {}
    if not url_secop or not url_secop.startswith("http"): return extra
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        r = requests.get(url_secop, headers=headers, timeout=12)
        if r.status_code != 200: return extra
        html = r.text
        texto_plano = re.sub(r'<[^>]+>', ' ', html)
        texto_plano = re.sub(r'\s+', ' ', texto_plano)

        m_dur = re.search(r'Duraci[óo]n del contrato[:\s]*(\d+)\s*\(?([A-Za-zÁÉÍÓÚáéíóú]+)\)?', texto_plano, re.IGNORECASE)
        if m_dur: extra['tiempo'] = f"{m_dur.group(1)} {m_dur.group(2).lower()}"

        codigos_web = list(dict.fromkeys(re.findall(r'\b(\d{8})\s*-\s*', texto_plano)))
        if codigos_web: extra['unspsc'] = "; ".join(codigos_web)

        patrones_hitos = {
            'f_int': r'Manifestaci[óo]n de inter[ée]s.*?(\d{2}/\d{2}/\d{4}(?:\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[ap]\.?\s*m\.?)?)?)',
            'f_mip': r'Mipyme.*?(\d{2}/\d{2}/\d{4}(?:\s+\d{1,2}:\d{2})?)',
            'f_obsp': r'(?:Observaciones al proyecto|borrador).*?(\d{2}/\d{2}/\d{4}(?:\s+\d{1,2}:\d{2})?)',
            'f_obsd': r'(?:Observaciones al pliego|extempor[áa]neas).*?(\d{2}/\d{2}/\d{4}(?:\s+\d{1,2}:\d{2})?)',
            'f_ofe': r'(?:Presentaci[óo]n de ofertas|l[íi]mite para presentar ofertas).*?(\d{2}/\d{2}/\d{4}(?:\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[ap]\.?\s*m\.?)?)?)'
        }
        for clave, patron in patrones_hitos.items():
            m_f = re.search(patron, texto_plano, re.IGNORECASE)
            if m_f:
                f_dt, h_dt = parsear_fecha_hora_secop(m_f.group(1))
                if f_dt: extra[clave] = f_dt
                if clave == 'f_ofe' and h_dt: extra['h_ofe'] = h_dt
    except Exception:
        pass
    return extra

def buscar_proceso_secop_completo(expediente: str, link_manual: str = "") -> bool:
    encontrado = False
    headers = {"User-Agent": "Mozilla/5.0"}
    url_api = "https://www.datos.gov.co/resource/p6dx-8zbt.json"
    datos = {}

    if expediente:
        exp_clean = expediente.strip()
        try:
            resp = requests.get(url_api, headers=headers, params={"referencia_del_proceso": exp_clean}, timeout=10)
            if resp.status_code == 200 and len(resp.json()) > 0:
                datos = resp.json()[0]
            else:
                resp2 = requests.get(url_api, headers=headers, params={"$where": f"upper(referencia_del_proceso) like '%{exp_clean.upper()}%'"}, timeout=10)
                if resp2.status_code == 200 and len(resp2.json()) > 0:
                    datos = resp2.json()[0]
        except Exception:
            pass

    if datos:
        encontrado = True
        st.session_state['api_entidad'] = datos.get('entidad', '')
        st.session_state['api_objeto'] = datos.get('descripci_n_del_procedimiento', datos.get('detalle_del_objeto_a_contratar', datos.get('descripcion_del_proceso', '')))
        
        presupuesto_str = datos.get('precio_base', datos.get('cuantia_proceso', datos.get('estimacion_del_presupuesto', 0)))
        try: st.session_state['api_cuantia'] = formatear_miles_input(float(presupuesto_str))
        except Exception: st.session_state['api_cuantia'] = "$ 0"

        st.session_state['api_modalidad'] = homologar_modalidad(datos.get('modalidad_de_contratacion', ''))
        st.session_state['api_etapa'] = homologar_etapa(datos.get('fase', datos.get('estado_del_procedimiento', '')))
        st.session_state['api_lugar'] = datos.get('ciudad_entidad', datos.get('ciudad_de_la_unidad_de', 'Bogotá D.C.'))

        dur = str(datos.get('duracion', '')).strip()
        unid = str(datos.get('unidad_de_duracion', '')).strip()
        if dur and dur not in ['0', 'N/A', 'None']: st.session_state['api_tiempo'] = f"{dur} {unid.lower()}".strip()

        url_cruda = datos.get('urlproceso', '')
        link_api = url_cruda.get('url', '') if isinstance(url_cruda, dict) else str(url_cruda)
        if link_api: st.session_state['api_link'] = link_api

        cod_api = datos.get('codigo_principal_de_categoria', datos.get('codigos_unspsc', ''))
        cod_limpio = limpiar_codigos_unspsc(cod_api)
        if cod_limpio: st.session_state['api_unspsc'] = cod_limpio

        f_rec, h_rec = parsear_fecha_hora_secop(datos.get('fecha_de_recepcion_de', datos.get('fecha_de_recepcion_de_ofertas')))
        if f_rec: st.session_state['api_f_ofe'] = f_rec
        if h_rec: st.session_state['api_h_ofe'] = h_rec

        f_obsp, _ = parsear_fecha_hora_secop(datos.get('fecha_de_publicacion_fase_borrador', datos.get('fecha_de_publicacion_del')))
        if f_obsp: st.session_state['api_f_obsp'] = f_obsp

        f_obsd, _ = parsear_fecha_hora_secop(datos.get('fecha_de_ultima_publicaci'))
        if f_obsd: st.session_state['api_f_obsd'] = f_obsd

    url_objetivo = link_manual.strip() if link_manual.strip() else st.session_state.get('api_link', '')
    if url_objetivo:
        datos_web = rastrear_web_secop(url_objetivo)
        if datos_web:
            encontrado = True
            if 'tiempo' in datos_web: st.session_state['api_tiempo'] = datos_web['tiempo']
            if 'unspsc' in datos_web: st.session_state['api_unspsc'] = datos_web['unspsc']
            for k_f in ['f_int', 'f_mip', 'f_obsp', 'f_obsd', 'f_ofe', 'h_ofe']:
                if k_f in datos_web: st.session_state[f'api_{k_f}'] = datos_web[k_f]

    return encontrado

# =====================================================================
# 2. MOTOR MATEMÁTICO FINANCIERO Y CRUCE DE CÓDIGOS UNSPSC (RUP)
# =====================================================================
def evaluar_indicador(nombre, regla, exigido, valor_consolidado, es_porcentaje=False, es_moneda=False, indeterminado=False):
    if exigido is None or exigido == "" or float(exigido) == 0:
        return {"indicador": nombre, "regla": regla, "exigido_fmt": "N/A", "consolidado_fmt": formatear_moneda_cop(valor_consolidado) if es_moneda else formatear_indicador(valor_consolidado, es_porcentaje, indeterminado), "estado": "NO EXIGIDO"}
    
    exigido_fmt = formatear_moneda_cop(exigido) if es_moneda else formatear_indicador(exigido, es_porcentaje, False)
    consolidado_fmt = formatear_moneda_cop(valor_consolidado) if es_moneda else formatear_indicador(valor_consolidado, es_porcentaje, indeterminado)
    
    if indeterminado or valor_consolidado is None: estado = "REVISAR"
    else:
        if regla == ">=": estado = "CUMPLE" if float(valor_consolidado) >= float(exigido) else "NO CUMPLE"
        elif regla == "<=": estado = "CUMPLE" if float(valor_consolidado) <= float(exigido) else "NO CUMPLE"
        else: estado = "REVISAR"
    return {"indicador": nombre, "regla": regla, "exigido_fmt": exigido_fmt, "consolidado_fmt": consolidado_fmt, "estado": estado}

def evaluar_cruce_unspsc(licitacion: Dict[str, Any], integrantes_seleccionados: List[Dict[str, Any]]) -> Dict[str, Any]:
    cod_req_raw = str(licitacion.get("codigos_unspsc_req", ""))
    lista_req = list(dict.fromkeys(re.findall(r'\b(\d{8})\b', cod_req_raw)))
    min_exigido = int(float(licitacion.get("cant_codigos_unspsc_req", 0) or 0))

    set_rup_exacto = set()
    set_rup_clase = set()
    for emp in integrantes_seleccionados:
        cod_emp_raw = str(emp.get("codigos_unspsc_rup", ""))
        for c in re.findall(r'\b(\d{8})\b', cod_emp_raw):
            set_rup_exacto.add(c)
            set_rup_clase.add(c[:6] + "00")

    coincidentes = []
    faltantes = []
    for c_req in lista_req:
        if c_req in set_rup_exacto or (c_req[:6] + "00") in set_rup_clase:
            coincidentes.append(c_req)
        else:
            faltantes.append(c_req)

    cant_cumplidos = len(coincidentes)
    if not lista_req and min_exigido == 0:
        estado_unspsc = "NO EXIGIDO"
    elif min_exigido > 0:
        estado_unspsc = "CUMPLE" if cant_cumplidos >= min_exigido else "NO CUMPLE"
    else:
        estado_unspsc = "CUMPLE" if (cant_cumplidos == len(lista_req) and len(lista_req) > 0) else "REVISAR"

    return {
        "total_publicados": len(lista_req),
        "min_exigido": min_exigido,
        "codigos_cumplidos": cant_cumplidos,
        "coincidentes": coincidentes,
        "faltantes": faltantes,
        "estado_unspsc": estado_unspsc
    }

def consolidar_proponente_plural(licitacion, integrantes_seleccionados, tipo_figura="UNION_TEMPORAL"):
    ac_cons = pc_cons = at_cons = pt_cons = pat_cons = uo_cons = gi_cons = ct_cons = 0.0
    for emp in integrantes_seleccionados:
        peso = float(emp.get("porcentaje_participacion", 0.0)) / 100.0 if tipo_figura != "INDIVIDUAL" else 1.0
        ac_cons += float(emp.get("activo_corriente", 0.0)) * peso
        pc_cons += float(emp.get("pasivo_corriente", 0.0)) * peso
        at_cons += float(emp.get("activo_total", 0.0)) * peso
        pt_cons += float(emp.get("pasivo_total", 0.0)) * peso
        pat_cons += float(emp.get("patrimonio", 0.0)) * peso
        uo_cons += float(emp.get("utilidad_operacional", 0.0)) * peso
        gi_cons += float(emp.get("gastos_intereses", 0.0)) * peso
        ct_cons += float(emp.get("capital_trabajo", 0.0))
    
    liq = (ac_cons / pc_cons) if pc_cons > 0 else None
    end = (pt_cons / at_cons) if at_cons > 0 else None
    cob_ind = (gi_cons == 0)
    cob = (uo_cons / gi_cons) if not cob_ind else None
    rp = (uo_cons / pat_cons) if pat_cons > 0 else None
    ra = (uo_cons / at_cons) if at_cons > 0 else None
    
    comparativo = [
        evaluar_indicador("Liquidez", ">=", licitacion.get("req_liquidez_min"), liq),
        evaluar_indicador("Endeudamiento", "<=", licitacion.get("req_endeudamiento_max"), end, es_porcentaje=True),
        evaluar_indicador("Cobertura de intereses", ">=", licitacion.get("req_cobertura_intereses_min"), cob, indeterminado=cob_ind),
        evaluar_indicador("Capital de trabajo (COP)", ">=", licitacion.get("req_capital_trabajo_cop"), ct_cons, es_moneda=True),
        evaluar_indicador("Rentabilidad patrimonio", ">=", licitacion.get("req_rentabilidad_patrimonio_min"), rp, es_porcentaje=True),
        evaluar_indicador("Rentabilidad del activo", ">=", licitacion.get("req_rentabilidad_activo_min"), ra, es_porcentaje=True),
    ]
    estados = [item["estado"] for item in comparativo if item["estado"] != "NO EXIGIDO"]
    estado_global = "NO CUMPLE" if "NO CUMPLE" in estados else "REVISAR" if "REVISAR" in estados else "CUMPLE"
    
    cruce_unspsc = evaluar_cruce_unspsc(licitacion, integrantes_seleccionados)
    return {
        "tipo_figura": tipo_figura,
        "comparativo_indicadores": comparativo,
        "estado_global": estado_global,
        "cruce_unspsc": cruce_unspsc,
        "codigos_cumplidos": cruce_unspsc["codigos_cumplidos"]
    }

def selector_calendario_seguro(etiqueta: str, valor_defecto: Any, clave: str) -> Optional[datetime.date]:
    """Genera un selector de calendario con una llave única para evitar conflictos entre los formularios de Crear y Editar."""
    try: return st.date_input(etiqueta, value=valor_defecto, format="DD/MM/YYYY", key=clave)
    except TypeError: return st.date_input(etiqueta, value=valor_defecto, key=clave)

def formatear_fecha_db(fecha_obj: Optional[datetime.date], hora_obj: Optional[datetime.time] = None) -> Optional[str]:
    if not fecha_obj: return None
    f_str = fecha_obj.strftime("%Y-%m-%d")
    if hora_obj: return f"{f_str} {hora_obj.strftime('%H:%M:%S')}"
    return f_str

# =====================================================================
# 3. INTERFAZ ALL-IN-ONE
# =====================================================================
def main():
    st.set_page_config(page_title="SECOP II ProMax", page_icon="⚖️", layout="wide")
    st.title("⚖️ Centro de Comando SECOP II — ASESOL / ZEKIA")
    
    empresas, licitaciones = cargar_datos_base()
    licitaciones_validas = [lic for lic in licitaciones if isinstance(lic, dict)]
    
    # ------------------ RADAR DE ALERTAS INTELIGENTES ------------------
    alertas_criticas = []
    alertas_medias = []
    hoy = datetime.date.today()

    for lic in licitaciones_validas:
        estado_rev = str(lic.get("estado_revision", ""))
        num_proc = str(lic.get("numero_proceso", "S/N"))
        
        # 1. Alertas de Vencimiento de Ofertas
        f_oferta_raw = lic.get("fecha_presentacion_oferta")
        if f_oferta_raw and f_oferta_raw != "N/A":
            f_solo = str(f_oferta_raw).split(" ")[0]
            try:
                f_oferta_dt = datetime.datetime.strptime(f_solo, "%Y-%m-%d").date()
                dias_restantes = (f_oferta_dt - hoy).days
                if estado_rev not in ["Presentada", "Inviable", "Seleccionada", "Desierto"]:
                    if 0 <= dias_restantes <= 3:
                        alertas_criticas.append(f"**{num_proc}**: Cierra en **{dias_restantes} días** ({f_solo}).")
                    elif 4 <= dias_restantes <= 7:
                        alertas_medias.append(f"**{num_proc}**: Cierra en **{dias_restantes} días** ({f_solo}).")
            except Exception: pass
            
        # 2. Alertas de Pólizas
        est_pol = str(lic.get("estado_poliza", ""))
        if est_pol in ["Pendiente", "Solicitada"] and estado_rev in ["Alistamiento", "Viable", "Presentacion"]:
            alertas_medias.append(f"**{num_proc}**: Atención, Póliza en estado '{est_pol}'.")

    with st.expander("🔔 Radar de Vencimientos y Alertas", expanded=bool(alertas_criticas or alertas_medias)):
        if not alertas_criticas and not alertas_medias:
            st.success("✅ Todo bajo control. No hay cierres críticos en los próximos 7 días ni pólizas pendientes urgentes.")
        else:
            if alertas_criticas:
                for alerta in alertas_criticas:
                    st.error(f"🚨 {alerta}")
            if alertas_medias:
                for alerta in alertas_medias:
                    st.warning(f"⚠️ {alerta}")
    # -------------------------------------------------------------------

    with st.sidebar:
        # =======================================================
        # MÓDULO 1: BUSCADOR Y CREADOR DE PROCESOS
        # =======================================================
        with st.expander("➕ Buscar y Registrar Nuevo Proceso", expanded=False):
            exp_buscar = st.text_input("Expediente (Ej. FDLSC-LP-006-2026)")
            link_rastreo = st.text_input("Opcional: Link directo SECOP II", value=st.session_state.get('api_link', ''))
            
            if st.button("🔍 Buscar API y Rastrear Web", use_container_width=True):
                if exp_buscar or link_rastreo:
                    if buscar_proceso_secop_completo(exp_buscar, link_rastreo):
                        st.success("✅ Datos, duración, fechas y códigos extraídos.")
                    else:
                        st.warning("⚠️ No indexado aún en API. Puedes diligenciarlo manualmente.")
            
            with st.form("form_guardar_proceso", clear_on_submit=True):
                st.caption("Diligencia las 12 secciones (Matriz Excel)")
                t1, t2, t3, t4 = st.tabs(["01-02", "03-05", "06-08", "09-12"])
                
                with t1:
                    st.write("**01 BÁSICOS**")
                    num_interno = st.number_input("Nº Interno", value=len(licitaciones) + 1, min_value=1, key="num_interno_c")
                    num_proceso = st.text_input("Nº Proceso", value=exp_buscar, key="num_proceso_c")
                    entidad = st.text_input("Entidad", value=st.session_state.get('api_entidad', ''), key="entidad_c")
                    objeto = st.text_area("Objeto", value=st.session_state.get('api_objeto', ''), key="objeto_c")
                    
                    mod_def = st.session_state.get('api_modalidad', LISTA_MODALIDADES[0])
                    idx_mod = get_index_safe(LISTA_MODALIDADES, mod_def)
                    modalidad = st.selectbox("Modalidad", LISTA_MODALIDADES, index=idx_mod, key="modalidad_c")
                    cuantia_txt = st.text_input("Presupuesto Oficial (COP)", value=st.session_state.get('api_cuantia', "$ 0"), key="cuantia_c")
                    
                    etapa_def = st.session_state.get('api_etapa', "Ofertas")
                    idx_etapa = get_index_safe(LISTA_ETAPAS, etapa_def)
                    etapa = st.selectbox("Etapa Actual", LISTA_ETAPAS, index=idx_etapa, key="etapa_c")
                    estado = st.selectbox("Estado Revisión", LISTA_ESTADOS_REVISION, index=0, key="estado_c")
                    lugar = st.text_input("Lugar Ejecución", value=st.session_state.get('api_lugar', "Bogotá D.C."), key="lugar_c")
                    tiempo = st.text_input("Tiempo Ejecución", value=st.session_state.get('api_tiempo', "N/A"), key="tiempo_c")
                    
                    st.write("**02 CRONOGRAMA (Calendario)**")
                    f_int = selector_calendario_seguro("📅 Manifestación Interés", st.session_state.get('api_f_int', None), "f_int_c")
                    f_sor = selector_calendario_seguro("📅 Fecha Sorteo", st.session_state.get('api_f_sor', None), "f_sor_c")
                    f_mip = selector_calendario_seguro("📅 Límite Mipyme", st.session_state.get('api_f_mip', None), "f_mip_c")
                    f_obsp = selector_calendario_seguro("📅 Obs. Proyecto Pliego", st.session_state.get('api_f_obsp', None), "f_obsp_c")
                    f_obsd = selector_calendario_seguro("📅 Obs. Pliego Definitivo", st.session_state.get('api_f_obsd', None), "f_obsd_c")
                    f_ofe = selector_calendario_seguro("📅 Fecha Presentación Ofertas", st.session_state.get('api_f_ofe', None), "f_ofe_c")
                    hora_ofe = st.time_input("⏰ Hora de Cierre Oferta", value=st.session_state.get('api_h_ofe', datetime.time(10, 0)), key="h_ofe_c")

                with t2:
                    st.write("**03 UNSPSC | 04 TRIBUTOS**")
                    unspsc_input = st.text_area("Códigos UNSPSC", value=st.session_state.get('api_unspsc', ''), height=110, key="unspsc_c")
                    cant_u = st.number_input("CANT. COD. REQ (Mínimo exigido en pliegos)", value=0, min_value=0, key="cant_u_c")
                    estampillas = st.text_area("Estampillas / Descuentos", value="N/A", key="estampillas_c")
                    
                    st.write("**05 FINANCIEROS (Pliego)**")
                    r_liq = st.number_input("Liquidez (>=)", value=0.0, step=0.1, key="r_liq_c")
                    r_end = st.number_input("Endeudamiento (<= decimal o %)", value=0.0, step=0.05, key="r_end_c")
                    r_cob = st.number_input("Cobertura (>=)", value=0.0, step=0.1, key="r_cob_c")
                    r_cap_txt = st.text_input("Capital Trabajo Exigido ($ COP)", value="$ 0", key="r_cap_c")
                    r_rpat = st.number_input("Rent. Patrimonio (>=)", value=0.0, step=0.05, key="r_rpat_c")
                    r_ract = st.number_input("Rent. Activo (>=)", value=0.0, step=0.05, key="r_ract_c")
                
                with t3:
                    st.write("**06 RESUMEN EJECUCIÓN**")
                    resumen = st.text_area("Resumen y Requerimientos Generales", value="N/A", key="resumen_c")
                    st.write("**07 EXPERIENCIA**")
                    eg_cont = st.text_input("Exp. General Contratos", value="N/A", key="eg_cont_c")
                    eg_desc = st.text_area("Desc. Exp. General", value="N/A", key="eg_desc_c")
                    ee_cont = st.text_input("Exp. Específica Contratos", value="N/A", key="ee_cont_c")
                    ee_desc = st.text_area("Desc. Exp. Específica", value="N/A", key="ee_desc_c")
                    reg_emp = st.text_area("Emprendimientos / Mujeres / Mipyme", value="N/A", key="reg_emp_c")
                    
                    st.write("**08 EVALUACIÓN MÉTODOS**")
                    met_eco_sel = st.multiselect("Métodos de Oferta Económica (Excel)", options=LISTA_METODOS_ECONOMICOS, key="met_eco_c")
                    fac_tec = st.text_area("Relación de Factores Técnicos Ponderables", value="N/A", key="fac_tec_c")

                with t4:
                    st.write("**09 PONDERACIÓN (Puntos)**")
                    pt_t = st.number_input("Técnica", value=0.0, step=0.5, key="pt_t_c")
                    pt_e = st.number_input("Económica", value=0.0, step=0.5, key="pt_e_c")
                    pt_i = st.number_input("Ind. Nacional", value=0.0, step=0.5, key="pt_i_c")
                    pt_d = st.number_input("Discapacidad", value=0.0, step=0.5, key="pt_d_c")
                    pt_m = st.number_input("Mipyme", value=0.0, step=0.25, key="pt_m_c")
                    pt_mu = st.number_input("Mujeres", value=0.0, step=0.25, key="pt_mu_c")
                    pt_tot = st.number_input("Total Puntos", value=100.0, step=0.5, key="pt_tot_c")
                    
                    st.write("**10 RESPONSABLE | 11 LINK**")
                    responsable = st.selectbox("Responsable del Proceso", options=LISTA_RESPONSABLES, index=0, key="responsable_c")
                    obs_fin = st.text_area("Observaciones y Recomendaciones", value="N/A", key="obs_fin_c")
                    link_secop = st.text_input("Link Permanente SECOP II", value=st.session_state.get('api_link', link_rastreo), key="link_c")
                    
                    st.write("**12 GARANTÍAS (Pólizas)**")
                    pol_tipo = st.selectbox("¿Exige Póliza?", options=LISTA_POLIZA, index=0, key="pol_tipo_c")
                    pol_ser = st.text_input("Póliza Seriedad Oferta (Ej. 10% del PO)", value="N/A", key="pol_ser_c")
                    pol_fec_obj = selector_calendario_seguro("📅 Fecha Solicitud Póliza", st.session_state.get('api_f_pol', None), "pol_fec_c")
                    pol_vr_txt = st.text_input("Vr. Póliza ($ COP)", value="$ 0", key="pol_vr_c")
                    pol_est = st.selectbox("Estado de la Póliza", options=LISTA_ESTADO_POLIZA, index=0, key="pol_est_c")

                if st.form_submit_button("💾 Guardar Proceso Completo", type="primary"):
                    if num_proceso and entidad:
                        nueva_lic = {
                            "numero_interno": int(num_interno),
                            "fecha_registro": datetime.date.today().strftime("%Y-%m-%d"),
                            "numero_proceso": num_proceso,
                            "entidad": entidad,
                            "objeto": objeto,
                            "modalidad": modalidad,
                            "cuantia_presupuesto": limpiar_moneda_input(cuantia_txt),
                            "etapa_actual": etapa,
                            "estado_revision": estado,
                            "lugar_ejecucion": lugar,
                            "tiempo_ejecucion": tiempo,
                            "fecha_manifestacion_interes": formatear_fecha_db(f_int),
                            "fecha_sorteo": formatear_fecha_db(f_sor),
                            "fecha_limitacion_mipyme": formatear_fecha_db(f_mip),
                            "fecha_obs_prepliego": formatear_fecha_db(f_obsp),
                            "fecha_obs_pliego_def": formatear_fecha_db(f_obsd),
                            "fecha_presentacion_oferta": formatear_fecha_db(f_ofe, hora_ofe),
                            "codigos_unspsc_req": limpiar_codigos_unspsc(unspsc_input) or "N/A",
                            "cant_codigos_unspsc_req": int(cant_u),
                            "estampillas": estampillas,
                            "req_liquidez_min": r_liq,
                            "req_endeudamiento_max": r_end,
                            "req_cobertura_intereses_min": r_cob,
                            "req_capital_trabajo_cop": limpiar_moneda_input(r_cap_txt),
                            "req_rentabilidad_patrimonio_min": r_rpat,
                            "req_rentabilidad_activo_min": r_ract,
                            "resumen_requerimientos_generales": resumen,
                            "exp_general_contratos": eg_cont,
                            "exp_general_descripcion": eg_desc,
                            "exp_especifica_contratos": ee_cont,
                            "exp_especifica_descripcion": ee_desc,
                            "regla_emprendimientos_mujeres_mipyme": reg_emp,
                            "metodos_oferta_economica": "\n".join(met_eco_sel) if met_eco_sel else "N/A",
                            "factores_tecnicos_ponderables": fac_tec,
                            "puntos_tecnica": pt_t,
                            "puntos_economica": pt_e,
                            "puntos_industria_nacional": pt_i,
                            "puntos_discapacidad": pt_d,
                            "puntos_mipyme": pt_m,
                            "puntos_mujeres": pt_mu,
                            "total_puntos": pt_tot,
                            "responsable_proceso": responsable,
                            "observaciones_recomendaciones": obs_fin,
                            "link_secop": link_secop,
                            "poliza": pol_tipo,
                            "poliza_seriedad_oferta": pol_ser,
                            "fecha_solicitud_poliza": formatear_fecha_db(pol_fec_obj),
                            "vr_poliza": limpiar_moneda_input(pol_vr_txt),
                            "estado_poliza": pol_est
                        }
                        try:
                            obtener_cliente_supabase().table("licitaciones_secop").insert(nueva_lic).execute()
                            for k in list(st.session_state.keys()):
                                if k.startswith('api_'): del st.session_state[k]
                            st.success("✅ ¡Proceso registrado con éxito!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")

        # =======================================================
        # MÓDULO 2: MODIFICAR PROCESO EXISTENTE (ADENDAS)
        # =======================================================
        with st.expander("✏️ Modificar Proceso Existente (Adendas)", expanded=False):
            if not licitaciones_validas:
                st.warning("No hay procesos registrados para editar.")
            else:
                opciones_editar = {f"#{lic.get('numero_interno', 0)} | {lic.get('numero_proceso', 'S/N')}": lic for lic in licitaciones_validas}
                proc_edit_label = st.selectbox("Selecciona el proceso que deseas modificar:", list(opciones_editar.keys()), key="sel_proc_edit")
                p_ed = opciones_editar[proc_edit_label]
                
                with st.form("form_editar_proceso", clear_on_submit=False):
                    st.caption("Modifica los valores y presiona Actualizar al final del formulario.")
                    e1, e2, e3, e4 = st.tabs(["01-02", "03-05", "06-08", "09-12"])
                    
                    with e1:
                        st.write("**01 BÁSICOS**")
                        num_interno_e = st.number_input("Nº Interno (No modificable)", value=int(p_ed.get('numero_interno', 1)), disabled=True, key="num_interno_e")
                        num_proceso_e = st.text_input("Nº Proceso", value=str(p_ed.get('numero_proceso', '')), key="num_proceso_e")
                        entidad_e = st.text_input("Entidad", value=str(p_ed.get('entidad', '')), key="entidad_e")
                        objeto_e = st.text_area("Objeto", value=str(p_ed.get('objeto', '')), key="objeto_e")
                        
                        idx_mod_e = get_index_safe(LISTA_MODALIDADES, p_ed.get('modalidad', ''))
                        modalidad_e = st.selectbox("Modalidad", LISTA_MODALIDADES, index=idx_mod_e, key="modalidad_e")
                        cuantia_txt_e = st.text_input("Presupuesto Oficial (COP)", value=formatear_miles_input(p_ed.get('cuantia_presupuesto', 0)), key="cuantia_e")
                        
                        idx_etapa_e = get_index_safe(LISTA_ETAPAS, p_ed.get('etapa_actual', ''))
                        etapa_e = st.selectbox("Etapa Actual", LISTA_ETAPAS, index=idx_etapa_e, key="etapa_e")
                        idx_est_e = get_index_safe(LISTA_ESTADOS_REVISION, p_ed.get('estado_revision', ''))
                        estado_e = st.selectbox("Estado Revisión", LISTA_ESTADOS_REVISION, index=idx_est_e, key="estado_e")
                        lugar_e = st.text_input("Lugar Ejecución", value=str(p_ed.get('lugar_ejecucion', '')), key="lugar_e")
                        tiempo_e = st.text_input("Tiempo Ejecución", value=str(p_ed.get('tiempo_ejecucion', '')), key="tiempo_e")
                        
                        st.write("**02 CRONOGRAMA (Calendario)**")
                        f_int_dt, _ = parsear_fecha_hora_db(p_ed.get('fecha_manifestacion_interes'))
                        f_sor_dt, _ = parsear_fecha_hora_db(p_ed.get('fecha_sorteo'))
                        f_mip_dt, _ = parsear_fecha_hora_db(p_ed.get('fecha_limitacion_mipyme'))
                        f_obsp_dt, _ = parsear_fecha_hora_db(p_ed.get('fecha_obs_prepliego'))
                        f_obsd_dt, _ = parsear_fecha_hora_db(p_ed.get('fecha_obs_pliego_def'))
                        f_ofe_dt, h_ofe_dt = parsear_fecha_hora_db(p_ed.get('fecha_presentacion_oferta'))
                        
                        f_int_e = selector_calendario_seguro("📅 Manifestación Interés", f_int_dt, "f_int_e")
                        f_sor_e = selector_calendario_seguro("📅 Fecha Sorteo", f_sor_dt, "f_sor_e")
                        f_mip_e = selector_calendario_seguro("📅 Límite Mipyme", f_mip_dt, "f_mip_e")
                        f_obsp_e = selector_calendario_seguro("📅 Obs. Proyecto Pliego", f_obsp_dt, "f_obsp_e")
                        f_obsd_e = selector_calendario_seguro("📅 Obs. Pliego Definitivo", f_obsd_dt, "f_obsd_e")
                        f_ofe_e = selector_calendario_seguro("📅 Fecha Presentación Ofertas", f_ofe_dt, "f_ofe_e")
                        hora_ofe_e = st.time_input("⏰ Hora de Cierre Oferta", value=h_ofe_dt or datetime.time(10, 0), key="h_ofe_e")

                    with e2:
                        st.write("**03 UNSPSC | 04 TRIBUTOS**")
                        unspsc_input_e = st.text_area("Códigos UNSPSC", value=str(p_ed.get('codigos_unspsc_req', '')), height=110, key="unspsc_e")
                        cant_u_e = st.number_input("CANT. COD. REQ (Mínimo exigido)", value=int(p_ed.get('cant_codigos_unspsc_req', 0)), min_value=0, key="cant_u_e")
                        estampillas_e = st.text_area("Estampillas / Descuentos", value=str(p_ed.get('estampillas', '')), key="estampillas_e")
                        
                        st.write("**05 FINANCIEROS (Pliego)**")
                        r_liq_e = st.number_input("Liquidez (>=)", value=float(p_ed.get('req_liquidez_min', 0.0)), step=0.1, key="r_liq_e")
                        r_end_e = st.number_input("Endeudamiento (<= decimal o %)", value=float(p_ed.get('req_endeudamiento_max', 0.0)), step=0.05, key="r_end_e")
                        r_cob_e = st.number_input("Cobertura (>=)", value=float(p_ed.get('req_cobertura_intereses_min', 0.0)), step=0.1, key="r_cob_e")
                        r_cap_txt_e = st.text_input("Capital Trabajo Exigido ($ COP)", value=formatear_miles_input(p_ed.get('req_capital_trabajo_cop', 0)), key="r_cap_e")
                        r_rpat_e = st.number_input("Rent. Patrimonio (>=)", value=float(p_ed.get('req_rentabilidad_patrimonio_min', 0.0)), step=0.05, key="r_rpat_e")
                        r_ract_e = st.number_input("Rent. Activo (>=)", value=float(p_ed.get('req_rentabilidad_activo_min', 0.0)), step=0.05, key="r_ract_e")
                    
                    with e3:
                        st.write("**06 RESUMEN EJECUCIÓN**")
                        resumen_e = st.text_area("Resumen y Requerimientos Generales", value=str(p_ed.get('resumen_requerimientos_generales', '')), key="resumen_e")
                        st.write("**07 EXPERIENCIA**")
                        eg_cont_e = st.text_input("Exp. General Contratos", value=str(p_ed.get('exp_general_contratos', '')), key="eg_cont_e")
                        eg_desc_e = st.text_area("Desc. Exp. General", value=str(p_ed.get('exp_general_descripcion', '')), key="eg_desc_e")
                        ee_cont_e = st.text_input("Exp. Específica Contratos", value=str(p_ed.get('exp_especifica_contratos', '')), key="ee_cont_e")
                        ee_desc_e = st.text_area("Desc. Exp. Específica", value=str(p_ed.get('exp_especifica_descripcion', '')), key="ee_desc_e")
                        reg_emp_e = st.text_area("Emprendimientos / Mujeres / Mipyme", value=str(p_ed.get('regla_emprendimientos_mujeres_mipyme', '')), key="reg_emp_e")
                        
                        st.write("**08 EVALUACIÓN MÉTODOS**")
                        met_eco_db = str(p_ed.get('metodos_oferta_economica', '')).split('\n')
                        met_eco_sel_e = [m for m in met_eco_db if m in LISTA_METODOS_ECONOMICOS]
                        met_eco_edit = st.multiselect("Métodos de Oferta Económica", options=LISTA_METODOS_ECONOMICOS, default=met_eco_sel_e, key="met_eco_e")
                        fac_tec_e = st.text_area("Relación de Factores Técnicos Ponderables", value=str(p_ed.get('factores_tecnicos_ponderables', '')), key="fac_tec_e")

                    with e4:
                        st.write("**09 PONDERACIÓN (Puntos)**")
                        pt_t_e = st.number_input("Técnica", value=float(p_ed.get('puntos_tecnica', 0.0)), step=0.5, key="pt_t_e")
                        pt_e_e = st.number_input("Económica", value=float(p_ed.get('puntos_economica', 0.0)), step=0.5, key="pt_e_e")
                        pt_i_e = st.number_input("Ind. Nacional", value=float(p_ed.get('puntos_industria_nacional', 0.0)), step=0.5, key="pt_i_e")
                        pt_d_e = st.number_input("Discapacidad", value=float(p_ed.get('puntos_discapacidad', 0.0)), step=0.5, key="pt_d_e")
                        pt_m_e = st.number_input("Mipyme", value=float(p_ed.get('puntos_mipyme', 0.0)), step=0.25, key="pt_m_e")
                        pt_mu_e = st.number_input("Mujeres", value=float(p_ed.get('puntos_mujeres', 0.0)), step=0.25, key="pt_mu_e")
                        pt_tot_e = st.number_input("Total Puntos", value=float(p_ed.get('total_puntos', 100.0)), step=0.5, key="pt_tot_e")
                        
                        st.write("**10 RESPONSABLE | 11 LINK**")
                        idx_resp_e = get_index_safe(LISTA_RESPONSABLES, p_ed.get('responsable_proceso', ''))
                        responsable_e = st.selectbox("Responsable del Proceso", options=LISTA_RESPONSABLES, index=idx_resp_e, key="responsable_e")
                        obs_fin_e = st.text_area("Observaciones y Recomendaciones", value=str(p_ed.get('observaciones_recomendaciones', '')), key="obs_fin_e")
                        link_secop_e = st.text_input("Link Permanente SECOP II", value=str(p_ed.get('link_secop', '')), key="link_e")
                        
                        st.write("**12 GARANTÍAS (Pólizas)**")
                        idx_polt_e = get_index_safe(LISTA_POLIZA, p_ed.get('poliza', ''))
                        pol_tipo_e = st.selectbox("¿Exige Póliza?", options=LISTA_POLIZA, index=idx_polt_e, key="pol_tipo_e")
                        pol_ser_e = st.text_input("Póliza Seriedad Oferta", value=str(p_ed.get('poliza_seriedad_oferta', '')), key="pol_ser_e")
                        pol_fec_dt, _ = parsear_fecha_hora_db(p_ed.get('fecha_solicitud_poliza'))
                        pol_fec_obj_e = selector_calendario_seguro("📅 Fecha Solicitud Póliza", pol_fec_dt, "pol_fec_e")
                        pol_vr_txt_e = st.text_input("Vr. Póliza ($ COP)", value=formatear_miles_input(p_ed.get('vr_poliza', 0)), key="pol_vr_e")
                        idx_pole_e = get_index_safe(LISTA_ESTADO_POLIZA, p_ed.get('estado_poliza', ''))
                        pol_est_e = st.selectbox("Estado de la Póliza", options=LISTA_ESTADO_POLIZA, index=idx_pole_e, key="pol_est_e")

                    if st.form_submit_button("💾 Actualizar Proceso", type="primary"):
                        if num_proceso_e and entidad_e:
                            dict_actualizado = {
                                "numero_proceso": num_proceso_e,
                                "entidad": entidad_e,
                                "objeto": objeto_e,
                                "modalidad": modalidad_e,
                                "cuantia_presupuesto": limpiar_moneda_input(cuantia_txt_e),
                                "etapa_actual": etapa_e,
                                "estado_revision": estado_e,
                                "lugar_ejecucion": lugar_e,
                                "tiempo_ejecucion": tiempo_e,
                                "fecha_manifestacion_interes": formatear_fecha_db(f_int_e),
                                "fecha_sorteo": formatear_fecha_db(f_sor_e),
                                "fecha_limitacion_mipyme": formatear_fecha_db(f_mip_e),
                                "fecha_obs_prepliego": formatear_fecha_db(f_obsp_e),
                                "fecha_obs_pliego_def": formatear_fecha_db(f_obsd_e),
                                "fecha_presentacion_oferta": formatear_fecha_db(f_ofe_e, hora_ofe_e),
                                "codigos_unspsc_req": limpiar_codigos_unspsc(unspsc_input_e) or "N/A",
                                "cant_codigos_unspsc_req": int(cant_u_e),
                                "estampillas": estampillas_e,
                                "req_liquidez_min": r_liq_e,
                                "req_endeudamiento_max": r_end_e,
                                "req_cobertura_intereses_min": r_cob_e,
                                "req_capital_trabajo_cop": limpiar_moneda_input(r_cap_txt_e),
                                "req_rentabilidad_patrimonio_min": r_rpat_e,
                                "req_rentabilidad_activo_min": r_ract_e,
                                "resumen_requerimientos_generales": resumen_e,
                                "exp_general_contratos": eg_cont_e,
                                "exp_general_descripcion": eg_desc_e,
                                "exp_especifica_contratos": ee_cont_e,
                                "exp_especifica_descripcion": ee_desc_e,
                                "regla_emprendimientos_mujeres_mipyme": reg_emp_e,
                                "metodos_oferta_economica": "\n".join(met_eco_edit) if met_eco_edit else "N/A",
                                "factores_tecnicos_ponderables": fac_tec_e,
                                "puntos_tecnica": pt_t_e,
                                "puntos_economica": pt_e_e,
                                "puntos_industria_nacional": pt_i_e,
                                "puntos_discapacidad": pt_d_e,
                                "puntos_mipyme": pt_m_e,
                                "puntos_mujeres": pt_mu_e,
                                "total_puntos": pt_tot_e,
                                "responsable_proceso": responsable_e,
                                "observaciones_recomendaciones": obs_fin_e,
                                "link_secop": link_secop_e,
                                "poliza": pol_tipo_e,
                                "poliza_seriedad_oferta": pol_ser_e,
                                "fecha_solicitud_poliza": formatear_fecha_db(pol_fec_obj_e),
                                "vr_poliza": limpiar_moneda_input(pol_vr_txt_e),
                                "estado_poliza": pol_est_e
                            }
                            try:
                                obtener_cliente_supabase().table("licitaciones_secop").update(dict_actualizado).eq("numero_interno", num_interno_e).execute()
                                st.success("✅ ¡Proceso actualizado con éxito!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al actualizar: {e}")

        # =======================================================
        # MÓDULO 3: REGISTRO / ACTUALIZACIÓN DE EMPRESAS (RUP)
        # =======================================================
        with st.expander("🏢 Registrar Nueva Empresa (RUP)"):
            with st.form("form_nueva_empresa", clear_on_submit=True):
                alias = st.text_input("Alias (Ej. ZEKIA)")
                razon_social = st.text_input("Razón Social Completa")
                nit = st.text_input("NIT")
                
                st.write("**Indicadores Financieros RUP**")
                ac = st.number_input("Act. Corriente", value=0.0, step=1000000.0)
                pc = st.number_input("Pas. Corriente", value=0.0, step=1000000.0)
                at = st.number_input("Act. Total", value=0.0, step=1000000.0)
                pt = st.number_input("Pas. Total", value=0.0, step=1000000.0)
                pat = st.number_input("Patrimonio", value=0.0, step=1000000.0)
                uo = st.number_input("Utilidad Op.", value=0.0, step=1000000.0)
                gi = st.number_input("Gastos Int.", value=0.0, step=1000000.0)
                ct = st.number_input("Cap. Trabajo", value=0.0, step=1000000.0)
                
                st.write("**Clasificación UNSPSC del RUP**")
                st.caption("Pega los códigos UNSPSC registrados en el RUP:")
                unspsc_rup_raw = st.text_area("Códigos UNSPSC en RUP", height=120, placeholder="86101600; 86111500; 90111600...")
                
                if st.form_submit_button("💾 Guardar Empresa (RUP)", type="primary"):
                    if alias and nit:
                        codigos_rup_limpios = limpiar_codigos_unspsc(unspsc_rup_raw)
                        datos_emp = {
                            "alias_codigo": alias.strip().upper(),
                            "razon_social": razon_social.strip() if razon_social.strip() else alias.strip().upper(),
                            "nit": nit.strip(),
                            "activo_corriente": ac,
                            "pasivo_corriente": pc,
                            "activo_total": at,
                            "pasivo_total": pt,
                            "patrimonio": pat,
                            "utilidad_operacional": uo,
                            "gastos_intereses": gi,
                            "capital_trabajo": ct,
                            "codigos_unspsc_rup": codigos_rup_limpios if codigos_rup_limpios else "N/A"
                        }
                        try:
                            cliente = obtener_cliente_supabase()
                            aliases_existentes = {str(e.get("alias_codigo", "")).strip().upper() for e in empresas if isinstance(e, dict)}
                            if alias.strip().upper() in aliases_existentes:
                                cliente.table("empresas_proponentes").update(datos_emp).eq("alias_codigo", alias.strip().upper()).execute()
                                st.success(f"✅ Empresa {alias.upper()} actualizada.")
                            else:
                                cliente.table("empresas_proponentes").insert(datos_emp).execute()
                                st.success(f"✅ Empresa {alias.upper()} registrada.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar empresa: {e}")

    # =====================================================================
    # PANEL CENTRAL DIVIDIDO POR PESTAÑAS (EVALUADOR Y DIRECTORIO)
    # =====================================================================
    tab_eval, tab_directorio = st.tabs(["⚖️ Evaluación de Procesos", "🏢 Directorio de Empresas (RUP)"])

    # ------------------ PESTAÑA 1: EVALUADOR Y GENERADOR DE PDF ------------------
    with tab_eval:
        if not licitaciones_validas: 
            st.warning("⚠️ No hay licitaciones registradas. Agrega una desde el menú lateral izquierdo.")
        else:
            st.header("1. Selección del Proceso SECOP II")
            opciones_lic = {f"#{lic.get('numero_interno', 0)} | {lic.get('numero_proceso', 'S/N')}": lic for lic in licitaciones_validas}
            lic_label = st.selectbox("Licitación a evaluar:", options=list(opciones_lic.keys()))
            licitacion_actual = opciones_lic[lic_label]

            st.header("2. Configuración del Proponente")
            tipo_figura = st.radio("Modalidad de Participación:", ["INDIVIDUAL", "UNION_TEMPORAL"], horizontal=True)
            empresas_validas = [emp for emp in empresas if isinstance(emp, dict)]
            mapa_empresas = {e.get("alias_codigo", "S/N"): e for e in empresas_validas}
            
            if tipo_figura == "INDIVIDUAL":
                alias_sel = st.selectbox("Empresa (RUP):", list(mapa_empresas.keys()))
                empresas_elegidas = [alias_sel]
            else:
                empresas_elegidas = st.multiselect("Integrantes UT:", list(mapa_empresas.keys()), default=[list(mapa_empresas.keys())[0]] if mapa_empresas else [])
                
            nombre_proponente = st.text_input("Nombre Organización / UT:", value=f"UT {' + '.join(empresas_elegidas)}" if tipo_figura != "INDIVIDUAL" else (empresas_elegidas[0] if empresas_elegidas else ""))

            st.subheader(f"📋 {licitacion_actual.get('numero_proceso', '')} — {licitacion_actual.get('entidad', '')}")
            st.write(f"**Objeto:** {licitacion_actual.get('objeto', '')}")
            st.write(f"**Cuantía:** {formatear_moneda_cop(licitacion_actual.get('cuantia_presupuesto', 0))} | **Etapa:** {licitacion_actual.get('etapa_actual', 'N/A')} | **Plazo:** {licitacion_actual.get('tiempo_ejecucion', 'N/A')}")

            if empresas_elegidas:
                integrantes_simulacion = []
                cols_part = st.columns(len(empresas_elegidas))
                for idx, alias in enumerate(empresas_elegidas):
                    emp_copy = dict(mapa_empresas[alias])
                    with cols_part[idx]:
                        pct = 100.0 if tipo_figura == "INDIVIDUAL" else st.number_input(f"% Participación {alias}:", min_value=1.0, max_value=99.0, value=round(100/len(empresas_elegidas), 2))
                    emp_copy["porcentaje_participacion"] = pct
                    integrantes_simulacion.append(emp_copy)

                resultado_sim = consolidar_proponente_plural(licitacion_actual, integrantes_simulacion, tipo_figura)
                
                cruce_u = resultado_sim["cruce_unspsc"]
                st.subheader("🏷️ Cruce de Clasificación UNSPSC (Pliego vs. RUP)")
                col_u1, col_u2, col_u3, col_u4 = st.columns(4)
                col_u1.metric("Publicados en Proceso", cruce_u["total_publicados"])
                col_u2.metric("Mínimo Exigido (Pliego)", cruce_u["min_exigido"])
                col_u3.metric("Cumplidos en RUP", cruce_u["codigos_cumplidos"])
                col_u4.metric("Estado UNSPSC", cruce_u["estado_unspsc"])
                if cruce_u["coincidentes"]:
                    st.caption(f"**Códigos aportados por el RUP:** {'; '.join(cruce_u['coincidentes'])}")

                st.subheader("📊 Consolidado Financiero")
                df_comp = pd.DataFrame([{"Indicador": item["indicador"], "Exigido": item["exigido_fmt"], "Capacidad": item["consolidado_fmt"], "Estado": item["estado"]} for item in resultado_sim["comparativo_indicadores"]])
                st.dataframe(df_comp, use_container_width=True, hide_index=True)
                st.info(f"DICTAMEN FINANCIERO GLOBAL: **{resultado_sim['estado_global']}**")
                st.divider()

                st.header("3. Emisión de Informe Ejecutivo en PDF")
                lic_limpia_pdf = {k: ("N/A" if v is None else v) for k, v in licitacion_actual.items()}
                
                tipo_etiqueta = "UT/Consorcio" if tipo_figura != "INDIVIDUAL" else "Único"
                dic_simulacion = {
                    "nombre_proponente": f"{nombre_proponente} ({tipo_etiqueta})",
                    "estado_global": resultado_sim['estado_global'],
                    "comparativo_indicadores": resultado_sim["comparativo_indicadores"],
                    "codigos_cumplidos": resultado_sim["codigos_cumplidos"],
                    "estado_unspsc": cruce_u["estado_unspsc"]
                }

                try:
                    pdf_bytes = generar_informe_ejecutivo_pdf(licitacion=lic_limpia_pdf, simulacion=dic_simulacion, integrantes=integrantes_simulacion)
                    st.download_button(
                        label="⬇️ Descargar Informe Ejecutivo Corporativo (12 Secciones)",
                        data=pdf_bytes,
                        file_name=f"Informe_Completo_{licitacion_actual.get('numero_proceso', '0')}.pdf",
                        mime="application/pdf",
                        type="primary"
                    )
                except Exception as e:
                    st.error(f"Error al compilar el documento: {e}")

    # ------------------ PESTAÑA 2: DIRECTORIO DE EMPRESAS ------------------
    with tab_directorio:
        st.header("🏢 Base Empresarial y Capacidad Financiera")
        empresas_validas = [emp for emp in empresas if isinstance(emp, dict)]
        if not empresas_validas:
            st.warning("⚠️ No hay empresas registradas. Agrega una desde el menú lateral izquierdo.")
        else:
            df_empresas = pd.DataFrame(empresas_validas)
            cols_mostrar = {"alias_codigo": "Alias", "nit": "NIT", "razon_social": "Razón Social", "capital_trabajo": "Cap. Trabajo ($)", "codigos_unspsc_rup": "Catálogo UNSPSC"}
            cols_existentes = {k: v for k, v in cols_mostrar.items() if k in df_empresas.columns}
            df_vista = df_empresas[list(cols_existentes.keys())].rename(columns=cols_existentes)
            
            if "Cap. Trabajo ($)" in df_vista.columns: df_vista["Cap. Trabajo ($)"] = df_vista["Cap. Trabajo ($)"].apply(lambda x: formatear_moneda_cop(x))
            if "Catálogo UNSPSC" in df_vista.columns:
                df_vista["Cant. Códigos"] = df_vista["Catálogo UNSPSC"].apply(lambda x: len(str(x).split(";")) if x and str(x) != "N/A" else 0)
                df_vista = df_vista.drop(columns=["Catálogo UNSPSC"])
            
            st.dataframe(df_vista, use_container_width=True, hide_index=True)
            st.divider()
            
            st.subheader("🔍 Ficha Técnica Detallada")
            mapa_empresas = {e.get("alias_codigo", "S/N"): e for e in empresas_validas}
            alias_sel = st.selectbox("Selecciona una empresa para analizar sus indicadores y códigos:", list(mapa_empresas.keys()))
            
            if alias_sel:
                e_data = mapa_empresas[alias_sel]
                ac, pc, at, pt = float(e_data.get('activo_corriente', 0)), float(e_data.get('pasivo_corriente', 0)), float(e_data.get('activo_total', 0)), float(e_data.get('pasivo_total', 0))
                pat, uo, gi, ct = float(e_data.get('patrimonio', 0)), float(e_data.get('utilidad_operacional', 0)), float(e_data.get('gastos_intereses', 0)), float(e_data.get('capital_trabajo', 0))
                
                liq = (ac / pc) if pc > 0 else 0
                end = (pt / at) if at > 0 else 0
                cob = (uo / gi) if gi > 0 else ("INDETERMINADO" if gi == 0 else 0)
                rp = (uo / pat) if pat > 0 else 0
                ra = (uo / at) if at > 0 else 0
                
                st.markdown(f"**Empresa:** {e_data.get('razon_social', alias_sel)} (NIT: {e_data.get('nit', 'N/A')})")
                col_i1, col_i2, col_i3, col_i4, col_i5 = st.columns(5)
                col_i1.metric("Liquidez (x)", f"{liq:,.2f}")
                col_i2.metric("Endeudamiento", f"{end*100:,.2f}%")
                col_i3.metric("Cobertura Int. (x)", cob if isinstance(cob, str) else f"{cob:,.2f}")
                col_i4.metric("Rent. Patrimonio", f"{rp*100:,.2f}%")
                col_i5.metric("Rent. Activo", f"{ra*100:,.2f}%")
                
                st.write(f"**Capital de Trabajo:** {formatear_moneda_cop(ct)}")
                
                st.write("**Catálogo de Códigos UNSPSC registrados en RUP:**")
                cods_str = str(e_data.get("codigos_unspsc_rup", "No registra"))
                if cods_str and cods_str != "N/A":
                    lista_cods = [c.strip() for c in cods_str.split(";")]
                    st.caption(f"Total inscritos: {len(lista_cods)} códigos")
                    st.info(" ; ".join(lista_cods))
                else: st.info("Sin códigos registrados.")

if __name__ == "__main__":
    main()
