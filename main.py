from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
import smtplib
from email.message import EmailMessage
import os
import requests
import re
from datetime import datetime
import pytz
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="IAAS Email Service")

def buscar_valor_por_clave(diccionario: dict, subcadena: str):
    """Busca en un diccionario la primera clave que contenga (case-insensitive) la subcadena y devuelve su valor."""
    sub_lower = subcadena.lower()
    for key, value in diccionario.items():
        if sub_lower in key.lower():
            if isinstance(value, str):
                return value.strip()
            return value
    return None

def enviar_correos_lote(nombre_cumpleanero: str, destinatarios: list, image_data: bytes):
    if not destinatarios or not image_data:
        print(f"Lote vacío o sin imagen para {nombre_cumpleanero}")
        return

    html_content = f"""
    <html>
        <body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #f9f9f9; padding: 20px;">
            <div style="max-width: 600px; margin: auto; background: white; border-radius: 10px; padding: 30px; border: 1px solid #ddd;">
                <h1 style="color: #2E8B57; text-align: center;">¡Felicidades {nombre_cumpleanero}! 🎂</h1>
                <p style="font-size: 16px; color: #555;">Hola a toda la <b>FamilIAAS Ecuador</b>,</p>
                <p style="font-size: 16px; color: #555;">Hoy nos unimos para celebrar la vida de nuestro/a querido/a compañero/a.</p>
                <p style="font-size: 16px; color: #555;">Adjunto encontrarán un detalle especial diseñado por OpenHub para compartir este momento.</p>
                <div style="text-align: center; margin-top: 20px;">
                    <span style="font-size: 40px;">🎉 🥳 🎈</span>
                </div>
            </div>
        </body>
    </html>
    """

    msg = EmailMessage()
    msg['Subject'] = f"¡Hoy celebramos a {nombre_cumpleanero}! 🥳 - IAAS Ecuador"
    
    remitente = os.getenv("SMTP_USER")
    msg['From'] = remitente
    msg['To'] = remitente
    msg['Bcc'] = ", ".join(destinatarios)

    msg.set_content("Felicidades en tu día.", subtype='plain')
    msg.add_alternative(html_content, subtype='html')

    msg.add_attachment(
        image_data, 
        maintype='image', 
        subtype='png', 
        filename=f"felicitacion_{nombre_cumpleanero.replace(' ', '_')}.png"
    )

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
            smtp.starttls()
            smtp.login(remitente, os.getenv("SMTP_PASSWORD"))
            smtp.send_message(msg)
            print(f"Lote enviado con éxito a {len(destinatarios)} destinatarios por el cumple de {nombre_cumpleanero}.")
    except Exception as e:
        import traceback
        print(f"Error en envío de lote por {nombre_cumpleanero}: {str(e)}")
        traceback.print_exc()

def tarea_procesar_cumpleanos(datos_hoja: list):
    """Tarea asíncrona que extrae todos los correos, filtra cumpleañeros, llama a Java y manda los mails."""
    try:
        # 1. Extraer todos los correos (Destinatarios)
        todos_los_correos = set()
        for fila in datos_hoja:
            correo = buscar_valor_por_clave(fila, "correo electrónico")
            if correo:
                # Si en el excel ponen múltiples separados por coma, o espacios:
               for c in re.split(r',| |;', correo):
                   if '@' in c:
                       todos_los_correos.add(c.strip())
        
        lista_destinatarios = list(todos_los_correos)
        if not lista_destinatarios:
            print("No se encontraron correos en la base de datos para enviar el mensaje.")
            return

        print(f"Correos totales extraídos para Bcc: {len(lista_destinatarios)}")

        # 2. Identificar el día actual en Ecuador
        tz_ec = pytz.timezone('America/Guayaquil')
        hoy_ec = datetime.now(tz_ec)
        dia_actual = hoy_ec.day
        mes_actual = hoy_ec.month

        # 3. Filtrar cumpleañeros
        cumpleaneros_hoy = []
        for fila in datos_hoja:
            fecha_str = buscar_valor_por_clave(fila, "fecha de nacimiento")
            if not fecha_str:
                 continue
            
            # Intentar parsear "DD/MM/YYYY" o "YYYY-MM-DD"
            try:
                if '/' in fecha_str:
                    partes = fecha_str.split('/')
                    dia_nac = int(partes[0])
                    mes_nac = int(partes[1])
                elif '-' in fecha_str:
                    partes = fecha_str.split('-')
                    if len(partes[0]) == 4: # YYYY-MM-DD
                        dia_nac = int(partes[2].split(' ')[0])
                        mes_nac = int(partes[1])
                    else: # DD-MM-YYYY
                        dia_nac = int(partes[0])
                        mes_nac = int(partes[1])
                else:
                    continue

                if dia_nac == dia_actual and mes_nac == mes_actual:
                    cumpleaneros_hoy.append(fila)

            except Exception as e:
                print(f"Error procesando fecha {fecha_str}: {e}")
                continue

        print(f"Se encontraron {len(cumpleaneros_hoy)} cumpleañeros hoy.")

        # 4. Por cada cumpleañero, llamar a Java Jasper y Enviar Lotes
        for c in cumpleaneros_hoy:
            nombre_completo = buscar_valor_por_clave(c, "nombre completo") or "Compañero/a"
            apodo = buscar_valor_por_clave(c, "sobrenombre") or ""
            url_foto = buscar_valor_por_clave(c, "adjunta una foto tuya") or ""

            # Nombre a usar en el asunto/mensaje
            nombre_mostrar = apodo if apodo else nombre_completo.split(' ')[0]

            # Payload para el servicio Jasper en Render
            payload_jasper = {
                "apodo": apodo,
                "nombreCompleto": nombre_completo,
                "urlFotoPerfil": url_foto
            }

            print(f"Solicitando imagen a Jasper para {nombre_mostrar}...")
            
            # Petición HTTP síncrona al servicio Java (timeout preventivo)
            url_jasper = "https://reporte-iaas.onrender.com/api/v1/generador/social-post"
            try:
                respuesta_jasper = requests.post(url_jasper, json=payload_jasper, timeout=120)
                respuesta_jasper.raise_for_status()
                image_data = respuesta_jasper.content
            except Exception as e:
                import traceback
                print(f"Fallo al obtener la imagen de {nombre_mostrar} desde Jasper: {e}")
                traceback.print_exc()
                continue
            
            print(f"Imagen obtenida para {nombre_mostrar}. Repartiendo en lotes...")
            
            # 5. Dividir destinatarios en lotes de 50 y enviar
            batch_size = 50
            for i in range(0, len(lista_destinatarios), batch_size):
                lote = lista_destinatarios[i:i + batch_size]
                enviar_correos_lote(nombre_mostrar, lote, image_data)

    except Exception as e:
         import traceback
         print(f"Falla general en la tarea de procesamiento: {e}")
         traceback.print_exc()


@app.post("/procesar-cumpleanos-diario")
async def procesar_cumpleanos(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint principal. Recibe TODO el JSON exportado de Google Sheets mediante n8n.
    """
    try:
        datos = await request.json()
        if not isinstance(datos, list):
             raise HTTPException(status_code=400, detail="El cuerpo de la petición debe ser una lista JSON con las filas de gsheets.")
        
        # Iniciar todo el proceso en el subproceso para no causar Timeout en n8n
        background_tasks.add_task(tarea_procesar_cumpleanos, datos)

        return {
            "status": "success", 
            "message": "Analisis iniciado. La aplicación filtrará fechas, se comunicará con Jasper y encolará los correos en segundo plano."
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "online"}

