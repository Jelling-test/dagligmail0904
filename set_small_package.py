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

def update_package_size():
    """Opdaterer package_size for bruger 41967 til 0.003 enheder"""
    try:
        # Opret forbindelse til databasen
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        
        cursor = conn.cursor(dictionary=True)
        
        # Vis nuværende indstillinger
        cursor.execute('SELECT * FROM active_meters WHERE booking_id = %s', ('41967',))
        before = cursor.fetchone()
        print(f"FØR opdatering: {before}")
        
        # Opdater package_size til 0.003 enheder
        cursor.execute('''
            UPDATE active_meters
            SET package_size = 0.003
            WHERE booking_id = %s
        ''', ('41967',))
        
        conn.commit()
        
        # Vis opdaterede indstillinger
        cursor.execute('SELECT * FROM active_meters WHERE booking_id = %s', ('41967',))
        after = cursor.fetchone()
        print(f"EFTER opdatering: {after}")
        
        print("Pakkestørrelse er nu opdateret til 0.003 enheder")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Fejl under opdatering: {e}")

if __name__ == "__main__":
    update_package_size()
