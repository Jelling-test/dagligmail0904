import os
import requests
from dotenv import load_dotenv

# Indlæs miljøvariabler fra .env filen
load_dotenv()

HASS_URL = os.getenv('HASS_URL')
HASS_TOKEN = os.getenv('HASS_TOKEN')

print(f"HASS_URL: {HASS_URL}")
print(f"HASS_TOKEN: {'*' * 10 if HASS_TOKEN else 'Ikke sat'}")

if not HASS_URL or not HASS_TOKEN:
    print("FEJL: HASS_URL eller HASS_TOKEN er ikke sat i .env filen")
    exit(1)

try:
    print(f"\nForsøger at forbinde til Home Assistant på {HASS_URL}...")
    response = requests.get(
        f"{HASS_URL}/api/states",
        headers={"Authorization": f"Bearer {HASS_TOKEN}"},
        timeout=10
    )
    
    if response.status_code == 200:
        print("Forbindelse til Home Assistant oprettet succesfuldt!")
        data = response.json()
        print(f"Modtog {len(data)} enheder fra Home Assistant")
        
        # Vis nogle eksempler på energi/strøm sensorer
        energy_sensors = [entity for entity in data 
                         if entity['entity_id'].startswith('sensor.') 
                         and ('energy' in entity['entity_id'].lower() 
                              or 'power' in entity['entity_id'].lower()
                              or 'obk' in entity['entity_id'].lower())]
        
        print(f"\nFandt {len(energy_sensors)} energi/strøm sensorer:")
        # Vis alle sensorer, ikke kun de første 5
        for i, sensor in enumerate(energy_sensors):
            print(f"{i+1}. {sensor['entity_id']}: {sensor['state']} {sensor['attributes'].get('unit_of_measurement', '')}")
            
        # Test specifikt de sensorer, der bruges i applikationen
        print("\nTest af specifikke sensorer:")
        test_sensors = ["sensor.tester_f42", "sensor.maler_904"]
        for sensor_id in test_sensors:
            normalized_id = sensor_id if sensor_id.startswith('sensor.') else f"sensor.{sensor_id}"
            energy_id = f"{normalized_id}_energy_total" if "_energy_total" not in normalized_id else normalized_id
            
            print(f"\nTester {sensor_id}:")
            # Test uden _energy_total
            try:
                resp = requests.get(
                    f"{HASS_URL}/api/states/{normalized_id}",
                    headers={"Authorization": f"Bearer {HASS_TOKEN}"},
                    timeout=5
                )
                if resp.status_code == 200:
                    data = resp.json()
                    print(f"  - {normalized_id}: {data['state']} {data['attributes'].get('unit_of_measurement', '')}")
                else:
                    print(f"  - {normalized_id}: Ikke fundet (status {resp.status_code})")
            except Exception as e:
                print(f"  - {normalized_id}: Fejl: {e}")
                
            # Test med _energy_total
            if normalized_id != energy_id:
                try:
                    resp = requests.get(
                        f"{HASS_URL}/api/states/{energy_id}",
                        headers={"Authorization": f"Bearer {HASS_TOKEN}"},
                        timeout=5
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        print(f"  - {energy_id}: {data['state']} {data['attributes'].get('unit_of_measurement', '')}")
                    else:
                        print(f"  - {energy_id}: Ikke fundet (status {resp.status_code})")
                except Exception as e:
                    print(f"  - {energy_id}: Fejl: {e}")
    else:
        print(f"FEJL: Kunne ikke forbinde til Home Assistant. Status kode: {response.status_code}")
        print(f"Svar: {response.text}")
        
except requests.exceptions.RequestException as e:
    print(f"FEJL ved forbindelse til Home Assistant: {e}")
except Exception as e:
    print(f"Uventet fejl: {e}")
