from fastapi import FastAPI, UploadFile, File, Form, HTTPException
import smtplib
from email.message import EmailMessage
import os

app = FastAPI(title="IAAS Email Service")

# Endpoint para recibir datos de n8n
@app.post("/send-birthday-email")
async def send_birthday_email(
    to_email: str = Form(...),
    subject: str = Form(...),
    body: str = Form(...),
    image: UploadFile = File(...)
):
    try:
        # Configuración del mensaje
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = os.getenv("SMTP_USER")
        msg['To'] = to_email.strip()
        msg.set_content(body, subtype='html')

        # Leer y adjuntar la imagen generada por tu servicio Java
        image_data = await image.read()
        msg.add_attachment(
            image_data, 
            maintype='image', 
            subtype='png', 
            filename=f"felicitacion_iaas.png"
        )

        # Envío seguro mediante SMTP_SSL
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
            smtp.send_message(msg)
        
        return {"status": "success", "message": f"Email enviado a {to_email}"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "online"}
