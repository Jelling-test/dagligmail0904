import os
import mysql.connector
from dotenv import load_dotenv

# Indlæs miljøvariabler
load_dotenv()

# Opret forbindelse til databasen
conn = mysql.connector.connect(
    host=os.getenv('DB_HOST'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME')
)

# Opret cursor
cursor = conn.cursor(dictionary=True)

# Definer den måler, vi leder efter
meter_name = "obkBFBFD7F0"
meter_pattern = "%obkBFBFD7F0%"

# Tjek i stroem_maalere tabellen
print("\n=== Søger i stroem_maalere ===")
cursor.execute("SELECT * FROM stroem_maalere WHERE entity_id LIKE %s OR navn LIKE %s", (meter_pattern, meter_pattern))
results = cursor.fetchall()
if results:
    print(f"Fundet {len(results)} resultater:")
    for row in results:
        print(f"ID: {row.get('id')}, Entity ID: {row.get('entity_id')}, Navn: {row.get('navn')}, Status: {row.get('status')}")
else:
    print("Ingen resultater fundet")

# Tjek i active_meters tabellen
print("\n=== Søger i active_meters ===")
cursor.execute("SELECT * FROM active_meters WHERE meter_id LIKE %s", (meter_pattern,))
results = cursor.fetchall()
if results:
    print(f"Fundet {len(results)} resultater:")
    for row in results:
        print(f"ID: {row.get('id')}, Booking ID: {row.get('booking_id')}, Meter ID: {row.get('meter_id')}")
else:
    print("Ingen resultater fundet")

# Søg i alle tabeller efter kolonner, der indeholder ordet 'meter' eller 'måler'
print("\n=== Søger efter måler-kolonner i alle tabeller ===")
cursor.execute("SHOW TABLES")
tables = cursor.fetchall()

for table_row in tables:
    table_name = list(table_row.values())[0]
    cursor.execute(f"SHOW COLUMNS FROM {table_name}")
    columns = cursor.fetchall()
    
    for column in columns:
        column_name = column.get('Field')
        if 'meter' in column_name.lower() or 'måler' in column_name.lower() or 'entity' in column_name.lower():
            print(f"Tabel: {table_name}, Kolonne: {column_name}")
            
            # Undersøg om vores måler findes i denne kolonne
            try:
                cursor.execute(f"SELECT * FROM {table_name} WHERE {column_name} LIKE %s LIMIT 5", (meter_pattern,))
                results = cursor.fetchall()
                if results:
                    print(f"  Fundet {len(results)} resultater:")
                    for row in results:
                        print(f"  Data: {row}")
            except Exception as e:
                print(f"  Fejl ved søgning: {str(e)}")

# Undersøg også, hvad Home Assistant ser
print("\n=== Home Assistant integration ===")
print("For at undersøge om Home Assistant har denne måler, skal du kontrollere, at:")
print("1. HASS_URL og HASS_TOKEN er korrekt konfigureret i .env filen")
print("2. Home Assistant API'et er tilgængeligt fra denne server")
print("3. Sensoren 'obkBFBFD7F0' er korrekt registreret i Home Assistant")

# Luk forbindelser
cursor.close()
conn.close()

print("\n=== Anbefaling ===")
print("Baseret på resultaterne, kan du muligvis registrere måleren manuelt i stroem_maalere tabellen med:")
print("INSERT INTO stroem_maalere (entity_id, navn, status) VALUES ('obkBFBFD7F0', 'Campingplads måler', 'LEDIG')")
