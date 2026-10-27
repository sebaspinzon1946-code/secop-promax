import streamlit as st
import datetime
import requests
from generador_pdf import generar_informe_ejecutivo_pdf

st.title("📄 Emisión de Informes Ejecutivos")
st.caption("Generación automatizada de PDFs para evaluación técnica y financiera")
st.divider()

# ==========================================
# 1. BUSCADOR AUTOMÁTICO SECOP II (Respaldo)
# ==========================================
st.subheader("🔍 Autocompletado desde SECOP II (Respaldo)")
st.caption("Si vienes desde el Evaluador Financiero, los datos ya están cargados. Si no, puedes buscar aquí.")
col_s1, col_s2 = st.columns([3, 1])

# Lee el número de proceso que envía app.py, si no hay nada, lo deja en blanco
exp_input = col_s1.text_input("Ingresa el Número de Expediente para extraer datos", value=st.session_state.get('doc_num_proceso', ''))

if col_s2.button("Buscar Proceso", type="secondary"):
    if exp_input:
        url = "https://www.datos.gov.co/resource/p6dx-8zbt.json"
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            parametros = {"referencia_del_proceso": exp_input.strip()}
            respuesta = requests.get(url, headers=headers, params=parametros, timeout=10)
            
            if respuesta.status_code == 200:
                datos_json = respuesta.json()
                if len(datos_json) > 0:
                    datos = datos_json[0]
                    st.session_state['doc_entidad'] = datos.get('entidad', '')
                    st.session_state['doc_objeto'] = datos.get('detalle_del_objeto_a_contratar', '')
                    st.session_state['doc_presupuesto'] = int(datos.get('cuantia_proceso', 0))
                    
                    url_cruda = datos.get('urlproceso', '')
                    st.session_state['doc_link'] = url_cruda.get('url', '') if isinstance(url_cruda, dict) else url_cruda
                    st.success("✅ Datos extraídos correctamente.")
                else:
                    st.warning("⚠️ Proceso no encontrado.")
            else:
                st.error("Rechazo de conexión por parte del Estado.")
        except Exception as e:
            st.error(f"Falla de conexión: {e}")

