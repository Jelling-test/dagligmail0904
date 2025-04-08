import os
import mysql.connector
import requests
from datetime import datetime
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

class MockUser:
    def __init__(self, username, id):
        self.username = username
        self.id = id

def simulate_stroem_dashboard():
    """Simulerer hele stroem_dashboard funktionen trin for trin"""
    try:
        # Simulerer login-bruger
        current_user = MockUser("41967", 2)  # Brugerens username og id
        
        print("=== SIMULERING AF STRØMDASHBOARD FUNKTION ===")
        print(f"Bruger: username={current_user.username}, id={current_user.id}")
        
        # Trin 1: Hent målerdata
        print("\n=== TRIN 1: HENT MÅLERDATA ===")
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute(
            'SELECT meter_id, start_value, package_size FROM active_meters WHERE booking_id = %s',
            (current_user.username,)
        )
        meter_data = cursor.fetchone()
        
        if not meter_data:
            print("STOP: Ingen målerdata fundet - bruger ville blive sendt til select_meter.html")
            return
            
        print(f"Målerdata fundet: {meter_data}")
        
        # Trin 2: Meter_id og værdier
        print("\n=== TRIN 2: METER_ID OG VÆRDIER ===")
        meter_id = meter_data['meter_id']
        print(f"Meter ID: {meter_id}")
        
        try:
            start_value = float(meter_data['start_value'])
            package_size = float(meter_data['package_size'])
            print(f"Start værdi: {start_value}, Pakke størrelse: {package_size}")
            
            if package_size <= 0:
                print("BEMÆRK: Pakke størrelse er 0 eller mindre, dette kan forårsage division by zero")
        except (ValueError, TypeError) as e:
            print(f"STOP: Kunne ikke konvertere værdier - {e}")
            return
            
        # Trin 3: Hent måler værdi fra Home Assistant
        print("\n=== TRIN 3: HENT MÅLERVÆRDI FRA HOME ASSISTANT ===")
        try:
            response = requests.get(
                f"{HASS_URL}/api/states/{meter_id}",
                headers={"Authorization": f"Bearer {HASS_TOKEN}"}
            )
            print(f"Response status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"STOP: Kunne ikke hente målerværdi, status: {response.status_code}")
                return
                
            state = response.json()
            print(f"Målerværdi state: {state}")
            
            if 'state' not in state or not state['state']:
                print("STOP: Ingen målerværdi i svaret fra Home Assistant")
                return
                
            current_value = float(state['state'])
            print(f"Current value: {current_value}")
        except Exception as e:
            print(f"STOP: Fejl under hentning af målerværdi - {e}")
            return
            
        # Trin 4: Beregninger
        print("\n=== TRIN 4: BEREGNINGER ===")
        total_usage = current_value - start_value
        if total_usage < 0:
            print(f"BEMÆRK: Negativt forbrug justeret til 0 (current: {current_value}, start: {start_value})")
            total_usage = 0
            
        remaining = package_size - total_usage
        if remaining < 0:
            print(f"BEMÆRK: Negative enheder justeret til 0 (package: {package_size}, usage: {total_usage})")
            remaining = 0
            
        print(f"Total forbrug: {total_usage}")
        print(f"Resterende enheder: {remaining}")
        
        if package_size > 0:
            percentage = (total_usage / package_size) * 100
        else:
            percentage = 100
            
        if percentage > 100:
            percentage = 100
            
        print(f"Procentvist forbrug: {percentage}%")
        
        # Trin 5: Hent status på strømafbryder
        print("\n=== TRIN 5: STRØMAFBRYDER STATUS ===")
        power_switch_state = "unknown"
        try:
            meter_parts = meter_id.split('_')
            device_id = meter_parts[0].replace('sensor.', '')
            switch_id = f"switch.{device_id}_0"
            print(f"Switch ID: {switch_id}")
            
            response = requests.get(
                f"{HASS_URL}/api/states/{switch_id}",
                headers={"Authorization": f"Bearer {HASS_TOKEN}"}
            )
            
            if response.status_code == 200:
                switch_data = response.json()
                power_switch_state = switch_data['state']
                print(f"Strømafbryder status: {power_switch_state}")
            else:
                print(f"Kunne ikke hente switch status, status: {response.status_code}")
        except Exception as e:
            print(f"Fejl ved hentning af switch status: {e}")
            
        # Konklusion
        print("\n=== KONKLUSION ===")
        print("Alle trin gennemført uden fejl - brugeren burde se strømdashboard-siden")
        print(f"- Måler ID: {meter_id}")
        print(f"- Nuværende værdi: {current_value}")
        print(f"- Start værdi: {start_value}")
        print(f"- Forbrug: {total_usage}")
        print(f"- Resterende: {remaining}")
        print(f"- Procent: {percentage}%")
        print(f"- Strømafbryder: {power_switch_state}")
        
        # Ekstra debug: Test om den returnerede template har de forventede data
        print("\nTemplate ville indeholde følgende data:")
        format_number = lambda num: "{:,.3f}".format(num).replace(",", "X").replace(".", ",").replace("X", ".")
        print(f"- current_value: {format_number(current_value)}")
        print(f"- start_value: {format_number(start_value)}")
        print(f"- total_usage: {format_number(total_usage)}")
        print(f"- remaining: {format_number(remaining)}")
        print(f"- percentage: {int(percentage)}")
        print(f"- power_switch_state: {power_switch_state}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"GENEREL FEJL i simulering: {e}")

if __name__ == "__main__":
    simulate_stroem_dashboard()
