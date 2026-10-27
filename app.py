"""
Módulo Único: Centro de Comando (Buscador SECOP, Evaluador UT y Emisión PDF Completa)
"""

import os
import datetime
from dotenv import load_dotenv
load_dotenv()

import pandas as pd
import streamlit as st
import requests
from typing import Dict, Any, List, Optional, Tuple

from generador_pdf import generar_informe_ejecutivo_pdf, formatear_moneda_cop, formatear_indicador

# =====================================================================
# 1. CONEXIÓN A SUPABASE
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
            
            empresas = emp_res.data if isinstance(emp_res.data, list) else []
            licitaciones = lic_res.data if isinstance(lic_res.data, list) else []
            return empresas, licitaciones
        except Exception as e:
            st.sidebar.error(f"Error de lectura: {e}")
    return [], []

# =====================================================================
# 2. MOTOR MATEMÁTICO FINANCIERO
# =====================================================================
def evaluar_indicador(nombre: str, regla: str, exigido: Optional[float], valor_consolidado: Optional[float], es_porcentaje: bool = False, es_moneda: bool = False, indeterminado: bool = False) -> Dict[str, Any]:
    if exigido is None:
        return {"indicador": nombre, "regla": regla, "exigido_fmt": "N/A", "consolidado_fmt": formatear_moneda_cop(valor_consolidado) if es_moneda else formatear_indicador(valor_consolidado, es_porcentaje, indeterminado), "estado": "NO EXIGIDO"}
    
    exigido_fmt = formatear_moneda_cop(exigido) if es_moneda else formatear_indicador(exigido, es_porcentaje, False)
    consolidado_fmt = formatear_moneda_cop(valor_consolidado) if es_moneda else formatear_indicador(valor_consolidado, es_porcentaje, indeterminado)
    
    if indeterminado or valor_consolidado is None:
        estado = "REVISAR"
    else:
        if regla == ">=": estado = "CUMPLE" if float(valor_consolidado) >= float(exigido) else "NO CUMPLE"
        elif regla == "<=": estado = "CUMPLE" if float(valor_consolidado) <= float(exigido) else "NO CUMPLE"
        else: estado = "REVISAR"

    return {"indicador": nombre, "regla": regla, "exigido_fmt": exigido_fmt, "consolidado_fmt": consolidado_fmt, "estado": estado}

def consolidar_proponente_plural(licitacion: Dict[str, Any], integrantes_seleccionados: List[Dict[str, Any]], tipo_figura: str = "UNION_TEMPORAL") -> Dict[str, Any]:
    ac_cons, pc_cons, at_cons, pt_cons, pat_cons, uo_cons, gi_cons, ct_cons = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

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

    return {
        "tipo_figura": tipo_figura,
        "comparativo_indicadores": comparativo,
        "estado_global": estado_global,
        "codigos_cumplidos": sum([int(emp.get("codigos_aportados", 0)) for emp in integrantes_seleccionados])
    }

# =====================================================================
# 3. INTERFAZ ALL-IN-ONE
# =====================================================================
def limpiar_num(v):
    try: return float(v)
    except: return 0.0

