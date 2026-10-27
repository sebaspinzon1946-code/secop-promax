"""
Módulo 2: Motor de Evaluación, Simulador UT y Migrador de Excel (Streamlit)
"""

import os
from dotenv import load_dotenv
load_dotenv()

import pandas as pd
import streamlit as st
import requests  # <- Nueva librería agregada para buscar en SECOP
from typing import Dict, Any, List, Optional, Tuple

from generador_pdf import generar_informe_ejecutivo_pdf, formatear_moneda_cop, formatear_indicador

# =====================================================================
# 1. CONEXIÓN A SUPABASE Y EXTRACCIÓN SEGURA
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
# 2. MOTOR MATEMÁTICO (COLOMBIA COMPRA EFICIENTE)
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
# 3. INTERFAZ WEB Y CARGA DE DATOS
# =====================================================================
def limpiar_num(v):
    try: return float(v)
    except: return 0.0

def main():
    st.set_page_config(page_title="SECOP II ProMax", page_icon="⚖️", layout="wide")
    st.title("⚖️ Plataforma SaaS SECOP II — Evaluador Financiero y Simulador UT")

    empresas, licitaciones = cargar_datos_base()
    
    with st.sidebar:
        # =======================================================
        # NUEVO MÓDULO 1: BUSCADOR Y CREADOR DE PROCESOS (API)
        # =======================================================
        with st.expander("➕ Buscar y Seguir Nuevo Proceso", expanded=True):
            st.caption("Busca en SECOP II y agrégalo a tu base de datos para evaluarlo.")
            
            col_b1, col_b2 = st.columns([2, 1])
            exp_buscar = col_b1.text_input("Expediente (Ej. FDL-001)")
            
            if col_b2.button("Buscar"):
                if exp_buscar:
                    try:
                        resp = requests.get("https://www.datos.gov.co/resource/p6dx-8zbt.json", params={"referencia_del_proceso": exp_buscar.strip()})
                        if resp.status_code == 200 and len(resp.json()) > 0:
                            datos = resp.json()[0]
                            st.session_state['api_entidad'] = datos.get('entidad', '')
                            
                            # Extracción robusta del Objeto (cubre múltiples variables de SECOP II)
                            st.session_state['api_objeto'] = datos.get('descripci_n_del_procedimiento', datos.get('detalle_del_objeto_a_contratar', datos.get('descripcion_del_proceso', '')))
                            
                            # Extracción robusta del Presupuesto
                            presupuesto_str = datos.get('precio_base', datos.get('cuantia_proceso', datos.get('estimacion_del_presupuesto', 0)))
                            try:
                                st.session_state['api_cuantia'] = float(presupuesto_str)
                            except ValueError:
                                st.session_state['api_cuantia'] = 0.0
                                
                            st.success("✅ Datos extraídos. Completa los requisitos abajo y guarda.")
                        else:
                            st.warning("⚠️ No encontrado en la API del Estado.")
                    except:
                        st.error("Error de conexión.")
            
            with st.form("form_guardar_proceso", clear_on_submit=True):
                num_interno = st.number_input("Nº Interno (Consecutivo ASESOL)", value=100)
                num_proceso = st.text_input("Número de Proceso", value=exp_buscar)
                entidad = st.text_input("Entidad Contratante", value=st.session_state.get('api_entidad', ''))
                objeto = st.text_area("Objeto del Contrato", value=st.session_state.get('api_objeto', ''))
                
                col_f1, col_f2 = st.columns(2)
                modalidad = col_f1.selectbox("Modalidad", ["Selección Abreviada", "Licitación Pública", "Mínima Cuantía", "Concurso de Méritos"])
                cuantia = col_f2.number_input("Presupuesto Oficial", value=st.session_state.get('api_cuantia', 0.0), step=1000000.0)
                
                st.write("**Requisitos Financieros Exigidos (Pliego)**")
                req_liq = st.number_input("Liquidez Exigida (>)", value=0.0, step=0.1)
                req_end = st.number_input("Endeudamiento Exigido (<) %", value=0.0, step=0.1)
                req_cob = st.number_input("Cobertura Exigida (>)", value=0.0, step=0.1)
                
                if st.form_submit_button("Guardar como Proceso a Seguir", type="primary"):
                    if num_proceso and entidad:
                        nueva_lic = {
                            "numero_interno": num_interno,
                            "numero_proceso": num_proceso,
                            "entidad": entidad,
                            "objeto": objeto,
                            "modalidad": modalidad,
                            "cuantia_presupuesto": cuantia,
                            "etapa_actual": "Presentación Ofertas",
                            "estado_revision": "ACTIVO",
                            "req_liquidez_min": req_liq if req_liq > 0 else None,
                            "req_endeudamiento_max": req_end if req_end > 0 else None,
                            "req_cobertura_intereses_min": req_cob if req_cob > 0 else None
                        }
                        try:
                            obtener_cliente_supabase().table("licitaciones_secop").insert(nueva_lic).execute()
                            # Limpiamos la memoria temporal tras guardar
                            for k in ['api_entidad', 'api_objeto', 'api_cuantia']:
                                if k in st.session_state: del st.session_state[k]
                            st.success(f"✅ ¡Proceso {num_proceso} guardado con éxito!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")

        # =======================================================
        # NUEVO MÓDULO 2: REGISTRO MANUAL DE EMPRESAS (RUP)
        # =======================================================
        with st.expander("🏢 Registrar Nueva Empresa (RUP)"):
            with st.form("form_nueva_empresa", clear_on_submit=True):
                alias = st.text_input("Alias / Código corto (Ej. ZEKIA)")
                razon_social = st.text_input("Razón Social Completa")
                nit = st.text_input("NIT")
                
                st.write("**Datos Financieros RUP**")
                ac = st.number_input("Activo Corriente", value=0.0, step=1000000.0)
                pc = st.number_input("Pasivo Corriente", value=0.0, step=1000000.0)
                at = st.number_input("Activo Total", value=0.0, step=1000000.0)
                pt = st.number_input("Pasivo Total", value=0.0, step=1000000.0)
                pat = st.number_input("Patrimonio", value=0.0, step=1000000.0)
                uo = st.number_input("Utilidad Operacional", value=0.0, step=1000000.0)
                gi = st.number_input("Gastos de Intereses", value=0.0, step=1000000.0)
                ct = st.number_input("Capital de Trabajo", value=0.0, step=1000000.0)
                
                if st.form_submit_button("Guardar Empresa en Base de Datos", type="primary"):
                    if alias and nit:
                        nueva_emp = {
                            "alias_codigo": alias, "razon_social": razon_social, "nit": nit, 
                            "activo_corriente": ac, "pasivo_corriente": pc, "activo_total": at, 
                            "pasivo_total": pt, "patrimonio": pat, "utilidad_operacional": uo, 
                            "gastos_intereses": gi, "capital_trabajo": ct
                        }
                        try:
                            obtener_cliente_supabase().table("empresas_proponentes").insert(nueva_emp).execute()
                            st.success("✅ Empresa guardada con éxito.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")

        # =======================================================
        # MÓDULO 3: MIGRACIÓN MASIVA (EXCEL)
        # =======================================================
        with st.expander("📥 Cargar Excel Histórico (Migración)"):
            st.info("Sube tu archivo Maestro para poblar la base de datos de forma masiva.")
            archivo_excel = st.file_uploader("Seleccionar archivo Excel", type=["xlsx", "xls"])
            
            if archivo_excel and st.button("Iniciar Migración a Supabase"):
                cliente = obtener_cliente_supabase()
                if not cliente:
                    st.error("Error: No hay conexión a Supabase configurada.")
                else:
                    try:
                        df_lic = pd.read_excel(archivo_excel, sheet_name="MATRIZ GENERAL")
                        df_lic.columns = [str(c).strip().upper() for c in df_lic.columns]
                        registros_lic = []
                        for _, fila in df_lic.iterrows():
                            num_proc = str(fila.get("NO. PROCESO", fila.get("N. PROCESO", ""))).strip()
                            if not num_proc or num_proc == "nan": continue
                            registros_lic.append({
                                "numero_interno": int(limpiar_num(fila.get("NO.", 0))),
                                "entidad": str(fila.get("ENTIDAD", "")),
                                "numero_proceso": num_proc,
                                "objeto": str(fila.get("OBJETO", "")),
                                "modalidad": str(fila.get("MODALIDAD", "")),
                                "cuantia_presupuesto": limpiar_num(fila.get("CUANTIA", fila.get("PRESUPUESTO OFICIAL", 0))),
                                "etapa_actual": str(fila.get("ETAPA ACTUAL DEL PROCESO", fila.get("ETAPA ACTUAL", ""))),
                                "estado_revision": str(fila.get("ESTADO REVISION", fila.get("REVISION", ""))),
                            })
                        if registros_lic:
                            cliente.table("licitaciones_secop").insert(registros_lic).execute()
                        
                        df_emp = pd.read_excel(archivo_excel, sheet_name="RUP EMPRESAS")
                        df_emp.columns = [str(c).strip().upper() for c in df_emp.columns]
                        registros_emp = []
                        for _, fila in df_emp.iterrows():
                            nit = str(fila.get("NIT", "")).strip()
                            if not nit or nit == "nan": continue
                            registros_emp.append({
                                "alias_codigo": str(fila.get("ALIAS", fila.get("ALIAS/CODIGO", "N/A"))).strip(),
                                "razon_social": str(fila.get("RAZON SOCIAL", fila.get("RAZÓN SOCIAL", "N/A"))).strip(),
                                "nit": nit,
                                "activo_corriente": limpiar_num(fila.get("ACTIVO CORRIENTE")),
                                "pasivo_corriente": limpiar_num(fila.get("PASIVO CORRIENTE")),
                                "activo_total": limpiar_num(fila.get("ACTIVO TOTAL")),
                                "pasivo_total": limpiar_num(fila.get("PASIVO TOTAL")),
                                "patrimonio": limpiar_num(fila.get("PATRIMONIO")),
                                "utilidad_operacional": limpiar_num(fila.get("UTILIDAD OPERACIONAL")),
                                "gastos_intereses": limpiar_num(fila.get("GASTOS DE INTERESES", fila.get("GASTOS DE INTERES", 0))),
                                "capital_trabajo": limpiar_num(fila.get("CAPITAL DE TRABAJO")),
                            })
                        if registros_emp:
                            cliente.table("empresas_proponentes").insert(registros_emp).execute()
                        
                        st.success("¡Migración completada!")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Error detallado de guardado: {e}")
        
        st.divider()

    # BLOQUE DE DIAGNÓSTICO
    if not licitaciones or not empresas:
        cliente = obtener_cliente_supabase()
        st.subheader("🔍 Diagnóstico Definitivo")
        if not cliente:
            st.error("🔴 **Error Local:** El sistema no detecta tus credenciales. Asegúrate de que iniciaste la consola negra estando dentro de la carpeta `D:\\PlataformaLicitaciones` para que pueda leer el archivo `.env`.")
        else:
            try:
                test = cliente.table("licitaciones_secop").select("*").limit(1).execute()
                if not test.data:
                    st.warning("🟡 **Supabase está conectado, pero responde con 0 datos.** (Puede ser por la falla técnica de sus servidores o la caché de seguridad).")
                else:
                    st.success(f"🟢 **¡Conectado! Datos crudos detectados:** {test.data}")
            except Exception as e:
                st.error(f"🔴 **Supabase rechazó la lectura por este error:** {e}")
        return

    st.header("1. Selección del Proceso SECOP II")
    
    licitaciones_validas = [lic for lic in licitaciones if isinstance(lic, dict)]
    if not licitaciones_validas: return

    opciones_lic = {f"#{lic.get('numero_interno', 0)} | {lic.get('numero_proceso', 'S/N')}": lic for lic in licitaciones_validas}
    lic_label = st.selectbox("Licitación a evaluar:", options=list(opciones_lic.keys()))
    licitacion_actual = opciones_lic[lic_label]

    st.header("2. Configuración del Proponente")
    tipo_figura = st.radio("Modalidad de Participación:", ["INDIVIDUAL", "UNION_TEMPORAL"])
    
    empresas_validas = [emp for emp in empresas if isinstance(emp, dict)]
    mapa_empresas = {e.get("alias_codigo", "S/N"): e for e in empresas_validas}
    
    if tipo_figura == "INDIVIDUAL":
        alias_sel = st.selectbox("Empresa (RUP):", list(mapa_empresas.keys()))
        empresas_elegidas = [alias_sel]
    else:
        empresas_elegidas = st.multiselect("Integrantes UT:", list(mapa_empresas.keys()), default=[list(mapa_empresas.keys())[0]] if mapa_empresas else [])
        
    nombre_proponente = st.text_input("Nombre de la Organización / UT:", value=f"UT {' + '.join(empresas_elegidas)}" if tipo_figura != "INDIVIDUAL" else empresas_elegidas[0] if empresas_elegidas else "")

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
    resultado_sim["nombre_proponente"] = nombre_proponente

    st.subheader("📊 Consolidado Financiero")
    df_comp = pd.DataFrame([{"Indicador": item["indicador"], "Exigido": item["exigido_fmt"], "Capacidad": item["consolidado_fmt"], "Estado": item["estado"]} for item in resultado_sim["comparativo_indicadores"]])
    st.dataframe(df_comp, use_container_width=True, hide_index=True)
    st.info(f"DICTAMEN GLOBAL: **{resultado_sim['estado_global']}**")
    
    # =========================================================
    # PUENTE INVISIBLE HACIA LA PESTAÑA DE DOCUMENTOS
    # =========================================================
    
    # 1. Enviamos los datos generales del proceso seleccionado
    st.session_state['doc_num_proceso'] = licitacion_actual.get('numero_proceso', '')
    st.session_state['doc_entidad'] = licitacion_actual.get('entidad', '')
    st.session_state['doc_objeto'] = licitacion_actual.get('objeto', '')
    st.session_state['doc_presupuesto'] = licitacion_actual.get('cuantia_presupuesto', 0)
    st.session_state['doc_modalidad'] = licitacion_actual.get('modalidad', '')

    # 2. Enviamos el cálculo financiero de la UT o empresa individual
    st.session_state['fin_nombre'] = nombre_proponente
    st.session_state['fin_global'] = resultado_sim['estado_global']
    
    st.session_state['fin_liq_exi'] = str(resultado_sim["comparativo_indicadores"][0]["exigido_fmt"])
    st.session_state['fin_liq_log'] = str(resultado_sim["comparativo_indicadores"][0]["consolidado_fmt"])
    st.session_state['fin_liq_est'] = resultado_sim["comparativo_indicadores"][0]["estado"]
    
    st.session_state['fin_end_exi'] = str(resultado_sim["comparativo_indicadores"][1]["exigido_fmt"])
    st.session_state['fin_end_log'] = str(resultado_sim["comparativo_indicadores"][1]["consolidado_fmt"])
    st.session_state['fin_end_est'] = resultado_sim["comparativo_indicadores"][1]["estado"]
    
    st.session_state['fin_cob_exi'] = str(resultado_sim["comparativo_indicadores"][2]["exigido_fmt"])
    st.session_state['fin_cob_log'] = str(resultado_sim["comparativo_indicadores"][2]["consolidado_fmt"])
    st.session_state['fin_cob_est'] = resultado_sim["comparativo_indicadores"][2]["estado"]

    st.divider()
    st.success("✅ **Cálculo completado.** Los datos del proceso y los resultados financieros han sido enviados a la memoria. Ve a la pestaña **'Documentos'** para generar el PDF de inmediato.")

if __name__ == "__main__":
    main()
