import streamlit as st
import pandas as pd
from datetime import date, timedelta
from supabase import create_client

st.set_page_config(page_title="Alertas SECOP II", page_icon="📅", layout="wide")

st.title("📅 Panel de Términos y Vencimientos")
st.caption("Control automatizado de plazos para licitaciones de ASESOL y clientes ZEKIA")

# ==========================================
# 1. MÉTRICAS DE URGENCIA
# ==========================================
st.subheader("Resumen de Tareas")
kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Procesos Activos", "3")
kpi2.metric("Vencimientos esta semana", "2", "-1 respecto a ayer", delta_color="inverse")
kpi3.metric("Respuestas a Observaciones", "1", "Urgente", delta_color="off")

st.divider()

# ==========================================
# 2. TABLERO DE CONTROL (MOCKUP INICIAL)
# ==========================================
st.subheader("🚨 Cronograma de Procesos Actuales")

@st.cache_resource
def conectar_bd():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = conectar_bd()

try:
    # Cambia "procesos_secop" por el nombre exacto de tu tabla en Supabase
    respuesta = supabase.table("procesos_secop").select("*").execute()
    df_alertas = pd.DataFrame(respuesta.data)
    
    if not df_alertas.empty:
        df_alertas['Cierre Observaciones'] = pd.to_datetime(df_alertas['Cierre Observaciones']).dt.date
        df_alertas['Cierre de Ofertas'] = pd.to_datetime(df_alertas['Cierre de Ofertas']).dt.date
        
        st.dataframe(
            df_alertas.style.map(resaltar_urgencia, subset=['Cierre Observaciones', 'Cierre de Ofertas']),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Aún no hay procesos registrados en la base de datos.")
except Exception as e:
    st.error(f"Error de conexión: {e}")

st.divider()

# ==========================================
# 3. FORMULARIO DE INGRESO DE PROCESOS
# ==========================================
with st.expander("➕ Agregar nueva licitación al sistema"):
    with st.form("form_nuevo_proceso", clear_on_submit=True):
        st.markdown("### Datos del proceso SECOP II")
        
        col1, col2 = st.columns(2)
        expediente = col1.text_input("Número de Expediente (Ej. FDL-CB-001-2026)")
        entidad = col2.text_input("Entidad Contratante")
        
        col3, col4, col5 = st.columns(3)
        etapa = col3.selectbox("Etapa Actual", ["Borrador", "Presentación Ofertas", "Evaluación", "Adjudicado"])
        cierre_obs = col4.date_input("Fecha límite de Observaciones")
        cierre_ofertas = col5.date_input("Fecha de Cierre de Ofertas")
        
        btn_guardar = st.form_submit_button("Guardar en Base de Datos", type="primary")
        
        if btn_guardar:
            if expediente.strip() == "" or entidad.strip() == "":
                st.warning("⚠️ Debes ingresar al menos el Expediente y la Entidad para guardar.")
            else:
                nuevo_registro = {
                    "Expediente": expediente,
                    "Entidad": entidad,
                    "Etapa Actual": etapa,
                    # Convertimos las fechas a texto (formato YYYY-MM-DD) para que Supabase las reciba sin error
                    "Cierre Observaciones": str(cierre_obs),
                    "Cierre de Ofertas": str(cierre_ofertas)
                }
                
                try:
                    # Inserción en la base de datos
                    supabase.table("procesos_secop").insert(nuevo_registro).execute()
                    st.success(f"✅ ¡El proceso {expediente} se registró correctamente!")
                    # Recarga la página automáticamente para actualizar la tabla de arriba
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al guardar en Supabase: {e}")
