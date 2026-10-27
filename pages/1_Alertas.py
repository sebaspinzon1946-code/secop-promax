import streamlit as st
import pandas as pd
import requests
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

st.divider()

# ==========================================
# 3. FORMULARIO AUTOMATIZADO CON API SECOP II
# ==========================================
with st.expander("➕ Agregar nueva licitación al sistema"):
    st.markdown("### 🔍 Búsqueda Inteligente")
    st.caption("Busca directamente en Datos Abiertos de Colombia ingresando el número de proceso.")
    
    col_b1, col_b2 = st.columns([3, 1])
    exp_input = col_b1.text_input("Número de Expediente (Ej. FDL-CB-001-2026)")
    
    if col_b2.button("Buscar en SECOP II", type="secondary"):
        if exp_input:
            # URL oficial de la API de SECOP II (Datos Abiertos)
            url = f"https://www.datos.gov.co/resource/jbjy-vk9h.json?referencia_del_proceso={exp_input.strip()}"
            try:
                # Disfrazar la petición como navegador para evitar el bloqueo del Estado
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                respuesta = requests.get(url, headers=headers, timeout=10)
                
                if respuesta.status_code == 200:
                    datos_json = respuesta.json()
                    if len(datos_json) > 0:
                        datos = datos_json[0]
                        st.session_state['entidad_secop'] = datos.get('entidad', '')
                        st.success(f"✅ Proceso encontrado: {datos.get('entidad', '')}")
                    else:
                        st.warning("⚠️ No se encontró el proceso en SECOP II. Revisa el número de expediente.")
                else:
                    st.error(f"El portal del Estado rechazó la conexión (Error {respuesta.status_code}).")
            except Exception as e:
                # Ahora imprimiremos el error exacto si vuelve a fallar
                st.error(f"Falla técnica de conexión: {e}")

    st.markdown("### Datos del Proceso")
    with st.form("form_nuevo_proceso", clear_on_submit=True):
        col1, col2 = st.columns(2)
        expediente = col1.text_input("Número de Expediente", value=exp_input)
        
        # Leemos la entidad si fue encontrada por la API, si no, queda en blanco
        entidad_previa = st.session_state.get('entidad_secop', '')
        entidad = col2.text_input("Entidad Contratante", value=entidad_previa)
        
        col3, col4, col5 = st.columns(3)
        etapa = col3.selectbox("Etapa Actual", ["Borrador", "Presentación Ofertas", "Evaluación", "Adjudicado"])
        cierre_obs = col4.date_input("Fecha límite de Observaciones")
        cierre_ofertas = col5.date_input("Fecha de Cierre de Ofertas")
        
        btn_guardar = st.form_submit_button("Guardar en Base de Datos", type="primary")
        
        if btn_guardar:
            if expediente.strip() == "" or entidad.strip() == "":
                st.warning("⚠️ Debes ingresar al menos el Expediente y la Entidad.")
            else:
                nuevo_registro = {
                    "Expediente": expediente,
                    "Entidad": entidad,
                    "Etapa Actual": etapa,
                    "Cierre Observaciones": str(cierre_obs),
                    "Cierre de Ofertas": str(cierre_ofertas)
                }
                try:
                    supabase.table("procesos_secop").insert(nuevo_registro).execute()
                    # Limpiamos la memoria temporal tras guardar con éxito
                    if 'entidad_secop' in st.session_state: 
                        del st.session_state['entidad_secop']
                    st.success(f"✅ ¡El proceso {expediente} se registró correctamente!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al guardar en Supabase: {e}")
