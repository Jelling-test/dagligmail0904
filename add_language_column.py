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

def add_language_column():
    """Tilføjer en language-kolonne til users-tabellen"""
    try:
        # Opret forbindelse til databasen
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        
        cursor = conn.cursor()
        
        # Tjek om kolonnen allerede eksisterer
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s
            AND TABLE_NAME = 'users'
            AND COLUMN_NAME = 'language'
        """, (DB_NAME,))
        
        if cursor.fetchone()[0] == 0:
            # Tilføj language-kolonnen med 'da' som standardværdi
            cursor.execute("""
                ALTER TABLE users
                ADD COLUMN language VARCHAR(5) DEFAULT 'da'
            """)
            
            print("Language-kolonnen er tilføjet til users-tabellen")
        else:
            print("Language-kolonnen eksisterer allerede i users-tabellen")
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Fejl under tilføjelse af language-kolonne: {e}")

if __name__ == "__main__":
    add_language_column()
