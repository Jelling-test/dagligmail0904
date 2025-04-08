import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from send_email import send_email

# Indlæs miljøvariabler
load_dotenv()

def test_email_system():
    """
    Test af email-systemet.
    
    Dette script sender en test-email til den angivne adresse
    for at verificere, at email-konfigurationen fungerer korrekt.
    """
    
    # Tjek om der er angivet en modtager-email som argument
    if len(sys.argv) < 2:
        print("FEJL: Du skal angive en modtager-email som argument.")
        print("Eksempel: python test_email_system.py test@example.com")
        sys.exit(1)
    
    to_email = sys.argv[1]
    
    # Indlæs SMTP konfiguration
    smtp_user = os.getenv('SMTP_USERNAME')
    smtp_pass = os.getenv('SMTP_PASSWORD')
    
    if not all([smtp_user, smtp_pass]):
        print("FEJL: SMTP konfiguration er ikke komplet i .env filen.")
        print("Sørg for at SMTP_USERNAME og SMTP_PASSWORD er sat korrekt.")
        sys.exit(1)
    
    print(f"Sender test-email til: {to_email}")
    print(f"Afsender: {os.getenv('EMAIL_FROM')}")
    print(f"SMTP server: {os.getenv('SMTP_SERVER')}:{os.getenv('SMTP_PORT')}")
    print(f"SMTP bruger: {smtp_user}")
    
    # Opret email indhold
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    subject = f"Jelling Camping - Test af strømadvarselssystem ({current_time})"
    
    html_message = f"""
    <html>
      <body>
        <h2>Jelling Camping - Strømadvarselstest</h2>
        <p>Dette er en test af strømadvarselsystemet fra Jelling Camping.</p>
        <p>Testen blev afsendt: {current_time}</p>
        <hr>
        <p>Hvis du modtager denne email, fungerer systemet korrekt!</p>
        <p>Med venlig hilsen,<br>Jelling Camping</p>
      </body>
    </html>
    """
    
    # Send test-email
    result = send_email(to_email, subject, html_message)
    
    if result:
        print("Success! Email blev sendt succesfuldt!")
        print("Tjek din indbakke for at verificere modtagelsen.")
    else:
        print("Fejl! Der opstod et problem ved afsendelse af emailen.")
        print("Tjek loggen for fejlmeddelelser og verifiér SMTP-indstillingerne.")

if __name__ == "__main__":
    test_email_system()
