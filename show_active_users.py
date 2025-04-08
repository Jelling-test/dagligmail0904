import mysql.connector
import os
from dotenv import load_dotenv

# Prøv at indlæse miljøvariabler, hvis .env findes
try:
    load_dotenv()
except:
    pass

# Forbind til databasen
try:
    # Brug de samme indstillinger som app.py
    conn = mysql.connector.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        database=os.getenv('DB_NAME', 'hastighed'),
        charset='utf8mb4',
        collation='utf8mb4_unicode_ci'
    )
    
    cursor = conn.cursor(dictionary=True)
    
    # Først undersøg strukturen af users tabellen
    print("\n=== USERS TABEL STRUKTUR ===")
    cursor.execute("DESCRIBE users")
    columns = cursor.fetchall()
    for col in columns:
        print(f"Kolonne: {col.get('Field')}, Type: {col.get('Type')}")
    
    # Vis aktive brugere
    print("\n=== AKTIVE BRUGERE (aktive_bookinger) ===")
    cursor.execute('SELECT * FROM aktive_bookinger')
    results = cursor.fetchall()
    
    if results:
        for row in results:
            print(f"ID: {row.get('id')}, Booking ID: {row.get('booking_id')}")
    else:
        print("Ingen aktive brugere fundet.")
    
    # Vis brugeroplysninger for bruger 41967
    print("\n=== BRUGEROPLYSNINGER FOR 41967 ===")
    cursor.execute('SELECT * FROM users WHERE username = "41967"')
    user_info = cursor.fetchone()
    
    if user_info:
        for key, value in user_info.items():
            print(f"{key}: {value}")
    else:
        print("Bruger 41967 ikke fundet i users tabellen.")
    
    # Vis aktive måler tilknytninger
    print("\n=== AKTIVE MÅLER TILKNYTNINGER (active_meters) ===")
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
