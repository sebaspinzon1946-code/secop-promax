"""
Módulo: Escáner de Formatos de Oferta Económica (SECOP II)
Cuenta ítems aproximados y detecta filas NO OFERTABLES, inmodificables o de valor fijo.
"""

import io
import re
import openpyxl
import pandas as pd
import streamlit as st
from typing import Dict, Any, List

PALABRAS_NO_OFERTABLE = [
    "no ofertable", "no ofertar", "inmodificable", "no modificar",
    "valor fijo", "precio fijo", "tarifa fija", "monto fijo",
    "no editable", "fijo por la entidad", "valor asignado",
    "no aplica oferta", "bolsa", "reembolsable", "provisional"
]

PALABRAS_EXCLUIR_CONTEO = [
    "subtotal", "total general", "gran total", "valor total",
    "iva", "aiu", "administracion", "imprevistos", "utilidad",
    "firma", "representante legal", "proponente", "nit", "observaciones"
]

def es_fila_item_valido(valores_fila: List[Any]) -> bool:
    """Determina heurísticamente si una fila corresponde a un ítem ofertable/técnico."""
    textos = [str(v).strip() for v in valores_fila if v is not None and str(v).strip() != ""]
    if len(textos) < 2:
        return False

    texto_completo = " ".join(textos).lower()
    # Descartar encabezados típicos o filas de totales
    if any(exc in texto_completo for exc in PALABRAS_EXCLUIR_CONTEO):
        return False

    # Debe tener al menos un texto descriptivo largo (> 8 caracteres) y al menos un número (ítem, cantidad o valor)
    tiene_descripcion = any(len(t) >= 8 and not re.fullmatch(r'[\d\.,\$\s%-]+', t) for t in textos)
    tiene_numero = any(isinstance(v, (int, float)) or re.search(r'\d', str(v)) for v in valores_fila if v is not None)
    return tiene_descripcion and tiene_numero

def analizar_excel_oferta_economica(archivo_bytes: bytes) -> Dict[str, Any]:
    wb = openpyxl.load_workbook(io.BytesIO(archivo_bytes), data_only=False)
    resumen_hojas = []
    items_no_ofertables = []
    total_items_global = 0

    for nombre_hoja in wb.sheetnames:
        ws = wb[nombre_hoja]
        hoja_protegida = ws.protection.sheet
        items_hoja = 0
        no_ofertables_hoja = 0

        for idx_fila, fila in enumerate(ws.iter_rows(values_only=False), start=1):
            valores = [celda.value for celda in fila]
            if not any(v is not None and str(v).strip() != "" for v in valores):
                continue

            texto_fila = " ".join([str(v).strip() for v in valores if v is not None]).lower()

            # 1. Conteo aproximado de ítems
            if es_fila_item_valido(valores):
                items_hoja += 1

            # 2. Detección de ítems NO OFERTABLES / INMODIFICABLES
            motivos = []
            for kw in PALABRAS_NO_OFERTABLE:
                if kw in texto_fila:
                    motivos.append(f"Texto: '{kw}'")

            # Si la hoja está protegida, revisar si todas las celdas numéricas de la fila están bloqueadas
            if hoja_protegida and es_fila_item_valido(valores):
                celdas_con_valor = [c for c in fila if c.value is not None]
                if celdas_con_valor and all(c.protection.locked for c in celdas_con_valor):
                    motivos.append("Fila bloqueada en hoja protegida")

            if motivos:
                no_ofertables_hoja += 1
                # Extraer un resumen legible de la fila (primeras 4 celdas con contenido)
                muestra = " | ".join([str(v).strip()[:60] for v in valores if v is not None and str(v).strip() != ""][:4])
                items_no_ofertables.append({
                    "Hoja": nombre_hoja,
                    "Fila": idx_fila,
                    "Motivo de Alerta": "; ".join(dict.fromkeys(motivos)),
                    "Contenido Detectado": muestra
                })

        total_items_global += items_hoja
        resumen_hojas.append({
            "Hoja": nombre_hoja,
            "Protegida": "🔒 Sí" if hoja_protegida else "🔓 No",
            "Ítems Aprox.": items_hoja,
            "Alertas No Ofertables": no_ofertables_hoja
        })

    return {
        "total_hojas": len(wb.sheetnames),
        "total_items_aprox": total_items_global,
        "total_no_ofertables": len(items_no_ofertables),
        "resumen_hojas": resumen_hojas,
        "items_no_ofertables": items_no_ofertables
    }

def renderizar_modulo_escaner():
    st.header("🧾 Escáner de Formato de Oferta Económica (Excel)")
    st.write("Sube el anexo económico de SECOP II (`.xlsx` o `.xlsm`) para contar automáticamente la cantidad aproximada de ítems y detectar filas **NO OFERTABLES / inmodificables**.")

    archivo = st.file_uploader("Arrastra aquí el Excel de Oferta Económica:", type=["xlsx", "xlsm"], key="uploader_eco")

    if archivo is not None:
        with st.spinner("Analizando hojas, filas y protecciones del Excel..."):
            try:
                resultado = analizar_excel_oferta_economica(archivo.getvalue())

                k1, k2, k3 = st.columns(3)
                k1.metric("Hojas Analizadas", resultado["total_hojas"])
                k2.metric("Ítems Aproximados", resultado["total_items_aprox"])
                k3.metric("Alertas No Ofertables / Fijas", resultado["total_no_ofertables"])

                st.subheader("📑 Resumen por Hoja")
                st.dataframe(pd.DataFrame(resultado["resumen_hojas"]), use_container_width=True, hide_index=True)

                st.subheader("🚨 Ítems NO OFERTABLES / Inmodificables Detectados")
                if resultado["items_no_ofertables"]:
                    st.warning("Revisa estas filas antes de formular la oferta económica para evitar rechazos por alterar valores fijos:")
                    st.dataframe(pd.DataFrame(resultado["items_no_ofertables"]), use_container_width=True, hide_index=True)
                else:
                    st.success("✅ No se detectaron textos de 'No ofertable / Inmodificable' ni filas completamente bloqueadas.")
            except Exception as e:
                st.error(f"No se pudo leer el archivo Excel: {e}")
