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

def debug_dashboard_query():
    """Debug af forespørgslen til active_meters tabellen i stroem_dashboard funktionen"""
    try:
        # Simuler brugerens bookingnummer
        username = "41967"
        
        print(f"Debugger SQL-forespørgsel for bruger: {username}")
        print("=" * 50)
        
        # Opret forbindelse til databasen
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        
        cursor = conn.cursor(dictionary=True)
        
        # Hent målerdata
        print(f"SQL: SELECT meter_id, start_value, package_size FROM active_meters WHERE booking_id = '{username}'")
        cursor.execute(
            'SELECT meter_id, start_value, package_size FROM active_meters WHERE booking_id = %s',
            (username,)
        )
        meter_data = cursor.fetchone()
        
        print(f"Returneret data: {meter_data}")
        
        if not meter_data:
            print("PROBLEM: Ingen data fundet - bruger vil blive omdirigeret til select_meter.html")
        else:
            print("SUCCES: Data fundet - bruger burde se strømdashboard")
            
        # Tjek direkte i databasen om brugeren har en aktiv måler
        cursor.execute('DESCRIBE active_meters')
        columns = cursor.fetchall()
        print("\nTabel-struktur for active_meters:")
        for col in columns:
            print(f"  {col['Field']} - {col['Type']}")
            
        # Tjek alle aktive målere
        cursor.execute('SELECT * FROM active_meters')
        all_meters = cursor.fetchall()
        print("\nAlle aktive målere i databasen:")
        for meter in all_meters:
            print(f"  {meter}")
            
        # Specifikt søg efter aktive målere for denne bruger med alle mulige kolonnenavne
        print("\nSøger efter aktive målere for denne bruger med alle mulige kolonnenavne:")
        
        # Prøv med user_id
        cursor.execute('SELECT * FROM active_meters WHERE booking_id = %s', (username,))
        result1 = cursor.fetchall()
        print(f"  Med booking_id = {username}: {result1}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Fejl under debug: {e}")

if __name__ == "__main__":
    debug_dashboard_query()
