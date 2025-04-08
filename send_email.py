import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

# Indlæs miljøvariabler
load_dotenv()

# Hent email konfiguration
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USERNAME = os.getenv('SMTP_USERNAME')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
EMAIL_FROM = os.getenv('EMAIL_FROM')

def send_email(to_email, subject, message_html, message_text=None):
    """
    Sender en email til den angivne modtager
    
    Args:
        to_email (str): Modtagers email
        subject (str): Emne på emailen
        message_html (str): HTML-indhold af emailen
        message_text (str, optional): Tekstversion af emailen. 
                                    Hvis None, bruges en forenklet version af HTML-indholdet.
    
    Returns:
        bool: True hvis emailen blev sendt, ellers False
    """
    if not all([SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, EMAIL_FROM]):
        print("Email konfiguration er ikke fuldendt. Tjek .env filen.")
        return False
        
    if not to_email:
        print("Ingen modtager-email angivet.")
        return False
    
    try:
        # Opret email-meddelelsen
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = EMAIL_FROM
        msg['To'] = to_email
        
        # Tilføj tekst og HTML versioner
        if message_text:
            msg.attach(MIMEText(message_text, 'plain'))
        msg.attach(MIMEText(message_html, 'html'))
        
        # Send emailen
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        print(f"Email sendt til {to_email}: {subject}")
        return True
    
    except Exception as e:
        print(f"Fejl ved afsendelse af email: {e}")
        return False

# Eksempel på anvendelse
if __name__ == "__main__":
    test_email = "test@example.com"  # Erstat med en rigtig email for at teste
    test_subject = "Test af Jelling Camping strømadvarsel"
    test_html = """
    <html>
      <body>
        <h2>Jelling Camping - Strømadvarsel</h2>
        <p>Dette er en test af strømadvarselsystemet.</p>
        <p>Med venlig hilsen,<br>Jelling Camping</p>
      </body>
    </html>
    """
    
    send_email(test_email, test_subject, test_html)
