import os
import mysql.connector
from dotenv import load_dotenv

# Indlæs miljøvariabler
load_dotenv()

# Hent database konfiguration
DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')

def check_user_email():
    """Tjekker email for bruger med booking_id 41967"""
    try:
        # Opret forbindelse til databasen
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        
        cursor = conn.cursor(dictionary=True)
        
        print("\n===== BRUGER 41967 I AKTIVE_BOOKINGER =====")
        cursor.execute("SELECT * FROM aktive_bookinger WHERE booking_id = 41967")
        user_in_aktive = cursor.fetchone()
        
        if user_in_aktive:
            print(f"Booking ID: {user_in_aktive.get('booking_id')}")
            print(f"Navn: {user_in_aktive.get('fornavn')} {user_in_aktive.get('efternavn')}")
            print(f"Email: {user_in_aktive.get('email')}")
            print(f"Plads type: {user_in_aktive.get('plads_type')}")
            print(f"Ankomst: {user_in_aktive.get('ankomst_dato')}")
            print(f"Afrejse: {user_in_aktive.get('afrejse_dato')}")
        else:
            print("Bruger 41967 findes ikke i aktive_bookinger tabellen.")
        
        print("\n===== BRUGER 41967 I USERS =====")
        cursor.execute("SELECT * FROM users WHERE username = '41967'")
        user_in_users = cursor.fetchone()
        
        if user_in_users:
            print(f"ID: {user_in_users.get('id')}")
            print(f"Username: {user_in_users.get('username')}")
            print(f"Navn: {user_in_users.get('fornavn')} {user_in_users.get('efternavn')}")
            print(f"Email: {user_in_users.get('email')}")
            print(f"Oprettet: {user_in_users.get('created_at')}")
        else:
            print("Bruger 41967 findes ikke i users tabellen.")
            
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Fejl under tjek af bruger 41967: {e}")

if __name__ == "__main__":
    check_user_email()
