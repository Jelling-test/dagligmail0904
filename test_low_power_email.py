import os
from datetime import datetime
from dotenv import load_dotenv
from send_email import send_email
from email_templates import get_low_power_template

# Indlæs miljøvariabler
load_dotenv()

def test_low_power_email():
    """
    Test af email-advarselssystem på engelsk.
    """
    # Testbruger data
    user_data = {
        'fornavn': 'Peter',
        'efternavn': 'Smith',
        'email': 'peter@jellingcamping.dk',
        'language': 'en',  # Engelsk sprog
        'remaining': 2.0   # 2 enheder tilbage
    }
    
    print(f"Sender engelsk test-advarsel til: {user_data['email']}")
    
    # Hent email skabelon på engelsk
    template = get_low_power_template(user_data['language'])
    
    # Erstat pladsholdere i skabelonerne
    formatted_html = template['html'].format(
        fornavn=user_data['fornavn'],
        efternavn=user_data['efternavn'],
        remaining=user_data['remaining']
    )
    
    formatted_text = template['text'].format(
        fornavn=user_data['fornavn'],
        efternavn=user_data['efternavn'],
        remaining=user_data['remaining']
    )
    
    # Vis email-indhold til test
    print("\n--- EMAIL INFORMATION ---")
    print(f"Emne: {template['subject']}")
    print(f"Sprog: Engelsk")
    print(f"Modtager: {user_data['fornavn']} {user_data['efternavn']} <{user_data['email']}>")
    print(f"Resterende enheder: {user_data['remaining']}")
    
    # Send email
    result = send_email(
        user_data['email'], 
        template['subject'], 
        formatted_html,
        formatted_text
    )
    
    if result:
        print("\nSuccess! Engelsk advarselsemail sendt succesfuldt!")
        print("Tjek indbakken for at se den engelske version af advarslen.")
    else:
        print("\nFejl! Der opstod et problem ved afsendelse af emailen.")
        print("Tjek loggen for fejlmeddelelser og verifiér SMTP-indstillingerne.")

if __name__ == "__main__":
    test_low_power_email()
