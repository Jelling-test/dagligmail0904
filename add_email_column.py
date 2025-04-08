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

def add_email_column():
    """Tilføjer email kolonne til users tabellen"""
    try:
        # Opret forbindelse til databasen
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        
        cursor = conn.cursor()
        
        # Tjek om email kolonnen allerede findes
        cursor.execute("SHOW COLUMNS FROM users LIKE 'email'")
        email_column_exists = cursor.fetchone() is not None
        
        if not email_column_exists:
            print("Tilføjer email kolonne til users tabellen...")
            cursor.execute("ALTER TABLE users ADD COLUMN email VARCHAR(255)")
            print("Email kolonne tilføjet!")
        else:
            print("Email kolonnen findes allerede i users tabellen.")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("Handling gennemført.")
        
    except Exception as e:
        print(f"Fejl under tilføjelse af email kolonne: {e}")

if __name__ == "__main__":
    add_email_column()