def main():
    st.set_page_config(page_title="SECOP II ProMax", page_icon="⚖️", layout="wide")
    st.title("⚖️ Centro de Comando SECOP II — ASESOL / ZEKIA")

    empresas, licitaciones = cargar_datos_base()
    
    with st.sidebar:
        # MÓDULO 1: BUSCADOR Y CREADOR DE PROCESOS (COMPLETO)
        with st.expander("➕ Buscar y Registrar Nuevo Proceso", expanded=True):
            col_b1, col_b2 = st.columns([2, 1])
            exp_buscar = col_b1.text_input("Expediente (Ej. FDL-001)")
            
            if col_b2.button("Buscar API"):
                if exp_buscar:
                    try:
                        resp = requests.get("https://www.datos.gov.co/resource/p6dx-8zbt.json", params={"referencia_del_proceso": exp_buscar.strip()})
                        if resp.status_code == 200 and len(resp.json()) > 0:
                            datos = resp.json()[0]
                            st.session_state['api_entidad'] = datos.get('entidad', '')
                            st.session_state['api_objeto'] = datos.get('descripci_n_del_procedimiento', datos.get('detalle_del_objeto_a_contratar', datos.get('descripcion_del_proceso', '')))
                            
                            presupuesto_str = datos.get('precio_base', datos.get('cuantia_proceso', datos.get('estimacion_del_presupuesto', 0)))
                            try:
                                st.session_state['api_cuantia'] = float(presupuesto_str)
                            except ValueError:
                                st.session_state['api_cuantia'] = 0.0
                                
                            # Extraer URL permanente oficial
                            url_cruda = datos.get('urlproceso', '')
                            st.session_state['api_link'] = url_cruda.get('url', '') if isinstance(url_cruda, dict) else url_cruda
                            
                            st.success("✅ Datos básicos extraídos de SECOP.")
                        else:
                            st.warning("⚠️ No encontrado en la API del Estado.")
                    except:
                        st.error("Error de conexión.")
            
            with st.form("form_guardar_proceso", clear_on_submit=True):
                num_interno = st.number_input("Nº Interno ASESOL", value=100)
                num_proceso = st.text_input("Número de Proceso", value=exp_buscar)
                entidad = st.text_input("Entidad", value=st.session_state.get('api_entidad', ''))
                objeto = st.text_area("Objeto del Contrato", value=st.session_state.get('api_objeto', ''))
                link_permanente = st.text_input("Link SECOP II", value=st.session_state.get('api_link', ''))
                
                col_f1, col_f2 = st.columns(2)
                modalidad = col_f1.selectbox("Modalidad", ["Selección Abreviada", "Licitación Pública", "Mínima Cuantía", "Concurso de Méritos"])
                cuantia = col_f2.number_input("Presupuesto", value=st.session_state.get('api_cuantia', 0.0), step=1000000.0)
                
                st.write("**Requisitos Financieros Exigidos**")
                req_liq = st.number_input("Liquidez Exigida (>)", value=0.0, step=0.1)
                req_end = st.number_input("Endeudamiento Exigido (<) %", value=0.0, step=0.1)
                req_cob = st.number_input("Cobertura Exigida (>)", value=0.0, step=0.1)
                
                st.write("**Hitos y Fechas Clave**")
                f_interes = st.text_input("Fecha Manifestación Interés", value="N/A")
                f_sorteo = st.text_input("Fecha Sorteo", value="N/A")
                f_mipyme = st.text_input("Fecha Limitación Mipyme", value="N/A")
                f_obs_pre = st.text_input("Fecha Obs. Proyectos", value="N/A")
                f_obs_def = st.text_input("Fecha Obs. Definitivos", value="N/A")
                f_oferta = st.text_input("Fecha Presentación Oferta", value="N/A")
                
                st.write("**Componente Técnico y Experiencia**")
                resumen_gen = st.text_area("Síntesis Ejecución / Requisitos", value="N/A")
                exp_gen_cont = st.text_input("Contratos Exp. General", value="N/A")
                exp_gen_desc = st.text_area("Descripción Exp. General", value="N/A")
                exp_esp_cont = st.text_input("Contratos Exp. Específica", value="N/A")
                exp_esp_desc = st.text_area("Descripción Exp. Específica", value="N/A")
                regla_emp = st.text_area("Reglas Emprendimientos / Mujeres / Mipyme", value="N/A")
                obs_rec = st.text_area("Observaciones y Recomendaciones", value="N/A")
                
                if st.form_submit_button("Guardar Proceso Completo", type="primary"):
                    if num_proceso and entidad:
                        nueva_lic = {
                            "numero_interno": num_interno, "numero_proceso": num_proceso,
                            "entidad": entidad, "objeto": objeto, "modalidad": modalidad,
                            "cuantia_presupuesto": cuantia, "etapa_actual": "Presentación Ofertas",
                            "estado_revision": "ACTIVO", 
                            "req_liquidez_min": req_liq if req_liq > 0 else None,
                            "req_endeudamiento_max": req_end if req_end > 0 else None,
                            "req_cobertura_intereses_min": req_cob if req_cob > 0 else None,
                            "link_secop": link_permanente,
                            "fecha_manifestacion_interes": f_interes, "fecha_sorteo": f_sorteo,
                            "fecha_limitacion_mipyme": f_mipyme, "fecha_obs_prepliego": f_obs_pre,
                            "fecha_obs_pliego_def": f_obs_def, "fecha_presentacion_oferta": f_oferta,
                            "resumen_requerimientos_generales": resumen_gen,
                            "exp_general_contratos": exp_gen_cont, "exp_general_descripcion": exp_gen_desc,
                            "exp_especifica_contratos": exp_esp_cont, "exp_especifica_descripcion": exp_esp_desc,
                            "regla_emprendimientos_mujeres_mipyme": regla_emp,
                            "observaciones_recomendaciones": obs_rec
                        }
                        try:
                            obtener_cliente_supabase().table("licitaciones_secop").insert(nueva_lic).execute()
                            for k in ['api_entidad', 'api_objeto', 'api_cuantia', 'api_link']:
                                if k in st.session_state: del st.session_state[k]
                            st.success("✅ ¡Proceso registrado con éxito!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")

        # MÓDULO 2: REGISTRO MANUAL DE EMPRESAS
        with st.expander("🏢 Registrar Nueva Empresa (RUP)"):
            with st.form("form_nueva_empresa", clear_on_submit=True):
                alias = st.text_input("Alias / Código corto (Ej. ZEKIA)")
                razon_social = st.text_input("Razón Social Completa")
                nit = st.text_input("NIT")
                
                ac = st.number_input("Activo Corriente", value=0.0, step=1000000.0)
                pc = st.number_input("Pasivo Corriente", value=0.0, step=1000000.0)
                at = st.number_input("Activo Total", value=0.0, step=1000000.0)
                pt = st.number_input("Pasivo Total", value=0.0, step=1000000.0)
                pat = st.number_input("Patrimonio", value=0.0, step=1000000.0)
                uo = st.number_input("Utilidad Operacional", value=0.0, step=1000000.0)
                gi = st.number_input("Gastos de Intereses", value=0.0, step=1000000.0)
                ct = st.number_input("Capital de Trabajo", value=0.0, step=1000000.0)
                
                if st.form_submit_button("Guardar Empresa", type="primary"):
                    if alias and nit:
                        nueva_emp = {
                            "alias_codigo": alias, "razon_social": razon_social, "nit": nit, 
                            "activo_corriente": ac, "pasivo_corriente": pc, "activo_total": at, 
                            "pasivo_total": pt, "patrimonio": pat, "utilidad_operacional": uo, 
                            "gastos_intereses": gi, "capital_trabajo": ct
                        }
                        try:
                            obtener_cliente_supabase().table("empresas_proponentes").insert(nueva_emp).execute()
                            st.success("✅ Empresa guardada.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

    # =====================================================================
    # PANEL CENTRAL: EVALUACIÓN Y EMISIÓN PDF COMPLETA
    # =====================================================================
    licitaciones_validas = [lic for lic in licitaciones if isinstance(lic, dict)]
    if not licitaciones_validas: 
        st.warning("⚠️ No hay licitaciones registradas. Agrega una desde el menú lateral izquierdo.")
        return

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
        
    nombre_proponente = st.text_input("Nombre de la Organización / UT:", value=f"UT {' + '.join(empresas_elegidas)}" if tipo_figura != "INDIVIDUAL" else (empresas_elegidas[0] if empresas_elegidas else ""))

    st.subheader(f"📋 {licitacion_actual.get('numero_proceso', '')} — {licitacion_actual.get('entidad', '')}")
    st.write(f"**Objeto:** {licitacion_actual.get('objeto', '')}")
    st.write(f"**Cuantía:** {formatear_moneda_cop(licitacion_actual.get('cuantia_presupuesto', 0))}")

    if not empresas_elegidas: return
    
    integrantes_simulacion = []
    cols_part = st.columns(len(empresas_elegidas))
    for idx, alias in enumerate(empresas_elegidas):
        emp_copy = dict(mapa_empresas[alias])
        with cols_part[idx]:
            pct = 100.0 if tipo_figura == "INDIVIDUAL" else st.number_input(f"% Participación {alias}:", min_value=1.0, max_value=99.0, value=round(100/len(empresas_elegidas),2))
        emp_copy["porcentaje_participacion"] = pct
        integrantes_simulacion.append(emp_copy)

    resultado_sim = consolidar_proponente_plural(licitacion_actual, integrantes_simulacion, tipo_figura)
    
    st.subheader("📊 Consolidado Financiero")
    df_comp = pd.DataFrame([{"Indicador": item["indicador"], "Exigido": item["exigido_fmt"], "Capacidad": item["consolidado_fmt"], "Estado": item["estado"]} for item in resultado_sim["comparativo_indicadores"]])
    st.dataframe(df_comp, use_container_width=True, hide_index=True)
    st.info(f"DICTAMEN GLOBAL: **{resultado_sim['estado_global']}**")

    st.divider()

    # =====================================================================
    # 3. GENERACIÓN DIRECTA DE PDF COMPLETO
    # =====================================================================
    st.header("3. Emisión de Informe Ejecutivo en PDF")
    st.info("El PDF incorporará automáticamente los hitos, la experiencia y los enlaces oficiales guardados en este proceso.")
    
    tipo_etiqueta = "UT/Consorcio" if tipo_figura != "INDIVIDUAL" else "Único"
    dic_simulacion = {
        "nombre_proponente": f"{nombre_proponente} ({tipo_etiqueta})",
        "estado_global": resultado_sim['estado_global'],
        "comparativo_indicadores": resultado_sim["comparativo_indicadores"]
    }

    try:
        pdf_bytes = generar_informe_ejecutivo_pdf(
            licitacion=licitacion_actual,
            simulination=dic_simulacion, iface=None,
            simulacion=dic_simulacion,
            integrantes=[]
        )
        st.download_button(
            label="⬇️ Descargar Informe Ejecutivo Completo (PDF)",
            data=pdf_bytes,
            file_name=f"Informe_Completo_{licitacion_actual.get('numero_proceso', '0')}.pdf",
            mime="application/pdf",
            type="primary"
        )
    except Exception as e:
        st.error(f"Error al compilar el documento: {e}")

if __name__ == "__main__":
    main()
