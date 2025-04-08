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

def list_users_and_meters():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        
        cursor = conn.cursor(dictionary=True)
        
        # Hent alle brugere
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        
        print("\n=== Alle brugere i systemet ===")
        for user in users:
            print(f"ID: {user['id']}, Brugernavn: {user['username']}")
        
        # Hent alle aktive målere
        cursor.execute("SELECT * FROM active_meters")
        meters = cursor.fetchall()
        
        print("\n=== Alle aktive målere ===")
        for meter in meters:
            print(f"ID: {meter['id']}, Booking ID: {meter['booking_id']}, Måler: {meter['meter_id']}, Pakke: {meter['package_size']}")
        
        # Join users og active_meters for at se sammenhængen
        cursor.execute("""
            SELECT u.id as user_id, u.username, am.id as meter_id, am.meter_id as meter_entity_id, 
                   am.package_size, am.start_value
            FROM users u
            LEFT JOIN active_meters am ON u.id = am.booking_id
        """)
        joined_data = cursor.fetchall()
        
        print("\n=== Brugere og deres målere ===")
        for data in joined_data:
            meter_info = f"Måler: {data['meter_entity_id']}, Pakke: {data['package_size']}" if data['meter_entity_id'] else "Ingen måler"
            print(f"Bruger ID: {data['user_id']}, Navn: {data['username']}, {meter_info}")
        
        cursor.close()
        conn.close()
        
    except mysql.connector.Error as e:
        print(f"Fejl ved lisning af brugere og målere: {e}")

if __name__ == "__main__":
    list_users_and_meters()
