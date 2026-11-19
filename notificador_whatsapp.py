import os
import datetime
import urllib.parse
import requests
from supabase import create_client

SUPABASE_URL = "https://mqcjmrdznbgfhpmnmvns.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1xY2ptcmR6bmJnZmhwbW5tdm5zIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTI3MDc2NzksImV4cCI6MjEwODI4MzY3OX0.oihDE7Za6nZDrpNl2SSPIgdaGVy716nTVw-UZzAWUX0"

PHONE = os.environ.get("WHATSAPP_PHONE", "")
APIKEY = os.environ.get("CALLMEBOT_APIKEY", "")

def enviar_whatsapp(mensaje: str):
    if not PHONE or not APIKEY:
        print("Faltan WHATSAPP_PHONE o CALLMEBOT_APIKEY en los Secrets de GitHub.")
        return
    texto_codificado = urllib.parse.quote(mensaje)
    url = f"https://api.callmebot.com/whatsapp.php?phone={PHONE}&text={texto_codificado}&apikey={APIKEY}"
    r = requests.get(url, timeout=15)
    print(f"Estado envío WhatsApp: {r.status_code} - {r.text}")

def revisar_y_notificar():
    cliente = create_client(SUPABASE_URL, SUPABASE_KEY)
    res = cliente.table("licitaciones_secop").select("*").execute()
    licitaciones = res.data if isinstance(res.data, list) else []

    hoy = datetime.date.today()
    criticas = []
    medias = []
    polizas = []

    for lic in licitaciones:
        estado_rev = str(lic.get("estado_revision", ""))
        num_proc = str(lic.get("numero_proceso", "S/N"))
        entidad = str(lic.get("entidad", ""))[:35]

        # 1. Revisar cierres en los próximos 7 días
        f_raw = lic.get("fecha_presentacion_oferta")
        if f_raw and str(f_raw) != "N/A":
            partes = str(f_raw).split(" ")
            f_solo = partes[0]
            h_solo = partes[1][:5] if len(partes) > 1 else ""
            try:
                f_dt = datetime.datetime.strptime(f_solo, "%Y-%m-%d").date()
                dias = (f_dt - hoy).days
                if estado_rev not in ["Presentada", "Inviable", "Seleccionada", "Desierto"]:
                    if 0 <= dias <= 3:
                        criticas.append(f"• {num_proc} ({entidad}): cierra en {dias} día(s) [{f_solo} {h_solo}]")
                    elif 4 <= dias <= 7:
                        medias.append(f"• {num_proc} ({entidad}): cierra en {dias} días [{f_solo} {h_solo}]")
            except Exception:
                pass

        # 2. Revisar pólizas pendientes
        est_pol = str(lic.get("estado_poliza", ""))
        if est_pol in ["Pendiente", "Solicitada"] and estado_rev in ["Alistamiento", "Viable", "Presentacion"]:
            polizas.append(f"• {num_proc}: Póliza '{est_pol}'")

    if not criticas and not medias and not polizas:
        print("Sin alertas para hoy. No se envía mensaje.")
        return

    lineas = [f"⚖️ *RADAR SECOP II — {hoy.strftime('%d/%m/%Y')}*\n"]
    if criticas:
        lineas.append("🚨 *CIERRES URGENTES (0-3 días):*")
        lineas.extend(criticas)
        lineas.append("")
    if medias:
        lineas.append("⚠️ *PRÓXIMOS CIERRES (4-7 días):*")
        lineas.extend(medias)
        lineas.append("")
    if polizas:
        lineas.append("🛡️ *PÓLIZAS PENDIENTES:*")
        lineas.extend(polizas)

    enviar_whatsapp("\n".join(lineas))

if __name__ == "__main__":
    revisar_y_notificar()
