"""
Módulo Único Definitivo: Centro de Comando SECOP II — Fase 3 (Storage PDF + Topes SMMLV + Escáner Económico)
"""

import io
import os
import re
import datetime
from dotenv import load_dotenv
load_dotenv()

import pandas as pd
import streamlit as st
import requests
from typing import Dict, Any, List, Optional, Tuple

from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from generador_pdf import generar_informe_ejecutivo_pdf, formatear_moneda_cop, formatear_indicador
from escaner_economico import renderizar_modulo_escaner

# =====================================================================
# LISTAS OFICIALES Y CATÁLOGOS NORMATIVOS
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
LISTA_INICIATIVAS = ["No aplica", "Sí - Asociado a Iniciativas Ciudadanas / Presupuestos Participativos", "Por verificar en Anexo Técnico"]

LISTA_REQ_ESPECIALES = [
    "PULEP (Portal Único de Espectáculos Públicos)", "RNT (Registro Nacional de Turismo)",
    "Certificado Operador Logístico", "SUGA / Permisos IDIGER", "Certificado de Residencia / Arraigo Local",
    "Certificado de Víctimas del Conflicto", "Certificado de Persona Cuidadora", "Certificado Población Afrodescendiente / Raizal",
    "Medio de Comunicación Certificado por IDPAC", "Certificado de Exclusividad Comercial", "Certificado de Derechos de Autor",
    "Certificado y/o Experiencia Docente", "Certificado Inscripción Población LGBTI", "Certificación como Institución Educativa",
    "Acuerdo o Alianza con Empresa de Transporte Habilitada", "Contrato de Arrendamiento, Comodato o Convenio de Sede"
]

MAPA_PROFESIONES_TP = {
    "Derecho / Abogado(a)": "SÍ EXIGE Tarjeta Profesional (CSJ) + Vigencia",
    "Contaduría Pública": "SÍ EXIGE Tarjeta Profesional (JCC) + Antecedentes",
    "Ingeniería (Civil, Industrial, Sistemas, Ambiental, etc.)": "SÍ EXIGE Matrícula Profesional (COPNIA) + Vigencia",
    "Arquitectura y Profesiones Auxiliares": "SÍ EXIGE Matrícula Profesional (CPNAA) + Vigencia",
    "Administración de Empresas / Negocios / Pública": "SÍ EXIGE Tarjeta Profesional (CPAE)",
    "Economía": "SÍ EXIGE Matrícula Profesional (CONALPE)",
    "Psicología": "SÍ EXIGE Tarjeta Profesional (COLPSIC)",
    "Trabajo Social": "SÍ EXIGE Registro / Tarjeta Profesional (CONETS)",
    "Áreas de la Salud (Medicina, Enfermería, Fisioterapia, Nutrición)": "SÍ EXIGE Tarjeta Profesional (RETHUS)",
    "Sociología / Antropología / Ciencia Política": "NO EXIGE Tarjeta Profesional (Solo Diploma y Acta)",
    "Comunicación Social / Periodismo": "NO EXIGE Tarjeta Profesional (Sentencia C-087/98)",
    "Artes Plásticas, Escénicas, Música o Literatura": "NO EXIGE Tarjeta Profesional (Solo Diploma / Experiencia Artística)",
    "Licenciaturas / Pedagogía / Educación": "NO EXIGE Tarjeta Profesional (Resol. Escalafón si aplica)",
    "Técnico / Tecnólogo / Bachiller / Operario Logístico": "NO EXIGE Tarjeta Profesional (Salvo técnicos electricistas CONTE)"
}

# =====================================================================
# 1. CONEXIÓN A SUPABASE, STORAGE Y UTILIDADES DE FORMATO
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

def autenticar_usuario(username, password):
    cliente = obtener_cliente_supabase()
    if cliente:
        try:
            res = cliente.table("usuarios_plataforma").select("*").eq("username", username).eq("password", password).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
        except Exception:
            return None
    return None

def cargar_datos_base() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    cliente = obtener_cliente_supabase()
    if cliente:
        try:
            emp_res = cliente.table("empresas_proponentes").select("*").execute()
            lic_res = cliente.table("licitaciones_secop").select("*").order("numero_interno").execute()
            exp_res = cliente.table("experiencias_rup").select("*").execute()
            return (emp_res.data if isinstance(emp_res.data, list) else [],
                    lic_res.data if isinstance(lic_res.data, list) else [],
                    exp_res.data if isinstance(exp_res.data, list) else [])
        except Exception as e:
            st.sidebar.error(f"Error de lectura: {e}")
    return [], [], []

def subir_certificacion_pdf(archivo_subido, alias_empresa: str, num_contrato: str) -> str:
    cliente = obtener_cliente_supabase()
    if not cliente or archivo_subido is None:
        return ""
    try:
        nombre_limpio = re.sub(r'[^a-zA-Z0-9_-]', '_', f"{alias_empresa}_{num_contrato}")
        ruta_destino = f"{alias_empresa.upper()}/{nombre_limpio}_{int(datetime.datetime.now().timestamp())}.pdf"
        cliente.storage.from_("certificaciones_rup").upload(
            path=ruta_destino,
            file=archivo_subido.getvalue(),
            file_options={"content-type": "application/pdf", "upsert": "true"}
        )
        return cliente.storage.from_("certificaciones_rup").get_public_url(ruta_destino)
    except Exception as e:
        st.error(f"Error al subir PDF: {e}")
        return ""

def guardar_licitacion_seguro(payload: Dict[str, Any], modo: str = "insert", num_interno: Optional[int] = None):
    cliente = obtener_cliente_supabase()
    if not cliente:
        raise Exception("No hay conexión con Supabase.")
    try:
        if modo == "insert":
            cliente.table("licitaciones_secop").insert(payload).execute()
        else:
