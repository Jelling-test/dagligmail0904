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

def fix_meter_entries():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        
        cursor = conn.cursor()
        
        # 1. Slet posten med booking_id = '41967' (streng)
        cursor.execute("DELETE FROM active_meters WHERE booking_id = '41967'")
        deleted_count = cursor.rowcount
        print(f"Slettet {deleted_count} post(er) med booking_id = '41967'")
        
        # 2. Opdater den anden post til at have korrekt package_size
        cursor.execute("UPDATE active_meters SET package_size = 250.000 WHERE id = 4")
        updated_count = cursor.rowcount
        print(f"Opdateret {updated_count} post(er) med id = 4 til package_size = 250.000")
        
        conn.commit()
        
        # Verificer ændringerne
        cursor.execute("SELECT * FROM active_meters")
        print("\nAktive målere efter rettelser:")
        for row in cursor.fetchall():
            print(f"ID: {row[0]}, Booking ID: {row[1]}, Måler: {row[2]}, Pakke: {row[4]}")
        
        cursor.close()
        conn.close()
        
        print("\nRettelser gennemført. Du kan nu genindlæse dashboardet.")
        
    except mysql.connector.Error as e:
        print(f"Fejl ved rettelse af målerdata: {e}")

if __name__ == "__main__":
    fix_meter_entries()
