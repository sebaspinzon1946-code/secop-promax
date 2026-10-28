"""
Módulo Único: Centro de Comando (Buscador SECOP + Web Scraper, Evaluador UT y Emisión PDF Completa)
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
# LISTAS OFICIALES EXTRAÍDAS DEL EXCEL MAESTRO (HOJA 'LISTAS')
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
# 1. CONEXIÓN A SUPABASE Y UTILIDADES DE FORMATO EN MILES
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
    """Formatea cualquier número a cadena con separador de miles (Ej: $ 1.373.261.913)."""
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

def limpiar_moneda_input(texto: Any) -> float:
    """Convierte una cadena con formato de miles ($ 1.373.261.913) a float puro para Supabase."""
    if isinstance(texto, (int, float)):
        return float(texto)
    if not texto:
        return 0.0
    s = str(texto).strip().replace("$", "").strip()
    if "," in s:
        s = s.split(",")[0]
    limpio = re.sub(r'[^\d]', '', s)
    try:
        return float(limpio)
    except Exception:
        return 0.0

def limpiar_codigos_unspsc(texto_crudo: str) -> Tuple[str, int]:
    """Extrae automáticamente todos los códigos de 8 dígitos aunque se peguen con descripción."""
    if not texto_crudo:
        return "", 0
    codigos_8_digitos = list(dict.fromkeys(re.findall(r'\b(\d{8})\b', str(texto_crudo))))
    if codigos_8_digitos:
        return "; ".join(codigos_8_digitos), len(codigos_8_digitos)
    partes = [c.strip() for c in str(texto_crudo).replace(';', '\n').split('\n') if c.strip()]
    return "; ".join(partes), len(partes)

def parsear_fecha_hora_secop(valor_str: Any) -> Tuple[Optional[datetime.date], Optional[datetime.time]]:
    """Convierte fechas ISO de la API o DD/MM/YYYY de la web de SECOP en objetos date y time."""
    if not valor_str or str(valor_str).strip() in ["", "N/A", "None", "nan"]:
        return None, None
    s = str(valor_str).strip()
    # 1. Formato ISO Socrata: 2026-10-30T10:00:00.000
    try:
        dt = datetime.datetime.fromisoformat(s.replace("Z", ""))
        hora = dt.time() if (dt.hour != 0 or dt.minute != 0) else None
        return dt.date(), hora
    except Exception:
        pass
    # 2. Formato Web SECOP II: DD/MM/YYYY HH:MM o DD/MM/YYYY
    m = re.search(r'(\d{2})/(\d{2})/(\d{4})(?:\s+(\d{1,2}):(\d{2}))?', s)
    if m:
        try:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            fecha = datetime.date(y, mo, d)
            if m.group(4) and m.group(5):
                h, mi = int(m.group(4)), int(m.group(5))
                if "p." in s.lower() and h < 12:
                    h += 12
                return fecha, datetime.time(h, mi)
            return fecha, None
        except Exception:
            pass
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

# =====================================================================
# RASTREADOR MIXTO: API DATOS ABIERTOS + RASTREO WEB DIRECTO SECOP II
# =====================================================================
def rastrear_web_secop(url_secop: str) -> Dict[str, Any]:
    """Rastrea la página pública de SECOP II para extraer Duración, Lista de UNSPSC y Cronograma."""
    extra = {}
    if not url_secop or not url_secop.startswith("http"):
        return extra
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get(url_secop, headers=headers, timeout=12)
        if r.status_code != 200:
            return extra
        html = r.text
        texto_plano = re.sub(r'<[^>]+>', ' ', html)
        texto_plano = re.sub(r'\s+', ' ', texto_plano)

        # 1. Duración del contrato (Ej. "Duración del contrato: 7 (Meses)")
        m_dur = re.search(r'Duraci[óo]n del contrato[:\s]*(\d+)\s*\(?([A-Za-zÁÉÍÓÚáéíóú]+)\)?', texto_plano, re.IGNORECASE)
        if m_dur:
            extra['tiempo'] = f"{m_dur.group(1)} {m_dur.group(2).lower()}"

        # 2. Todos los códigos UNSPSC publicados en la página (Principal + Lista adicional)
        codigos_web = list(dict.fromkeys(re.findall(r'\b(\d{8})\s*-\s*', texto_plano)))
        if codigos_web:
            extra['unspsc'] = "; ".join(codigos_web)
            extra['cant_unspsc'] = len(codigos_web)

        # 3. Fechas Hito del Cronograma en la página de SECOP II
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
                if f_dt:
                    extra[clave] = f_dt
                if clave == 'f_ofe' and h_dt:
                    extra['h_ofe'] = h_dt
    except Exception:
        pass
    return extra

def buscar_proceso_secop_completo(expediente: str, link_manual: str = "") -> bool:
    """Consulta la API de Datos Abiertos y complementa con el rastreo web de SECOP II."""
    encontrado = False
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    url_api = "https://www.datos.gov.co/resource/p6dx-8zbt.json"
    datos = {}

    if expediente:
        exp_clean = expediente.strip()
        try:
            resp = requests.get(url_api, headers=headers, params={"referencia_del_proceso": exp_clean}, timeout=10)
            if resp.status_code == 200 and len(resp.json()) > 0:
                datos = resp.json()[0]
            else:
                # Búsqueda flexible por si la entidad dejó espacios en el número de proceso
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
        try:
            st.session_state['api_cuantia'] = formatear_miles_input(float(presupuesto_str))
        except Exception:
            st.session_state['api_cuantia'] = "$ 0"

        st.session_state['api_modalidad'] = homologar_modalidad(datos.get('modalidad_de_contratacion', ''))
        st.session_state['api_etapa'] = homologar_etapa(datos.get('fase', datos.get('estado_del_procedimiento', '')))
        st.session_state['api_lugar'] = datos.get('ciudad_entidad', datos.get('ciudad_de_la_unidad_de', 'Bogotá D.C.'))

        # Tiempo de ejecución desde API (duracion + unidad_de_duracion)
        dur = str(datos.get('duracion', '')).strip()
        unid = str(datos.get('unidad_de_duracion', '')).strip()
        if dur and dur not in ['0', 'N/A', 'None']:
            st.session_state['api_tiempo'] = f"{dur} {unid.lower()}".strip()

        # Enlace permanente
        url_cruda = datos.get('urlproceso', '')
        link_api = url_cruda.get('url', '') if isinstance(url_cruda, dict) else str(url_cruda)
        if link_api:
            st.session_state['api_link'] = link_api

        # Código UNSPSC desde API
        cod_api = datos.get('codigo_principal_de_categoria', datos.get('codigos_unspsc', ''))
        cod_limpio, cant_cod = limpiar_codigos_unspsc(cod_api)
        if cod_limpio:
            st.session_state['api_unspsc'] = cod_limpio
            st.session_state['api_cant_unspsc'] = cant_cod

        # Fechas disponibles en API
        f_rec, h_rec = parsear_fecha_hora_secop(datos.get('fecha_de_recepcion_de', datos.get('fecha_de_recepcion_de_ofertas')))
        if f_rec: st.session_state['api_f_ofe'] = f_rec
        if h_rec: st.session_state['api_h_ofe'] = h_rec

        f_obsp, _ = parsear_fecha_hora_secop(datos.get('fecha_de_publicacion_fase_borrador', datos.get('fecha_de_publicacion_del')))
        if f_obsp: st.session_state['api_f_obsp'] = f_obsp

        f_obsd, _ = parsear_fecha_hora_secop(datos.get('fecha_de_ultima_publicaci'))
        if f_obsd: st.session_state['api_f_obsd'] = f_obsd

    # Rastreo directo de la página web de SECOP II (para capturar lista completa UNSPSC, duración y cronograma)
    url_objetivo = link_manual.strip() if link_manual.strip() else st.session_state.get('api_link', '')
    if url_objetivo:
        datos_web = rastrear_web_secop(url_objetivo)
        if datos_web:
            encontrado = True
            if 'tiempo' in datos_web: st.session_state['api_tiempo'] = datos_web['tiempo']
            if 'unspsc' in datos_web:
                st.session_state['api_unspsc'] = datos_web['unspsc']
                st.session_state['api_cant_unspsc'] = datos_web['cant_unspsc']
            for k_f in ['f_int', 'f_mip', 'f_obsp', 'f_obsd', 'f_ofe', 'h_ofe']:
                if k_f in datos_web:
                    st.session_state[f'api_{k_f}'] = datos_web[k_f]

    return encontrado

# =====================================================================
# 2. MOTOR MATEMÁTICO FINANCIERO
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

def consolidar_proponente_plural(licitacion, integrantes_seleccionados, tipo_figura="UNION_TEMPORAL"):
    ac_cons = pc_cons = at_cons = pt_cons = pat_cons = uo_cons = gi_cons = ct_cons = 0.0

    for emp in integrantes_seleccionados:
        peso = float(emp.get("porcentaje_participacion", 0.0)) / 100.0 if tipo_figura != "INDIVIDUAL" else 1.0
        ac_cons += float(emp.get("activo_corriente", 0.0)) * peso
        pc_
