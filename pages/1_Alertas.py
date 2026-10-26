import streamlit as st
import pandas as pd
from datetime import date, timedelta

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

# Datos estructurados basados en tu operación local
datos = {
    "Expediente": ["FDL-CB-001-2026", "FDL-ENG-004-2026", "UT-CE-010-2026"],
    "Entidad": ["Alcaldía Local Ciudad Bolívar", "Alcaldía Local Engativá", "Secretaría de Desarrollo"],
    "Etapa Actual": ["Borrador", "Presentación Ofertas", "Evaluación"],
    "Cierre Observaciones": [date.today() + timedelta(days=1), date.today() - timedelta(days=3), date.today() - timedelta(days=15)],
    "Cierre de Ofertas": [date.today() + timedelta(days=10), date.today() + timedelta(days=2), date.today() - timedelta(days=5)],
}

df_alertas = pd.DataFrame(datos)

# Aplicar un estilo visual para destacar fechas cercanas
def resaltar_urgencia(val):
    if isinstance(val, date):
        diferencia = (val - date.today()).days
        if 0 <= diferencia <= 3:
            return 'background-color: #ffcccc; color: #990000; font-weight: bold' # Rojo (Urgente)
        elif 3 < diferencia <= 7:
            return 'background-color: #fff0b3; color: #997300' # Amarillo (Atención)
    return ''

st.dataframe(
    df_alertas.style.map(resaltar_urgencia, subset=['Cierre Observaciones', 'Cierre de Ofertas']),
    use_container_width=True,
    hide_index=True
)

st.info("💡 En la siguiente fase, conectaremos este tablero directamente con Supabase para que las fechas se actualicen automáticamente sin necesidad de Excel.")
