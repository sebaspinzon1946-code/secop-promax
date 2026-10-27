import streamlit as st
import datetime
# Importamos tu función desde el archivo original
from generador_pdf import generar_informe_ejecutivo_pdf

st.title("📄 Emisión de Informes Ejecutivos")
st.caption("Generación automatizada de PDFs para evaluación técnica y financiera de ASESOL / ZEKIA")

st.divider()

with st.form("form_pdf"):
    st.subheader("Datos del Proceso")
    col1, col2 = st.columns(2)
    
    entidad = col1.text_input("Entidad Contratante")
    num_proceso = col2.text_input("Número de Proceso / Expediente")
    
    objeto = st.text_area("Objeto del Contrato")
    link_secop = st.text_input("Enlace directo a SECOP II (URL)")
    
    col3, col4 = st.columns(2)
    presupuesto = col3.number_input("Presupuesto Oficial (COP)", min_value=0, value=0, step=1000000)
    modalidad = col4.selectbox("Modalidad", ["Selección Abreviada", "Licitación Pública", "Mínima Cuantía", "Concurso de Méritos"])
    
    st.subheader("Datos del Proponente (Unión Temporal)")
    col5, col6 = st.columns(2)
    nombre_proponente = col5.text_input("Nombre de la Empresa o UT", value="ZEKIA S.A.S.")
    estado_global = col6.selectbox("Dictamen Financiero Global", ["CUMPLE", "NO CUMPLE", "REVISAR"])
    
    btn_generar = st.form_submit_button("Generar Borrador PDF", type="primary")

if btn_generar:
    # 1. Empaquetamos los datos en los diccionarios que exige tu script
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
    
    # 2. Ejecutamos tu motor ReportLab (en memoria)
    try:
        pdf_bytes = generar_informe_ejecutivo_pdf(
            licitacion=dic_licitacion,
            simulacion=dic_simulacion,
            integrantes=[]
        )
        
        st.success("✅ Documento generado con éxito.")
        
        # 3. Botón de descarga nativo
        st.download_button(
            label="⬇️ Descargar Informe Ejecutivo (PDF)",
            data=pdf_bytes,
            file_name=f"Informe_{num_proceso}.pdf",
            mime="application/pdf",
            type="primary"
        )
    except Exception as e:
        st.error(f"Error al compilar el documento: {e}")
