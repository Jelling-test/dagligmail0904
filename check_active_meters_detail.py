import os
import mysql.connector
from dotenv import load_dotenv
from mysql.connector import Error

# Indlæs miljøvariabler fra .env filen
load_dotenv()

print('Undersøger aktive målere og bookinger...')

try:
    # Opret forbindelse til databasen
    conn = mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )
    
    if conn.is_connected():
        print('Forbindelse oprettet succesfuldt!')
        cursor = conn.cursor(dictionary=True)
        
        # Tjek aktive målere
        print("\n=== AKTIVE MÅLERE ===")
        cursor.execute('SELECT * FROM active_meters')
        active_meters = cursor.fetchall()
        
        if active_meters:
            for meter in active_meters:
                print(f"ID: {meter['id']}, Booking ID: {meter['booking_id']}, Måler ID: {meter['meter_id']}")
                print(f"  Startværdi: {meter['start_value']}, Pakkestørrelse: {meter['package_size']}")
                print(f"  Oprettet: {meter['created_at']}")
                
                # Tjek om måler findes i meter_config
                cursor.execute('SELECT * FROM meter_config WHERE sensor_id = %s', (meter['meter_id'],))
                config = cursor.fetchone()
                if config:
                    print(f"  Måler findes i konfiguration: {config['display_name']} (ID: {config['id']})")
                else:
                    print(f"  ADVARSEL: Måler findes IKKE i konfiguration!")
                
                # Tjek om booking findes
                cursor.execute('SELECT * FROM aktive_bookinger WHERE booking_id = %s', (meter['booking_id'],))
                booking = cursor.fetchone()
                if booking:
                    print(f"  Booking findes: {booking['navn']} (Type: {booking['plads_type']})")
                else:
                    print(f"  ADVARSEL: Booking findes IKKE!")
        else:
            print("Ingen aktive målere fundet.")
        
        # Tjek målerkonfigurationer
        print("\n=== MÅLERKONFIGURATIONER ===")
        cursor.execute('SELECT * FROM meter_config')
        configs = cursor.fetchall()
        
        if configs:
            for config in configs:
                print(f"ID: {config['id']}, Sensor ID: {config['sensor_id']}, Navn: {config['display_name']}")
                print(f"  Lokation: {config['location']}, Aktiv: {config['is_active']}")
                
                # Tjek om denne måler er i brug
                cursor.execute('SELECT * FROM active_meters WHERE meter_id = %s', (config['sensor_id'],))
                active = cursor.fetchone()
                if active:
                    print(f"  BEMÆRK: Denne måler er i brug af booking {active['booking_id']}")
                else:
                    print(f"  Denne måler er ikke i brug.")
        else:
            print("Ingen målerkonfigurationer fundet.")
        
        # Luk forbindelsen
        cursor.close()
        conn.close()
        print('\nForbindelse lukket.')
    else:
        print('Forbindelse kunne ikke etableres selvom ingen fejl blev rapporteret.')
        
except Error as e:
    print(f'Fejl ved forbindelse til database: {e}')
except Exception as e:
    print(f'Uventet fejl: {e}')
