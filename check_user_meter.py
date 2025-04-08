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

def check_user_meter():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        
        cursor = conn.cursor(dictionary=True)
        
        # Tjek om bruger 41967 har en aktiv måler
        cursor.execute("SELECT * FROM active_meters WHERE booking_id = '41967'")
        meter = cursor.fetchone()
        
        if meter:
            print(f"Bruger 41967 har en aktiv måler:")
            print(f"ID: {meter['id']}")
            print(f"Booking ID: {meter['booking_id']}")
            print(f"Måler ID: {meter['meter_id']}")
            print(f"Start værdi: {meter['start_value']}")
            print(f"Pakke størrelse: {meter['package_size']}")
            
            # Tjek power_events for denne bruger
            cursor.execute("SELECT * FROM power_events WHERE user_id = '41967' ORDER BY created_at DESC LIMIT 5")
            events = cursor.fetchall()
            
            if events:
                print("\nSeneste power events for bruger 41967:")
                for event in events:
                    print(f"Tid: {event['created_at']}, Type: {event['event_type']}, Detaljer: {event['details']}")
            else:
                print("\nIngen power events fundet for bruger 41967")
        else:
            print("Bruger 41967 har IKKE en aktiv måler!")
        
        cursor.close()
        conn.close()
        
    except mysql.connector.Error as e:
        print(f"Fejl ved kontrol af brugerens måler: {e}")

if __name__ == "__main__":
    check_user_meter()
