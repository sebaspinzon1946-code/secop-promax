"""
Módulo 3: Generación Automática de Informes PDF Ejecutivos (SECOP II)
Diseño de 9 Secciones usando ReportLab (Nativo para Windows/Cualquier SO)
"""

from __future__ import annotations
import io
import datetime
from typing import Dict, Any, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

def formatear_moneda_cop(valor: Optional[float]) -> str:
    if valor is None: return "N/A"
    try: return f"$ {float(valor):,.0f}".replace(",", ".")
    except (ValueError, TypeError): return str(valor)

def formatear_indicador(valor: Optional[float], es_porcentaje: bool = False, indeterminado: bool = False) -> str:
    if indeterminado: return "INDETERMINADO"
    if valor is None: return "N/A"
    try:
        val = float(valor)
        if es_porcentaje: return f"{val * 100:.2f}%"
        return f"{val:,.2f}"
    except (ValueError, TypeError): return str(valor)

def generar_informe_ejecutivo_pdf(
    licitacion: Dict[str, Any],
    simulacion: Dict[str, Any],
    integrantes: List[Dict[str, Any]],
    output_path: Optional[str] = None
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=12*mm, rightMargin=12*mm, topMargin=12*mm, bottomMargin=12*mm
    )

    styles = getSampleStyleSheet()
    
    # Estilos de texto
    title_style = ParagraphStyle('Title', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, alignment=1)
    subtitle_style = ParagraphStyle('SubTitle', parent=styles['Normal'], fontName='Helvetica', fontSize=8, alignment=1, spaceAfter=10)
    sec_title_style = ParagraphStyle('SecTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8.5, backColor=colors.HexColor("#d9e1f2"), borderPadding=4)
    cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontName='Helvetica', fontSize=7.5, leading=9)
    cell_bold = ParagraphStyle('CellBold', parent=cell_style, fontName='Helvetica-Bold')
    cell_center = ParagraphStyle('CellCenter', parent=cell_style, alignment=1)
    cell_center_bold = ParagraphStyle('CellCenterBold', parent=cell_bold, alignment=1)

    story = []

    # Encabezado
    story.append(Paragraph("INFORME EJECUTIVO | ANÁLISIS DE VIABILIDAD SECOP", title_style))
    story.append(Paragraph("Reporte individual actualización automática al cambiar el N.º de registro información para evaluación técnica y comercial", subtitle_style))

    # Colores base
    gray_bg = colors.HexColor("#f2f2f2")
    border_color = colors.black

    def make_table(data, colWidths, style_cmds):
        t = Table(data, colWidths=colWidths)
        t.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, border_color),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ] + style_cmds))
        return t

    # Metadatos superiores
    fecha_hoy = datetime.date.today().strftime("%d/%m/%Y")
    data_meta = [
        [Paragraph("CÓDIGO INTERNO PROCESO", cell_bold), Paragraph(f"<font color='red'>{licitacion.get('numero_interno','')}</font>", ParagraphStyle('RedBig', parent=cell_center_bold, fontSize=11)),
         Paragraph("FECHA REGISTRO", cell_bold), Paragraph(licitacion.get("fecha_registro", "19/10/2026"), cell_center),
         Paragraph("FECHA DEL INFORME", cell_bold), Paragraph(fecha_hoy, cell_center)],
        [Paragraph("ENTIDAD", cell_bold), Paragraph(licitacion.get("entidad", ""), cell_style), "", "", "", ""],
        [Paragraph("N. PROCESO", cell_bold), Paragraph(licitacion.get("numero_proceso", ""), cell_style), "", "", Paragraph("MODALIDAD", cell_bold), Paragraph(licitacion.get("modalidad", ""), cell_center)],
        [Paragraph("OBJETO", cell_bold), Paragraph(licitacion.get("objeto", ""), cell_style), "", "", "", ""],
        [Paragraph("ORGANIZACIÓN:", cell_bold), Paragraph(simulacion.get("nombre_proponente", ""), cell_bold), "", "", Paragraph("RESPONSABLE DEL PROCESO", cell_bold), Paragraph(licitacion.get("responsable_proceso", "Valerie Carvajal"), cell_center)]
    ]
    t_meta = make_table(data_meta, [40*mm, 20*mm, 30*mm, 36*mm, 35*mm, 25*mm], [
        ('BACKGROUND', (0,0), (0,-1), gray_bg),
        ('BACKGROUND', (2,0), (2,0), gray_bg),
        ('BACKGROUND', (4,0), (4,0), gray_bg),
        ('BACKGROUND', (4,2), (4,2), gray_bg),
        ('BACKGROUND', (4,4), (4,4), gray_bg),
        ('SPAN', (1,1), (5,1)),
        ('SPAN', (1,2), (3,2)),
        ('SPAN', (1,3), (5,3)),
        ('SPAN', (1,4), (3,4)),
    ])
    story.append(t_meta)
    story.append(Spacer(1, 4*mm))

    # 01 Identificación
    story.append(Paragraph("01 IDENTIFICACIÓN Y ALCANCE DEL PROCESO", sec_title_style))
    data_01 = [
        [Paragraph("PRESUPUESTO OFICIAL", cell_bold), Paragraph(formatear_moneda_cop(licitacion.get("cuantia_presupuesto")), cell_center_bold),
         Paragraph("LUGAR", cell_bold), Paragraph(licitacion.get("lugar_ejecucion", "Bogotá D.C."), cell_center),
         Paragraph("PLAZO", cell_bold), Paragraph(licitacion.get("tiempo_ejecucion", ""), cell_center)],
        [Paragraph("ETAPA ACTUAL SECOP", cell_bold), Paragraph(licitacion.get("etapa_actual", ""), cell_center),
         Paragraph("REVISIÓN", cell_bold), Paragraph(licitacion.get("estado_revision", ""), cell_center),
         Paragraph("LINK DIRECTO SECOP", cell_bold), Paragraph("Ver en SECOP", cell_center)]
    ]
    story.append(make_table(data_01, [40*mm, 38*mm, 25*mm, 25*mm, 28*mm, 30*mm], [
        ('BACKGROUND', (0,0), (0,-1), gray_bg),
        ('BACKGROUND', (2,0), (2,-1), gray_bg),
        ('BACKGROUND', (4,0), (4,-1), gray_bg),
    ]))
    story.append(Spacer(1, 4*mm))

    # 02 Hitos
    story.append(Paragraph("02 HITOS Y FECHAS DE INTERÉS", sec_title_style))
    data_02 = [
        [Paragraph("INTERÉS", cell_center_bold), Paragraph("SORTEO", cell_center_bold), Paragraph("MIPYME", cell_center_bold),
         Paragraph("OBS. PROYECTO", cell_center_bold), Paragraph("OBS. DEFINITIVO", cell_center_bold), Paragraph("OFERTAS", cell_center_bold)],
        [Paragraph(licitacion.get("fecha_manifestacion_interes") or "N/A", cell_center),
         Paragraph(licitacion.get("fecha_sorteo") or "N/A", cell_center),
         Paragraph(licitacion.get("fecha_limitacion_mipyme") or "N/A", cell_center),
         Paragraph(licitacion.get("fecha_obs_prepliego") or "N/A", cell_center),
         Paragraph(licitacion.get("fecha_obs_pliego_def") or "N/A", cell_center),
         Paragraph(licitacion.get("fecha_presentacion_oferta") or "N/A", cell_center_bold)]
    ]
    story.append(make_table(data_02, [31*mm]*6, [('BACKGROUND', (0,0), (-1,0), gray_bg)]))
    story.append(Spacer(1, 4*mm))

    # 03 UNSPSC
    story.append(Paragraph("03 CLASIFICACIÓN UNSPSC Y COINCIDENCIA CON EL RUP", sec_title_style))
    codigos_req = licitacion.get("codigos_unspsc_req") or []
    str_codigos = "; ".join(codigos_req) if codigos_req else "No especificados"
    cant_req = licitacion.get("cant_codigos_unspsc_req", len(codigos_req))
    cant_cumple = simulacion.get("codigos_cumplidos", 0)
    data_03 = [
        [Paragraph("CÓDIGOS UNSPSC RUP REQUERIDOS", cell_bold), Paragraph(str_codigos, cell_style), "", "", "", ""],
        [Paragraph("CANTIDAD TOTAL CÓDIGOS", cell_bold), Paragraph(str(cant_req), cell_center),
         Paragraph("CÓDIGOS MÍNIMOS REQUERIDOS", cell_bold), Paragraph(str(licitacion.get('minimo_codigos_unspsc_exigidos') or cant_req), cell_center),
         Paragraph("CÓDIGOS CUMPLE", cell_bold), Paragraph(str(cant_cumple), cell_center_bold)]
    ]
    story.append(make_table(data_03, [50*mm, 20*mm, 52*mm, 20*mm, 24*mm, 20*mm], [
        ('BACKGROUND', (0,0), (0,-1), gray_bg),
        ('BACKGROUND', (2,1), (2,1), gray_bg),
        ('BACKGROUND', (4,1), (4,1), gray_bg),
        ('SPAN', (1,0), (5,0))
    ]))
    story.append(Spacer(1, 4*mm))

    # 04 Financieros
    story.append(Paragraph("04 COMPARATIVO DE REQUISITOS FINANCIEROS", sec_title_style))
    data_04 = [[Paragraph("INDICADOR", cell_center_bold), Paragraph("REGLA", cell_center_bold), Paragraph("EXIGIDO", cell_center_bold),
                Paragraph("EMPRESA (RUP)", cell_center_bold), Paragraph("CUMPLE/NO CUMPLE", cell_center_bold)]]
    
    for ind in simulacion.get("comparativo_indicadores", []):
        est = ind.get("estado", "REVISAR")
        color = 'green' if est == "CUMPLE" else 'red' if est == "NO CUMPLE" else '#B8860B'
        data_04.append([
            Paragraph(ind.get('indicador', '').split('(')[0].strip(), cell_style),
            Paragraph(ind.get('regla', ''), cell_center),
            Paragraph(ind.get('exigido_fmt', ''), cell_center),
            Paragraph(ind.get('consolidado_fmt', ''), cell_center),
            Paragraph(f"<font color='{color}'><b>{est}</b></font>", cell_center)
        ])
    
    estado_global = simulacion.get("estado_global", "REVISAR")
    color_global = 'green' if estado_global == "CUMPLE" else 'red' if estado_global == "NO CUMPLE" else '#B8860B'
    data_04.append([Paragraph("CONSOLIDADO FINANCIERO", ParagraphStyle('R', parent=cell_bold, alignment=2)), "", "", "", 
                    Paragraph(f"<font color='{color_global}'><b>{estado_global}</b></font>", cell_center)])
    
    story.append(make_table(data_04, [56*mm, 15*mm, 35*mm, 40*mm, 40*mm], [
        ('BACKGROUND', (0,0), (-1,0), gray_bg),
        ('BACKGROUND', (0,-1), (3,-1), gray_bg),
        ('SPAN', (0,-1), (3,-1))
    ]))
    story.append(Spacer(1, 4*mm))

    # 05 Anexo Técnico
    story.append(Paragraph("05 SÍNTESIS DE LA EJECUCIÓN | ANEXO TÉCNICO", sec_title_style))
    story.append(make_table([[Paragraph((licitacion.get('resumen_requerimientos_generales') or 'N/A').replace('\n', '<br/>'), cell_style)]], [186*mm], []))
    story.append(Spacer(1, 4*mm))

    # 06 Experiencia
    story.append(Paragraph("06 EXPERIENCIA GENERAL, ESPECÍFICA Y CONDICIONES DIFERENCIALES", sec_title_style))
    data_06 = [
        [Paragraph("CONTRATOS EXPERIENCIA GENERAL", cell_bold), Paragraph(licitacion.get('exp_general_contratos') or 'N/A', cell_style)],
        [Paragraph("REQUISITO/DESCRIPCIÓN DE EXPERIENCIA GENERAL", cell_bold), Paragraph((licitacion.get('exp_general_descripcion') or 'N/A').replace('\n', '<br/>'), cell_style)],
        [Paragraph("CONTRATOS EXPERIENCIA ESPECÍFICA", cell_bold), Paragraph(licitacion.get('exp_especifica_contratos') or 'N/A', cell_style)],
        [Paragraph("REQUISITO/DESCRIPCIÓN DE EXPERIENCIA ESPECÍFICA", cell_bold), Paragraph((licitacion.get('exp_especifica_descripcion') or 'N/A').replace('\n', '<br/>'), cell_style)],
        [Paragraph("EMPRENDIMIENTOS, MUJERES, MIPYMES Y REGLAS", cell_bold), Paragraph(licitacion.get('regla_emprendimientos_mujeres_mipyme') or 'N/A', cell_style)],
    ]
    story.append(make_table(data_06, [60*mm, 126*mm], [('BACKGROUND', (0,0), (0,-1), gray_bg)]))
    story.append(Spacer(1, 4*mm))

    # 07 Métodos
    story.append(Paragraph("07 MÉTODO DE OFERTA ECONÓMICA Y FACTORES TÉCNICOS PONDERABLES", sec_title_style))
    metodos_lista = licitacion.get("metodos_oferta_economica") or []
    metodos_html = "<br/>".join(metodos_lista) if isinstance(metodos_lista, list) else str(metodos_lista).replace('\n', '<br/>')
    data_07 = [
        [Paragraph("MÉTODOS DE EVALUACIÓN ECONÓMICA", cell_bold), Paragraph(metodos_html, cell_style)],
        [Paragraph("DESCRIPCIÓN DE FACTORES TÉCNICOS / DE CALIDAD / ADICIONALES", cell_bold), Paragraph((licitacion.get('factores_tecnicos_ponderables') or 'N/A').replace('\n', '<br/>'), cell_style)]
    ]
    story.append(make_table(data_07, [60*mm, 126*mm], [('BACKGROUND', (0,0), (0,-1), gray_bg)]))
    story.append(Spacer(1, 4*mm))

    # 08 Puntajes
    story.append(Paragraph("08 DISTRIBUCIÓN DE PUNTAJES Y TOTAL PONDERABLE", sec_title_style))
    data_08 = [
        [Paragraph("TÉCNICA", cell_center_bold), Paragraph("ECONÓMICA", cell_center_bold), Paragraph("IND. NAC.", cell_center_bold),
         Paragraph("DISCAPAC", cell_center_bold), Paragraph("MIPYME", cell_center_bold), Paragraph("MUJERES", cell_center_bold), Paragraph("TOTAL", cell_center_bold)],
        [Paragraph(str(licitacion.get('puntos_tecnica', 0)), cell_center),
         Paragraph(str(licitacion.get('puntos_economica', 0)), cell_center),
         Paragraph(str(licitacion.get('puntos_industria_nacional', 0)), cell_center),
         Paragraph(str(licitacion.get('puntos_discapacidad', 0)), cell_center),
         Paragraph(str(licitacion.get('puntos_mipyme', 0)), cell_center),
         Paragraph(str(licitacion.get('puntos_mujeres', 0)), cell_center),
         Paragraph(str(licitacion.get('total_puntos', 100)), cell_center_bold)]
    ]
    story.append(make_table(data_08, [26*mm]*6 + [30*mm], [('BACKGROUND', (0,0), (-1,0), gray_bg)]))
    story.append(Spacer(1, 4*mm))

    # 09 Observaciones
    story.append(Paragraph("09 DATOS IMPORTANTES A TENER EN CUENTA Y OBSERVACIONES", sec_title_style))
    story.append(make_table([[Paragraph((licitacion.get('observaciones_recomendaciones') or 'N/A').replace('\n', '<br/>'), cell_style)]], [186*mm], []))

    doc.build(story)
    
    if output_path:
        with open(output_path, "wb") as f:
            f.write(buffer.getvalue())
            
    return buffer.getvalue()