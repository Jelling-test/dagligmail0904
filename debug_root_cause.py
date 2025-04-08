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

def debug_complete_flow():
    """Detaljeret fejlsøgningsanalyse af den komplette flow fra app.py"""
    try:
        print("=== DETALJERET FEJLSØGNINGSANALYSE ===")
        
        # Brugerinfo
        booking_number = "41967"  # Brugerens bookingnummer
        print(f"Bookingnummer: {booking_number}")
        
        # Del 1: Tjek om brugeren har en aktiv måler
        print("\n=== DEL 1: TJEK OM BRUGEREN HAR EN AKTIV MÅLER ===")
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = conn.cursor(dictionary=True)
        
        # Hent metainfo om brugeren fra users-tabellen
        cursor.execute("SELECT * FROM users WHERE username = %s", (booking_number,))
        user = cursor.fetchone()
        print(f"Brugerinfo: {user if user else 'Bruger ikke fundet!'}")
        
        # Hent målerdata fra active_meters-tabellen
        cursor.execute(
            'SELECT * FROM active_meters WHERE booking_id = %s',
            (booking_number,)
        )
        meter_data = cursor.fetchone()
        
        if not meter_data:
            print(f"PROBLEM FUNDET: Ingen aktiv måler fundet for bookingnummer {booking_number}!")
            return
            
        print(f"Aktiv måler fundet: {meter_data}")
        
        # Del 2: Validering af målerdata
        print("\n=== DEL 2: VALIDERING AF MÅLERDATA ===")
        meter_id = meter_data['meter_id']
        print(f"Måler-ID: {meter_id}")
        
        try:
            start_value = float(meter_data['start_value'])
            package_size = float(meter_data['package_size'])
            print(f"Start-værdi: {start_value}, Pakke-størrelse: {package_size}")
            
            if package_size <= 0:
                print(f"PROBLEM FUNDET: Pakke-størrelse er {package_size}, hvilket kan forårsage division by zero!")
        except (ValueError, TypeError) as e:
            print(f"PROBLEM FUNDET: Kunne ikke konvertere værdier - {e}")
            return
            
        # Del 3: Hent målerværdi fra Home Assistant
        print("\n=== DEL 3: HENT MÅLERVÆRDI FRA HOME ASSISTANT ===")
        try:
            response = requests.get(
                f"{HASS_URL}/api/states/{meter_id}",
                headers={"Authorization": f"Bearer {HASS_TOKEN}"}
            )
            
            if response.status_code != 200:
                print(f"PROBLEM FUNDET: Kunne ikke hente målerværdi, status: {response.status_code}")
                return
                
            state = response.json()
            print(f"Målerværdi fra Home Assistant: {state}")
            
            if 'state' not in state or not state['state']:
                print("PROBLEM FUNDET: Ingen målerværdi i svaret fra Home Assistant")
                return
                
            current_value = float(state['state'])
            print(f"Nuværende målerværdi: {current_value}")
            
            # Del 4: Beregn forbrug og kontroller måler
            print("\n=== DEL 4: BEREGN FORBRUG OG KONTROLLER MÅLER ===")
            total_usage = current_value - start_value
            if total_usage < 0:
                print(f"BEMÆRK: Negativt forbrug korrigeret til 0 (current: {current_value}, start: {start_value})")
                total_usage = 0
                
            remaining = package_size - total_usage
            if remaining < 0:
                print(f"BEMÆRK: Negative resterende enheder korrigeret til 0 (package: {package_size}, usage: {total_usage})")
                remaining = 0
                
            print(f"Beregnet forbrug: {total_usage}")
            print(f"Resterende enheder: {remaining}")
            
            try:
                percentage = (total_usage / float(package_size)) * 100 if float(package_size) > 0 else 100
                print(f"Procentvis forbrug: {percentage}%")
            except ZeroDivisionError:
                print("PROBLEM FUNDET: Division by zero ved beregning af procentvis forbrug!")
            
            # Del 5: Tjek strømafbryder
            print("\n=== DEL 5: TJEK STRØMAFBRYDER ===")
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
                    print(f"PROBLEM FUNDET: Kunne ikke hente status for strømafbryder, status: {response.status_code}")
            except Exception as e:
                print(f"PROBLEM FUNDET: Fejl ved hentning af strømafbryder status - {e}")
            
            # Del 6: Undersøg check_package_status
            print("\n=== DEL 6: TJEK RESULTAT AF CHECK_PACKAGE_STATUS ===")
            
            # Hent power_events for denne bruger
            cursor.execute(
                '''
                SELECT * FROM power_events 
                WHERE booking_id = %s
                ORDER BY timestamp DESC
                LIMIT 5
                ''',
                (booking_number,)
            )
            
            events = cursor.fetchall()
            if events:
                print(f"Seneste power events for bruger {booking_number}:")
                for event in events:
                    print(f"  {event['timestamp']} - {event['event_type']} - {event['meter_id']} - {event['details']}")
            else:
                print(f"Ingen power events fundet for bruger {booking_number}")
            
            # Konkludér analysefund
            print("\n=== KONKLUSION ===")
            
            if total_usage >= package_size:
                print("1. Pakken er opbrugt - brugeren burde få slukket for strømmen automatisk.")
                if power_switch_state == 'on':
                    print("   PROBLEM FUNDET: Strømafbryderen er stadig tændt selvom pakken er opbrugt!")
                else:
                    print("   Korrekt: Strømafbryderen er slukket.")
            else:
                print(f"1. Pakken er ikke opbrugt (resterende: {remaining})")
                
            if meter_data and user:
                print("2. Brugeren har en korrekt tilknyttet aktiv måler i databasen.")
                print("   PROBLEM: Alligevel omdirigeres brugeren til målervalg-siden!")
            else:
                print("2. Bruger eller målerdata mangler - dette kan være årsagen til omdirigering.")
                
            print("\nMulige årsager til problemet:")
            print("1. Problemer med sessionsdata eller brugerautentificering")
            print("2. Fejl i stroem_dashboard-funktionens logik")
            print("3. Problemer med database-forbindelsen eller -spørgsmålene")
            print("4. En uventet undtagelse der fanges og fører til omdirigering")
            
        except Exception as e:
            print(f"PROBLEM FUNDET: Uventet fejl under analysefasen - {e}")
            
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Generel fejl i analysescript: {e}")

if __name__ == "__main__":
    debug_complete_flow()
