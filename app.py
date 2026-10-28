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
        except Exception: return None
    return None

def cargar_datos_base() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    cliente = obtener_cliente_supabase()
    if cliente:
        try:
            emp_res = cliente.table("empresas_proponentes").select("*").execute()
            lic_res = cliente.table("licitaciones_secop").select("*").order("numero_interno").execute()
            return (emp_res.data if isinstance(emp_res.data, list) else [], 
                    lic_res.data if isinstance(lic_res.data, list) else [])
        except Exception as e: st.sidebar.error(f"Error de lectura: {e}")
    return [], []

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
    return {"tipo_figura": tipo_figura, "comparativo_indicadores": comparativo, "estado_global": estado_global}

def limpiar_num(v):
    try: return float(v)
    except: return 0.0

# =====================================================================
# 3. INTERFAZ ALL-IN-ONE
# =====================================================================
def main():
    st.set_page_config(page_title="SECOP II ProMax", page_icon="⚖️", layout="wide")
    st.title("⚖️ Centro de Comando SECOP II — ASESOL / ZEKIA")

    empresas, licitaciones = cargar_datos_base()
    
    with st.sidebar:
        # MÓDULO 1: BUSCADOR Y CREADOR COMPLETO
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
                            try: st.session_state['api_cuantia'] = float(presupuesto_str)
                            except ValueError: st.session_state['api_cuantia'] = 0.0
                            url_cruda = datos.get('urlproceso', '')
                            st.session_state['api_link'] = url_cruda.get('url', '') if isinstance(url_cruda, dict) else url_cruda
                            st.success("✅ Datos extraídos.")
                        else: st.warning("⚠️ No encontrado en API.")
                    except: st.error("Error de conexión.")
            
            with st.form("form_guardar_proceso", clear_on_submit=True):
                st.caption("Diligencia las 12 secciones (Matriz Excel)")
                t1, t2, t3, t4 = st.tabs(["01-02", "03-05", "06-08", "09-12"])
                
                with t1:
                    st.write("**01 BÁSICOS**")
                    num_interno = st.number_input("Nº Interno", value=100)
                    num_proceso = st.text_input("Nº Proceso", value=exp_buscar)
                    entidad = st.text_input("Entidad", value=st.session_state.get('api_entidad', ''))
                    objeto = st.text_area("Objeto", value=st.session_state.get('api_objeto', ''))
                    modalidad = st.selectbox("Modalidad", ["Selección Abreviada", "Licitación Pública", "Mínima Cuantía", "Concurso de Méritos"])
                    cuantia = st.number_input("Presupuesto", value=st.session_state.get('api_cuantia', 0.0), step=1000000.0)
                    etapa = st.text_input("Etapa Actual", value="Presentación Ofertas")
                    estado = st.text_input("Revisión", value="ACTIVO")
                    lugar = st.text_input("Lugar Ejecución", value="Bogotá D.C.")
                    tiempo = st.text_input("Tiempo Ejecución", value="N/A")
                    st.write("**02 CRONOGRAMA**")
                    f_int = st.text_input("Manifestación Interés", value="N/A")
                    f_sor = st.text_input("Sorteo", value="N/A")
                    f_mip = st.text_input("Límite Mipyme", value="N/A")
                    f_obsp = st.text_input("Obs. Proyecto", value="N/A")
                    f_obsd = st.text_input("Obs. Definitivo", value="N/A")
                    f_ofe = st.text_input("Presentación Ofertas", value="N/A")

                with t2:
                    st.write("**03 UNSPSC | 04 TRIBUTOS**")
                    unspsc = st.text_input("Códigos Exigidos", value="N/A")
                    cant_u = st.number_input("Cantidad Mínima", value=0)
                    estampillas = st.text_area("Estampillas / Descuentos", value="N/A")
                    st.write("**05 FINANCIEROS (Pliego)**")
                    r_liq = st.number_input("Liquidez (>)", value=0.0, step=0.1)
                    r_end = st.number_input("Endeudamiento (<) %", value=0.0, step=0.1)
                    r_cob = st.number_input("Cobertura (>)", value=0.0, step=0.1)
                    r_cap = st.number_input("Capital Trabajo ($)", value=0.0, step=1000000.0)
                    r_rpat = st.number_input("Rent. Patrimonio (>)", value=0.0, step=0.1)
                    r_ract = st.number_input("Rent. Activo (>)", value=0.0, step=0.1)
                
                with t3:
                    st.write("**06 RESUMEN EJECUCIÓN**")
                    resumen = st.text_area("Resumen", value="N/A")
                    st.write("**07 EXPERIENCIA**")
                    eg_cont = st.text_input("Exp. General Contratos", value="N/A")
                    eg_desc = st.text_area("Desc. Exp. General", value="N/A")
                    ee_cont = st.text_input("Exp. Específica Contratos", value="N/A")
                    ee_desc = st.text_area("Desc. Exp. Específica", value="N/A")
                    reg_emp = st.text_area("Emprendimientos/Mujeres", value="N/A")
                    st.write("**08 EVALUACIÓN MÉTODOS**")
                    met_eco = st.text_area("Método Oferta Económica", value="N/A")
                    fac_tec = st.text_area("Factores Técnicos", value="N/A")

                with t4:
                    st.write("**09 PONDERACIÓN (Puntos)**")
                    pt_t = st.number_input("Técnica", value=0)
                    pt_e = st.number_input("Económica", value=0)
                    pt_i = st.number_input("Ind. Nacional", value=0)
                    pt_d = st.number_input("Discapacidad", value=0)
                    pt_m = st.number_input("Mipyme", value=0)
                    pt_mu = st.number_input("Mujeres", value=0)
                    pt_tot = st.number_input("Total Puntos", value=100)
                    st.write("**10 RESPONSABLE | 11 LINK**")
                    responsable = st.text_input("Responsable", value="Valerie Carvajal")
                    obs_fin = st.text_area("Observaciones Generales", value="N/A")
                    link_secop = st.text_input("Link Permanente", value=st.session_state.get('api_link', ''))
                    st.write("**12 GARANTÍAS (Pólizas)**")
                    pol_tipo = st.text_input("Póliza Exigida", value="N/A")
                    pol_ser = st.text_input("Seriedad Oferta", value="N/A")
                    pol_fec = st.text_input("Fecha Solicitud", value="N/A")
                    pol_vr = st.number_input("Vr. Póliza", value=0.0)
                    pol_est = st.text_input("Estado Póliza", value="Pendiente")

                if st.form_submit_button("💾 Guardar Proceso Completo", type="primary"):
                    if num_proceso and entidad:
                        nueva_lic = {
                            "numero_interno": num_interno, "fecha_registro": datetime.date.today().strftime("%Y-%m-%d"),
                            "numero_proceso": num_proceso, "entidad": entidad, "objeto": objeto, "modalidad": modalidad,
                            "cuantia_presupuesto": cuantia, "etapa_actual": etapa, "estado_revision": estado,
                            "lugar_ejecucion": lugar, "tiempo_ejecucion": tiempo,
                            "fecha_manifestacion_interes": f_int, "fecha_sorteo": f_sor, "fecha_limitacion_mipyme": f_mip,
                            "fecha_obs_prepliego": f_obsp, "fecha_obs_pliego_def": f_obsd, "fecha_presentacion_oferta": f_ofe,
                            "codigos_unspsc_req": unspsc, "cant_codigos_unspsc_req": cant_u, "estampillas": estampillas,
                            "req_liquidez_min": r_liq, "req_endeudamiento_max": r_end, "req_cobertura_intereses_min": r_cob,
                            "req_capital_trabajo_cop": r_cap, "req_rentabilidad_patrimonio_min": r_rpat, "req_rentabilidad_activo_min": r_ract,
                            "resumen_requerimientos_generales": resumen, "exp_general_contratos": eg_cont, "exp_general_descripcion": eg_desc,
                            "exp_especifica_contratos": ee_cont, "exp_especifica_descripcion": ee_desc, "regla_emprendimientos_mujeres_mipyme": reg_emp,
                            "metodos_oferta_economica": met_eco, "factores_tecnicos_ponderables": fac_tec,
                            "puntos_tecnica": pt_t, "puntos_economica": pt_e, "puntos_industria_nacional": pt_i, "puntos_discapacidad": pt_d,
                            "puntos_mipyme": pt_m, "puntos_mujeres": pt_mu, "total_puntos": pt_tot,
                            "responsable_proceso": responsable, "observaciones_recomendaciones": obs_fin, "link_secop": link_secop,
                            "poliza": pol_tipo, "poliza_seriedad_oferta": pol_ser, "fecha_solicitud_poliza": pol_fec, "vr_poliza": pol_vr, "estado_poliza": pol_est
                        }
                        try:
                            obtener_cliente_supabase().table("licitaciones_secop").insert(nueva_lic).execute()
                            for k in ['api_entidad', 'api_objeto', 'api_cuantia', 'api_link']:
                                if k in st.session_state: del st.session_state[k]
                            st.success("✅ ¡Proceso registrado!")
                            st.rerun()
                        except Exception as e: st.error(f"Error al guardar: {e}")

        # MÓDULO 2: REGISTRO MANUAL DE EMPRESAS
        with st.expander("🏢 Registrar Nueva Empresa (RUP)"):
            with st.form("form_nueva_empresa", clear_on_submit=True):
                alias = st.text_input("Alias (Ej. ZEKIA)")
                nit = st.text_input("NIT")
                ac = st.number_input("Act. Corriente", value=0.0)
                pc = st.number_input("Pas. Corriente", value=0.0)
                at = st.number_input("Act. Total", value=0.0)
                pt = st.number_input("Pas. Total", value=0.0)
                pat = st.number_input("Patrimonio", value=0.0)
                uo = st.number_input("Utilidad Op.", value=0.0)
                gi = st.number_input("Gastos Int.", value=0.0)
                ct = st.number_input("Cap. Trabajo", value=0.0)
                if st.form_submit_button("Guardar Empresa"):
                    if alias and nit:
                        try:
                            obtener_cliente_supabase().table("empresas_proponentes").insert({
                                "alias_codigo": alias, "nit": nit, "activo_corriente": ac, "pasivo_corriente": pc, "activo_total": at, 
                                "pasivo_total": pt, "patrimonio": pat, "utilidad_operacional": uo, "gastos_intereses": gi, "capital_trabajo": ct
                            }).execute()
                            st.success("✅ Empresa guardada.")
                            st.rerun()
                        except Exception as e: st.error(f"Error: {e}")

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
    else: empresas_elegidas = st.multiselect("Integrantes UT:", list(mapa_empresas.keys()), default=[list(mapa_empresas.keys())[0]] if mapa_empresas else [])
        
    nombre_proponente = st.text_input("Nombre Organización / UT:", value=f"UT {' + '.join(empresas_elegidas)}" if tipo_figura != "INDIVIDUAL" else (empresas_elegidas[0] if empresas_elegidas else ""))

    st.subheader(f"📋 {licitacion_actual.get('numero_proceso', '')} — {licitacion_actual.get('entidad', '')}")
    st.write(f"**Objeto:** {licitacion_actual.get('objeto', '')}")
    st.write(f"**Cuantía:** {formatear_moneda_cop(licitacion_actual.get('cuantia_presupuesto', 0))}")

    if not empresas_elegidas: return
    
    integrantes_simulacion = []
    cols_part = st.columns(len(empresas_elegidas))
    for idx, alias in enumerate(empresas_elegidas):
        emp_copy = dict(mapa_empresas[alias])
        with cols_part[idx]: pct = 100.0 if tipo_figura == "INDIVIDUAL" else st.number_input(f"% Participación {alias}:", min_value=1.0, max_value=99.0, value=round(100/len(empresas_elegidas),2))
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
    tipo_etiqueta = "UT/Consorcio" if tipo_figura != "INDIVIDUAL" else "Único"
    dic_simulacion = {"nombre_proponente": f"{nombre_proponente} ({tipo_etiqueta})", "estado_global": resultado_sim['estado_global'], "comparativo_indicadores": resultado_sim["comparativo_indicadores"]}

    try:
        pdf_bytes = generar_informe_ejecutivo_pdf(licitacion=licitacion_actual, simulacion=dic_simulacion, integrantes=[])
        st.download_button(
            label="⬇️ Descargar Informe Ejecutivo Corporativo (12 Secciones)",
            data=pdf_bytes, file_name=f"Informe_Completo_{licitacion_actual.get('numero_proceso', '0')}.pdf", mime="application/pdf", type="primary"
        )
    except Exception as e: st.error(f"Error al compilar el documento: {e}")

if __name__ == "__main__": main()
