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

import base64

def procesar_cumpleanos_logic(datos_hoja: list):
    """Extrae correos, filtra fechas, obtiene imágenes y retorna payloads para n8n."""
    # 1. Extraer todos los correos (Destinatarios)
    todos_los_correos = set()
    for fila in datos_hoja:
        correo = buscar_valor_por_clave(fila, "correo electrónico")
        if correo:
            for c in re.split(r',| |;', correo):
                if '@' in c:
                    todos_los_correos.add(c.strip())
    
    lista_destinatarios = list(todos_los_correos)
    if not lista_destinatarios:
        print("No se encontraron correos en la base de datos.")
        return []

    bcc_string = ", ".join(lista_destinatarios)

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
        
        try:
            if '/' in fecha_str:
                partes = fecha_str.split('/')
                dia_nac = int(partes[0])
                mes_nac = int(partes[1])
            elif '-' in fecha_str:
                partes = fecha_str.split('-')
                if len(partes[0]) == 4:
                    dia_nac = int(partes[2].split(' ')[0])
                    mes_nac = int(partes[1])
                else:
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
    
    payloads_para_enviar = []

    # 4. Obtener imagenes de Jasper y armar Payloads
    url_jasper = "https://reporte-iaas.onrender.com/api/v1/generador/social-post"
    for c in cumpleaneros_hoy:
        nombre_completo = buscar_valor_por_clave(c, "nombre completo") or "Compañero/a"
        apodo = buscar_valor_por_clave(c, "sobrenombre") or ""
        url_foto = buscar_valor_por_clave(c, "adjunta una foto tuya") or ""

        nombre_mostrar = apodo if apodo else nombre_completo.split(' ')[0]

        payload_jasper = {
            "apodo": apodo,
            "nombreCompleto": nombre_completo,
            "urlFotoPerfil": url_foto
        }

        print(f"Solicitando imagen a Jasper para {nombre_mostrar}...")
        
        try:
            respuesta_jasper = requests.post(url_jasper, json=payload_jasper, timeout=120)
            respuesta_jasper.raise_for_status()
            image_b64 = base64.b64encode(respuesta_jasper.content).decode('utf-8')
        except Exception as e:
            import traceback
            print(f"Fallo al obtener la imagen de {nombre_mostrar} desde Jasper: {e}")
            traceback.print_exc()
            continue
        
        html_content = f"""
        <html>
            <body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #f9f9f9; padding: 20px;">
                <div style="max-width: 600px; margin: auto; background: white; border-radius: 10px; padding: 30px; border: 1px solid #ddd;">
                    <h1 style="color: #2E8B57; text-align: center;">¡Felicidades {nombre_mostrar}! 🎂</h1>
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

        payloads_para_enviar.append({
            "nombre": nombre_mostrar,
            "subject": f"¡Hoy celebramos a {nombre_mostrar}! 🥳 - IAAS Ecuador",
            "html": html_content,
            "bcc": bcc_string,
            "image_filename": f"felicitacion_{nombre_mostrar.replace(' ', '_')}.png",
            "image_base64": image_b64
        })

    return payloads_para_enviar


@app.post("/procesar-cumpleanos-diario")
async def procesar_cumpleanos(request: Request):
    """
    Endpoint principal. Recibe el JSON de n8n, procesa todo,
    y devuelve una lista de correos listos para enviarse por el nodo de Gmail.
    """
    try:
        datos = await request.json()
        if not isinstance(datos, list):
             raise HTTPException(status_code=400, detail="El cuerpo debe ser una lista JSON.")
        
        # Procesamiento Síncrono
        resultado = procesar_cumpleanos_logic(datos)
        
        return {
            "status": "success",
            "enviables": resultado,
            "cantidad": len(resultado)
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "online"}

