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

def update_package_size(user_id, new_size):
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        
        cursor = conn.cursor()
        
        # Opdater pakke størrelsen
        cursor.execute("""
            UPDATE active_meters
            SET package_size = %s
            WHERE booking_id = %s
        """, (new_size, user_id))
        
        conn.commit()
        
        if cursor.rowcount > 0:
            print(f"Pakke størrelse opdateret til {new_size} for bruger med ID {user_id}")
        else:
            print(f"Ingen poster opdateret. Bruger med ID {user_id} har muligvis ikke en aktiv måler")
        
        cursor.close()
        conn.close()
        
    except mysql.connector.Error as e:
        print(f"Fejl ved opdatering af pakke størrelse: {e}")

if __name__ == "__main__":
    # Opdater pakke størrelsen for bruger med ID 2 til 0.005
    update_package_size(2, 0.005)
