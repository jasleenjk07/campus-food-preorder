import smtplib #Python’s built-in library to send emails using SMTP protocol. SMTP = Simple Mail Transfer Protocol

from email.mime.text import MIMEText #Used to create the email body
from email.mime.multipart import MIMEMultipart #Used to create an email

from app.config import settings #This pulls values like: EMAIL_HOST, EMAIL_PORT, EMAIL_USER, EMAIL_PASSWORD, EMAIL_FROM

def send_email(to_email: str, subject: str, body: str):
    msg = MIMEMultipart()
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain")) #"plain" → means plain text email

    with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT) as server: #This opens a connection to your email server
        server.starttls() #TLS = Transport Layer Security, Encrypts your connection 
        server.login(settings.EMAIL_USER, settings.EMAIL_PASSWORD) #Authenticates with the email serve
        server.send_message(msg) #Sends the email