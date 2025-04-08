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

def show_table_structure():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        
        cursor = conn.cursor(dictionary=True)
        
        # Vis struktur for users tabel
        cursor.execute("DESCRIBE users")
        print("\n=== Struktur for users tabel ===")
        for field in cursor.fetchall():
            print(f"Felt: {field['Field']}, Type: {field['Type']}, Nøgle: {field['Key']}, Null: {field['Null']}")
        
        # Vis struktur for active_meters tabel
        cursor.execute("DESCRIBE active_meters")
        print("\n=== Struktur for active_meters tabel ===")
        for field in cursor.fetchall():
            print(f"Felt: {field['Field']}, Type: {field['Type']}, Nøgle: {field['Key']}, Null: {field['Null']}")
        
        # Vis data for users tabel
        cursor.execute("SELECT * FROM users LIMIT 5")
        print("\n=== Data i users tabel (top 5) ===")
        users = cursor.fetchall()
        for user in users:
            print(f"ID: {user['id']}, Username: {user['username']}, Password: {'*' * len(user.get('password', ''))}")
        
        # Vis data for active_meters tabel
        cursor.execute("SELECT * FROM active_meters LIMIT 5")
        print("\n=== Data i active_meters tabel (top 5) ===")
        meters = cursor.fetchall()
        for meter in meters:
            print(f"ID: {meter['id']}, Booking ID: {meter['booking_id']}, Meter ID: {meter['meter_id']}")
        
        cursor.close()
        conn.close()
        
    except mysql.connector.Error as e:
        print(f"Fejl ved visning af tabelstruktur: {e}")

if __name__ == "__main__":
    show_table_structure()
