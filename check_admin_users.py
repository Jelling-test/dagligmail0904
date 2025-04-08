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

def check_admin_users():
    """Tjekker users tabellen for admin felter eller brugere"""
    try:
        # Opret forbindelse til databasen
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        
        cursor = conn.cursor(dictionary=True)
        
        # Tjek kolonner i users tabellen
        cursor.execute("""
            SHOW COLUMNS FROM users
        """)
        
        columns = cursor.fetchall()
        print("Kolonner i users tabellen:")
        for column in columns:
            print(f"  - {column['Field']} ({column['Type']})")
            
        print("\n")
        
        # Hent alle brugere for at se om der er admin konti
        cursor.execute("""
            SELECT id, username, fornavn, efternavn, email, language FROM users
        """)
        
        users = cursor.fetchall()
        print(f"Fandt {len(users)} brugere i databasen:")
        for user in users:
            print(f"  - ID: {user['id']}, Brugernavn: {user['username']}, Navn: {user['fornavn']} {user['efternavn']}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Fejl ved kontrol af admin brugere: {e}")

if __name__ == "__main__":
    check_admin_users()
