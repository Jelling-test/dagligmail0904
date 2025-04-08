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

def fix_package_size():
    """
    Sikrer at ingen pakker har en værdi på 0, da dette forårsager division by zero fejl.
    Opdaterer alle pakker med 0 eller NULL til en minimal værdi på 0.001
    """
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        
        cursor = conn.cursor(dictionary=True)
        
        # 1. Find pakker med 0 eller NULL værdi
        cursor.execute('''
            SELECT id, booking_id, meter_id, package_size 
            FROM active_meters 
            WHERE package_size IS NULL OR package_size <= 0
        ''')
        
        zero_packages = cursor.fetchall()
        print(f"Fandt {len(zero_packages)} pakker med 0 eller NULL værdi:")
        for pkg in zero_packages:
            print(f"ID: {pkg['id']}, Booking: {pkg['booking_id']}, Pakke-størrelse: {pkg['package_size']}")
        
        # 2. Opdater alle pakker med 0 eller NULL til 0.001
        cursor.execute('''
            UPDATE active_meters
            SET package_size = 0.001
            WHERE package_size IS NULL OR package_size <= 0
        ''')
        
        conn.commit()
        print(f"\nOpdaterede {cursor.rowcount} pakker med minimal værdi på 0.001 for at undgå division by zero")
        
        # 3. Verificer at alle pakker nu har positive værdier
        cursor.execute("SELECT id, booking_id, package_size FROM active_meters WHERE package_size <= 0")
        remaining_zero = cursor.fetchall()
        
        if remaining_zero:
            print(f"ADVARSEL: Der er stadig {len(remaining_zero)} pakker med 0 eller negativ værdi")
        else:
            print("Succes! Alle pakker har nu positive værdier")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Fejl: {e}")

if __name__ == "__main__":
    fix_package_size()
