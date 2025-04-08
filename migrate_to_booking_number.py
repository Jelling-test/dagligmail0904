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

def migrate_to_booking_number():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        
        cursor = conn.cursor(dictionary=True)
        
        # Trin 1: Hent den aktuelle mapping mellem id og username (bookingnummer)
        cursor.execute("SELECT id, username FROM users")
        user_mappings = {user['id']: user['username'] for user in cursor.fetchall()}
        
        print("=== Bruger mapping (ID -> Bookingnummer) ===")
        for user_id, booking_number in user_mappings.items():
            print(f"ID: {user_id} -> Bookingnummer: {booking_number}")
        
        # Trin 2: Opdater active_meters tabellen til at bruge bookingnummer i stedet for bruger-id
        for user_id, booking_number in user_mappings.items():
            cursor.execute(
                "UPDATE active_meters SET booking_id = %s WHERE booking_id = %s",
                (booking_number, str(user_id))
            )
            rows_updated = cursor.rowcount
            if rows_updated > 0:
                print(f"Opdateret {rows_updated} målerpost(er) fra ID {user_id} til bookingnummer {booking_number}")
        
        conn.commit()
        
        # Trin 3: Vis resultatet af migreringen
        cursor.execute("SELECT * FROM active_meters")
        meters = cursor.fetchall()
        
        print("\n=== Opdaterede måleropslag ===")
        for meter in meters:
            print(f"ID: {meter['id']}, Booking ID (nu bookingnummer): {meter['booking_id']}, Måler: {meter['meter_id']}")
        
        print("\nMigrering gennemført. Systemet bruger nu bookingnumre i stedet for bruger-ID'er.")
        
        cursor.close()
        conn.close()
        
    except mysql.connector.Error as e:
        print(f"Fejl ved migrering til bookingnummer: {e}")

if __name__ == "__main__":
    migrate_to_booking_number()
