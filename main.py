from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
import smtplib
from email.message import EmailMessage
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="IAAS Email Service")

def enviar_correos_lote(nombre_cumpleanero: str, destinatarios: list, image_data: bytes):
    # Plantilla HTML interna (Fácil de editar aquí)
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
    # Enviar al mismo remitente en 'To' para que no quede vacío ni exponga la lista
    msg['To'] = remitente
    
    # Anadir todos los destinatarios en Bcc para proteger direcciones y evitar Spam pasivo
    msg['Bcc'] = ", ".join(destinatarios)

    msg.set_content("Felicidades en tu día.", subtype='plain')
    msg.add_alternative(html_content, subtype='html')

    # Adjuntar imagen personalizada
    msg.add_attachment(
        image_data, 
        maintype='image', 
        subtype='png', 
        filename=f"felicitacion_{nombre_cumpleanero.replace(' ', '_')}.png"
    )

    # Envío vía Gmail SMTP
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(remitente, os.getenv("SMTP_PASSWORD"))
            smtp.send_message(msg)
    except Exception as e:
        print(f"Error en envío de lote: {str(e)}")

@app.post("/celebrar-cumpleanos")
async def celebrar_cumpleanos(
    background_tasks: BackgroundTasks,
    nombre_cumpleanero: str = Form(...),
    lista_correos: str = Form(...), # Correos separados por coma desde n8n
    image: UploadFile = File(...)
):
    try:
        image_data = await image.read()
        
        # Limpiar lista de destinatarios
        destinatarios = [email.strip() for email in lista_correos.split(",") if email.strip()]
        
        if not destinatarios:
            raise HTTPException(status_code=400, detail="La lista de correos está vacía.")

        # Lotes de a 50 destinatarios, para evitar límites estrictos de SMTP por transacción y spam
        batch_size = 50
        for i in range(0, len(destinatarios), batch_size):
            lote = destinatarios[i:i + batch_size]
            background_tasks.add_task(enviar_correos_lote, nombre_cumpleanero, lote, image_data)

        # n8n recibe respuesta al instante, no se bloquea esperando envío
        return {"status": "success", "message": "Correos encolados exitosamente", "total_recipients": len(destinatarios)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "online"}