# ==========================================
# 2. FORMULARIO DEL DOCUMENTO Y FINANZAS
# ==========================================
with st.form("form_pdf"):
    st.subheader("Datos del Proceso")
    col1, col2 = st.columns(2)
    
    num_proceso = col2.text_input("Número de Expediente", value=st.session_state.get('doc_num_proceso', exp_input))
    entidad = col1.text_input("Entidad Contratante", value=st.session_state.get('doc_entidad', ''))
    
    objeto = st.text_area("Objeto del Contrato", value=st.session_state.get('doc_objeto', ''))
    link_secop = st.text_input("Enlace permanente oficial (URL)", value=st.session_state.get('doc_link', ''))
    
    col3, col4 = st.columns(2)
    presupuesto = col3.number_input("Presupuesto Oficial (COP)", min_value=0, value=st.session_state.get('doc_presupuesto', 0), step=1000000)
    
    # Manejo inteligente de la modalidad desde la memoria
    lista_modalidades = ["Selección Abreviada", "Licitación Pública", "Mínima Cuantía", "Concurso de Méritos"]
    mod_memoria = st.session_state.get('doc_modalidad', 'Selección Abreviada')
    index_mod = lista_modalidades.index(mod_memoria) if mod_memoria in lista_modalidades else 0
    modalidad = col4.selectbox("Modalidad", lista_modalidades, index=index_mod)
    
    st.divider()
    st.subheader("Datos del Proponente y Resultados Financieros")
    
    # Selector de modalidad de participación
    tipo_proponente = st.radio("Naturaleza del Proponente", ["Proponente Único", "Plural (Unión Temporal / Consorcio)"], horizontal=True)
    nombre_proponente = st.text_input("Nombre de la Empresa o UT", value=st.session_state.get('fin_nombre', "ZEKIA S.A.S."))
    
    st.caption("Los siguientes valores han sido inyectados desde el Evaluador Financiero (o puedes digitarlos manualmente):")
    
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        st.markdown("**Liquidez (>=)**")
        liq_exi = st.text_input("Exigido", value=st.session_state.get('fin_liq_exi', "1.50"), key="l_e")
        liq_log = st.text_input("Logrado", value=st.session_state.get('fin_liq_log', "0.00"), key="l_l")
        liq_est = st.selectbox("Estado", ["CUMPLE", "NO CUMPLE"], key="l_s", index=0 if st.session_state.get('fin_liq_est') == "CUMPLE" else 1)

    with col_f2:
        st.markdown("**Endeudamiento (<=)**")
        end_exi = st.text_input("Exigido", value=st.session_state.get('fin_end_exi', "0.70"), key="e_e")
        end_log = st.text_input("Logrado", value=st.session_state.get('fin_end_log', "0.00"), key="e_l")
        end_est = st.selectbox("Estado", ["CUMPLE", "NO CUMPLE"], key="e_s", index=0 if st.session_state.get('fin_end_est') == "CUMPLE" else 1)

    with col_f3:
        st.markdown("**Razón Cobertura (>=)**")
        cob_exi = st.text_input("Exigido", value=st.session_state.get('fin_cob_exi', "3.00"), key="c_e")
        cob_log = st.text_input("Logrado", value=st.session_state.get('fin_cob_log', "0.00"), key="c_l")
        cob_est = st.selectbox("Estado", ["CUMPLE", "NO CUMPLE"], key="c_s", index=0 if st.session_state.get('fin_cob_est') == "CUMPLE" else 1)

    estado_global = st.selectbox("Dictamen Financiero Global", ["CUMPLE", "NO CUMPLE", "REVISAR"], index=0 if st.session_state.get('fin_global') == "CUMPLE" else 2)
    
    btn_generar = st.form_submit_button("Generar Borrador PDF", type="primary")

if btn_generar:
    dic_licitacion = {
        "numero_interno": num_proceso,
        "numero_proceso": num_proceso,
        "entidad": entidad,
        "objeto": objeto,
        "cuantia_presupuesto": presupuesto,
        "modalidad": modalidad,
        "fecha_registro": datetime.date.today().strftime("%d/%m/%Y"),
        "link_secop": link_secop
    }
    
    # Armamos la estructura exacta que pide el bloque "04 COMPARATIVO FINANCIERO" de tu ReportLab
    indicadores = [
        {"indicador": "Índice de Liquidez", "regla": ">=", "exigido_fmt": liq_exi, "consolidado_fmt": liq_log, "estado": liq_est},
        {"indicador": "Índice de Endeudamiento", "regla": "<=", "exigido_fmt": end_exi, "consolidado_fmt": end_log, "estado": end_est},
        {"indicador": "Razón de Cobertura de Intereses", "regla": ">=", "exigido_fmt": cob_exi, "consolidado_fmt": cob_log, "estado": cob_est}
    ]
    
    # Ajustamos el nombre para que el PDF especifique si es único o unión temporal
    nombre_formateado = f"{nombre_proponente} ({tipo_proponente})"
    
    dic_simulacion = {
        "nombre_proponente": nombre_formateado, 
        "estado_global": estado_global,
        "comparativo_indicadores": indicadores
    }
    
    try:
        pdf_bytes = generar_informe_ejecutivo_pdf(
            licitacion=dic_licitacion,
            simulacion=dic_simulacion,
            integrantes=[] 
        )
        
        st.success("✅ Documento generado con éxito.")
        st.download_button(
            label="⬇️ Descargar Informe Ejecutivo (PDF)",
            data=pdf_bytes,
            file_name=f"Informe_{num_proceso}.pdf",
            mime="application/pdf",
            type="primary"
        )
    except Exception as e:
        st.error(f"Error al compilar el documento: {e}")
