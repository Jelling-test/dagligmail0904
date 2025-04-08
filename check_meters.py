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

def check_meters():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        
        cursor = conn.cursor(dictionary=True)
        
        # Hent alle aktive målere med brugeroplysninger
        cursor.execute("""
            SELECT am.*, u.username 
            FROM active_meters am
            JOIN users u ON am.booking_id = u.id
        """)
        
        meters = cursor.fetchall()
        
        print("Aktive målere fundet:")
        for meter in meters:
            print(f"Bruger: {meter.get('username', 'Ukendt')}, ID: {meter['booking_id']}, Pakke størrelse: {meter['package_size']}")
        
        cursor.close()
        conn.close()
        
    except mysql.connector.Error as e:
        print(f"Fejl ved søgning efter målere: {e}")

if __name__ == "__main__":
    check_meters()
