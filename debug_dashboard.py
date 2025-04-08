import os
import mysql.connector
import requests
from dotenv import load_dotenv

# Indlæs miljøvariabler
load_dotenv()

# Hent database og API konfiguration
DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')
HASS_URL = os.getenv('HASS_URL')
HASS_TOKEN = os.getenv('HASS_TOKEN')

def debug_dashboard_flow():
    """Simulerer strømdashboard-funktionen skridt for skridt for at finde fejlen"""
    try:
        print("=== Debug af strømdashboard flow ===")
        
        # 1. Hent brugerinfo
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        
        cursor = conn.cursor(dictionary=True)
        
        # Bruger ID og username
        user_id = 2  # Vi ved dette er brugerens ID
        booking_number = "41967"  # Vi ved dette er brugerens bookingnummer
        
        print(f"\nBruger info - ID: {user_id}, Bookingnummer: {booking_number}")
        
        # 2. Tjek og print præcist hvad app.py's stroem_dashboard funktion ville gøre
        print("\nTrin 1: Henter målerdata...")
        cursor.execute(
            'SELECT meter_id, start_value, package_size FROM active_meters WHERE booking_id = %s',
            (booking_number,)
        )
        meter_data = cursor.fetchone()
        
        print(f"SQL: SELECT meter_id, start_value, package_size FROM active_meters WHERE booking_id = '{booking_number}'")
        print(f"Resultat: {meter_data}")
        
        if not meter_data:
            print("FEJL: Ingen målerdata fundet med dette bookingnummer!")
            return
        
        meter_id = meter_data['meter_id']
        
        # 3. Tjek om vi kan konvertere værdierne korrekt
        print("\nTrin 2: Konverterer værdier...")
        try:
            start_value = float(meter_data['start_value'])
            package_size = float(meter_data['package_size'])
            print(f"start_value: {start_value}, package_size: {package_size}")
        except (ValueError, TypeError) as e:
            print(f"FEJL: Kunne ikke konvertere værdier - {e}")
            return
        
        # 4. Hent målerværdien fra Home Assistant
        print("\nTrin 3: Henter målerværdi fra Home Assistant...")
        try:
            response = requests.get(
                f"{HASS_URL}/api/states/{meter_id}",
                headers={"Authorization": f"Bearer {HASS_TOKEN}"}
            )
            
            if response.status_code != 200:
                print(f"FEJL: Kunne ikke hente målerværdi, status: {response.status_code}")
                return
                
            state = response.json()
            print(f"Målerværdi rådata: {state}")
            
            if 'state' not in state or not state['state']:
                print("FEJL: Ingen målerværdi i svaret fra Home Assistant")
                return
                
            current_value = float(state['state'])
            print(f"current_value: {current_value}")
            
            # 5. Beregn forbrug og resterende enheder
            total_usage = current_value - start_value
            if total_usage < 0:
                total_usage = 0
                
            remaining = package_size - total_usage
            if remaining < 0:
                remaining = 0
                
            if float(package_size) > 0:
                percentage = (total_usage / float(package_size)) * 100
            else:
                percentage = 100
                
            if percentage > 100:
                percentage = 100
                
            print(f"\nBeregnet forbrug: {total_usage:.3f}")
            print(f"Resterende enheder: {remaining:.3f}")
            print(f"Procentvist forbrug: {percentage:.1f}%")
            
            # 6. Tjek strømafbryderens status
            print("\nTrin 4: Tjekker strømafbryderens status...")
            
            try:
                meter_parts = meter_id.split('_')
                device_id = meter_parts[0].replace('sensor.', '')
                switch_id = f"switch.{device_id}_0"
                
                response = requests.get(
                    f"{HASS_URL}/api/states/{switch_id}",
                    headers={"Authorization": f"Bearer {HASS_TOKEN}"}
                )
                
                if response.status_code == 200:
                    switch_data = response.json()
                    power_switch_state = switch_data['state']
                    print(f"Strømafbryder status: {power_switch_state}")
                else:
                    print(f"Kunne ikke hente status for strømafbryder, status: {response.status_code}")
            except Exception as e:
                print(f"Fejl ved hentning af strømafbryderens status: {e}")
                
            print("\nKonklusion: Strømdashboard burde vises korrekt uden fejl!")
                
        except Exception as e:
            print(f"FEJL: Uventet fejl under hentning af målerværdi - {e}")
            
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Generel fejl: {e}")

if __name__ == "__main__":
    debug_dashboard_flow()
