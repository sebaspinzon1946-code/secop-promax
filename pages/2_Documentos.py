import streamlit as st
import datetime
import requests
# Importamos tu función desde el archivo original
from generador_pdf import generar_informe_ejecutivo_pdf

st.title("📄 Emisión de Informes Ejecutivos")
st.caption("Generación automatizada de PDFs para evaluación técnica y financiera de ASESOL / ZEKIA")

st.divider()

# ==========================================
# 1. BUSCADOR AUTOMÁTICO SECOP II
# ==========================================
st.subheader("🔍 Autocompletado desde SECOP II")
col_s1, col_s2 = st.columns([3, 1])
exp_input = col_s1.text_input("Ingresa el Número de Expediente para extraer datos")

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
                    # Guardamos los datos en memoria
                    st.session_state['doc_entidad'] = datos.get('entidad', '')
                    st.session_state['doc_objeto'] = datos.get('detalle_del_objeto_a_contratar', '')
                    st.session_state['doc_presupuesto'] = int(datos.get('cuantia_proceso', 0))
                    
                    # Extraer el enlace permanente oficial de SECOP
                    url_cruda = datos.get('urlproceso', '')
                    if isinstance(url_cruda, dict):
                        st.session_state['doc_link'] = url_cruda.get('url', '')
                    else:
                        st.session_state['doc_link'] = url_cruda
                        
                    st.success("✅ Datos extraídos correctamente.")
                else:
                    st.warning("⚠️ Proceso no encontrado.")
            else:
                st.error("Rechazo de conexión por parte del Estado.")
        except Exception as e:
            st.error(f"Falla de conexión: {e}")

# ==========================================
# 2. FORMULARIO DEL DOCUMENTO
# ==========================================
with st.form("form_pdf"):
    st.subheader("Datos del Proceso")
    col1, col2 = st.columns(2)
    
    num_proceso = col2.text_input("Número de Proceso / Expediente", value=exp_input)
    entidad = col1.text_input("Entidad Contratante", value=st.session_state.get('doc_entidad', ''))
    
    objeto = st.text_area("Objeto del Contrato", value=st.session_state.get('doc_objeto', ''))
    link_secop = st.text_input("Enlace permanente oficial (URL)", value=st.session_state.get('doc_link', ''))
    
    col3, col4 = st.columns(2)
    presupuesto = col3.number_input("Presupuesto Oficial (COP)", min_value=0, value=st.session_state.get('doc_presupuesto', 0), step=1000000)
    modalidad = col4.selectbox("Modalidad", ["Selección Abreviada", "Licitación Pública", "Mínima Cuantía", "Concurso de Méritos"])
    
    st.subheader("Datos del Proponente (Unión Temporal)")
    col5, col6 = st.columns(2)
    nombre_proponente = col5.text_input("Nombre de la Empresa o UT", value="ZEKIA S.A.S.")
    estado_global = col6.selectbox("Dictamen Financiero Global", ["CUMPLE", "NO CUMPLE", "REVISAR"])
    
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
    
    dic_simulacion = {
        "nombre_proponente": nombre_proponente,
        "estado_global": estado_global,
        "comparativo_indicadores": [] 
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
