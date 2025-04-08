import mysql.connector
import os
from dotenv import load_dotenv
import datetime

# Prøv at indlæse miljøvariabler, hvis .env findes
try:
    load_dotenv()
except:
    pass

# Bruger ID og måler ID
BOOKING_ID = "41967"  # Allan Halse
METER_ID = "meter_1"  # Erstat med en faktisk måler ID
PACKAGE_SIZE = 0.1    # Meget lille pakke for at teste 0-enheder scenariet

# Forbind til databasen
try:
    conn = mysql.connector.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        database=os.getenv('DB_NAME', 'hastighed'),
        charset='utf8mb4',
        collation='utf8mb4_unicode_ci'
    )
    
    cursor = conn.cursor(dictionary=True)
    
    # Kontroller om brugeren allerede har en måler
    cursor.execute('SELECT * FROM active_meters WHERE booking_id = %s', (BOOKING_ID,))
    existing_meter = cursor.fetchone()
    
    if existing_meter:
        print(f"Bruger {BOOKING_ID} har allerede måler {existing_meter['meter_id']} tilknyttet.")
        print(f"Nuværende package_size: {existing_meter['package_size']}")
        
        # Opdater package_size til en meget lav værdi for at teste
        cursor.execute(
            'UPDATE active_meters SET package_size = %s WHERE booking_id = %s',
            (PACKAGE_SIZE, BOOKING_ID)
        )
        conn.commit()
        print(f"Opdateret package_size til {PACKAGE_SIZE} for måler {existing_meter['meter_id']}")
    else:
        # Kontroller først om måleren er ledig
        cursor.execute('SELECT * FROM active_meters WHERE meter_id = %s', (METER_ID,))
        meter_in_use = cursor.fetchone()
        
        if meter_in_use:
            print(f"Måler {METER_ID} er allerede i brug af booking_id {meter_in_use['booking_id']}")
        else:
            # Tilknyt måleren til brugeren
            now = datetime.datetime.now()
            cursor.execute(
                'INSERT INTO active_meters (booking_id, meter_id, package_size, created_at) VALUES (%s, %s, %s, %s)',
                (BOOKING_ID, METER_ID, PACKAGE_SIZE, now)
            )
            conn.commit()
            print(f"Måler {METER_ID} er nu tilknyttet bruger {BOOKING_ID} med package_size {PACKAGE_SIZE}")
    
    # Vis aktive måler tilknytninger
    print("\n=== AKTIVE MÅLER TILKNYTNINGER EFTER ÆNDRINGER ===")
    cursor.execute('SELECT * FROM active_meters')
    meter_results = cursor.fetchall()
    
    if meter_results:
        for row in meter_results:
            print(f"ID: {row.get('id')}, Booking ID: {row.get('booking_id')}, Måler: {row.get('meter_id')}, Pakke: {row.get('package_size')}, Oprettet: {row.get('created_at')}")
    else:
        print("Ingen aktive måler tilknytninger fundet.")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"Fejl ved forbindelse til database: {e}")
