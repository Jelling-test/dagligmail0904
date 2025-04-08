import os
import mysql.connector
import requests
from datetime import datetime
from dotenv import load_dotenv
import traceback

# Indlæs miljøvariabler
load_dotenv()

# Hent database og API konfiguration
DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')
HASS_URL = os.getenv('HASS_URL')
HASS_TOKEN = os.getenv('HASS_TOKEN')

def format_number(num):
    return "{:,.3f}".format(num).replace(",", "X").replace(".", ",").replace("X", ".")

def find_problem():
    """Simulerer stroem_dashboard funktionen trin for trin for at finde den præcise fejl"""
    try:
        print("\n===== START PROBLEM ANALYSE =====")
        
        # Trin 1: Hent målerdata
        print("\nTRIN 1: Hent målerdata")
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = conn.cursor(dictionary=True)
        
        username = "41967"  # Brugerens username
        cursor.execute(
            'SELECT meter_id, start_value, package_size FROM active_meters WHERE booking_id = %s',
            (username,)
        )
        meter_data = cursor.fetchone()
        print(f"Målerdata: {meter_data}")
        
        if not meter_data:
            print("RESULTAT: Ingen målerdata fundet - bruger bliver sendt til select_meter.html")
            return
            
        # Trin 2: Konverter værdier
        print("\nTRIN 2: Konverter værdier")
        try:
            meter_id = meter_data['meter_id']
            print(f"Meter ID: {meter_id}")
            
            start_value = float(meter_data['start_value'])
            print(f"Start værdi: {start_value}")
            
            package_size = float(meter_data['package_size'])
            print(f"Pakke størrelse: {package_size}")
            if package_size <= 0:
                package_size = 0.001  # Sætter en minimal værdi for at undgå division by zero
                print(f"Justeret pakke størrelse til {package_size}")
        except (ValueError, TypeError) as e:
            print(f"RESULTAT: Konverteringsfejl: {e} - bruger bliver sendt til select_meter.html")
            return
            
        # Trin 3: Hent målerværdi fra Home Assistant
        print("\nTRIN 3: Hent målerværdi fra Home Assistant")
        try:
            response = requests.get(
                f"{HASS_URL}/api/states/{meter_id}",
                headers={"Authorization": f"Bearer {HASS_TOKEN}"}
            )
            print(f"Response status: {response.status_code}")
            
            response.raise_for_status()
            state = response.json()
            print(f"Målerværdi state: {state['state']}")
            
            if 'state' not in state or not state['state']:
                print("RESULTAT: Ingen state i Home Assistant svaret - bruger bliver sendt til select_meter.html")
                return
        except Exception as e:
            print(f"RESULTAT: Home Assistant API fejl: {e} - bruger bliver sendt til select_meter.html")
            return
            
        # Trin 4: Konverter målerværdi
        print("\nTRIN 4: Konverter målerværdi")
        try:
            current_value = float(state['state'])
            print(f"Nuværende målerværdi: {current_value}")
        except (ValueError, TypeError) as e:
            print(f"RESULTAT: Konverteringsfejl målerværdi: {e} - bruger bliver sendt til select_meter.html")
            return
            
        # Trin 5: Beregn forbrug og resterende enheder
        print("\nTRIN 5: Beregn forbrug og resterende enheder")
        total_usage = current_value - start_value
        if total_usage < 0:
            print(f"Justerer negativt forbrug fra {total_usage} til 0")
            total_usage = 0
        print(f"Total forbrug: {total_usage}")
        
        remaining = package_size - total_usage
        print(f"Resterende enheder: {remaining}")
        
        if remaining < 0:
            print(f"Justerer negative enheder fra {remaining} til 0")
            remaining = 0
        
        print("\nTRIN 6: Beregn procentvis forbrug")
        try:
            if float(package_size) > 0:
                percentage = (total_usage / float(package_size)) * 100
                print(f"Procentvis forbrug: {percentage}%")
            else:
                percentage = 100
                print(f"Pakke størrelse er 0, sætter procent til 100%")
                
            if percentage > 100:
                print(f"Justerer procent fra {percentage}% til 100%")
                percentage = 100
        except Exception as e:
            print(f"Fejl ved beregning af procent: {e}")
            
        # Trin 7: Generér template data
        print("\nTRIN 7: Generér template data")
        try:
            template_data = {
                'current_value': format_number(current_value),
                'start_value': format_number(start_value),
                'total_usage': format_number(total_usage),
                'remaining': format_number(remaining),
                'meter_id': meter_id,
                'unit_text': 'enheder',
                'percentage': int(percentage),
                'package_size': int(package_size),  # <-- POTENTIELT PROBLEM HER!
                'power_switch_state': 'on',
                'updated': datetime.now().strftime('%H:%M:%S')
            }
            print(f"Template data: {template_data}")
            print(f"\nKRITISK VÆRDI: package_size = {int(package_size)}")
            
            # Test hvad der sker hvis package_size er mindre end 1
            if package_size < 1:
                print(f"BEMÆRK: package_size er mindre end 1 ({package_size}), og bliver konverteret til {int(package_size)} via int()")
                print(f"Dette kan være årsagen til problemet, da {int(package_size)} = 0")
        except Exception as e:
            print(f"RESULTAT: Fejl ved generering af template data: {e}")
            print(traceback.format_exc())
            return
            
        print("\n===== KONKLUSION =====")
        print("MULIGT PROBLEM FUNDET: Når pakke størrelsen er mindre end 1 (som 0.003), bliver den afrundet til 0 via int()")
        print("Dette kan forårsage problemer i template rendering eller beregninger, der forventer en package_size > 0")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Uventet fejl: {e}")
        print(traceback.format_exc())

if __name__ == "__main__":
    find_problem()
