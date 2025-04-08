import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Home Assistant configuration
HASS_URL = os.getenv('HASS_URL')
HASS_TOKEN = os.getenv('HASS_TOKEN')

def get_sensors():
    try:
        # Get all sensors from Home Assistant
        response = requests.get(
            f"{HASS_URL}/api/states",
            headers={"Authorization": f"Bearer {HASS_TOKEN}"}
        )
        response.raise_for_status()
        all_entities = response.json()
        
        # Find all obk sensors
        sensors = []
        for entity in all_entities:
            if entity['entity_id'].startswith('sensor.obk'):
                sensors.append({
                    'id': entity['entity_id'],
                    'state': entity['state'],
                    'unit': entity['attributes'].get('unit_of_measurement', '')
                })
        
        # Sort by ID
        sensors.sort(key=lambda x: x['id'])
        
        # Print all sensors
        print("\nAlle sensorer fra Home Assistant:")
        print("-" * 100)
        print(f"{'Sensor ID':<60} {'Værdi':<20} {'Enhed':<10}")
        print("-" * 100)
        for sensor in sensors:
            print(f"{sensor['id']:<60} {sensor['state']:<20} {sensor['unit']:<10}")
            
    except Exception as e:
        print(f"Fejl ved hentning af data: {str(e)}")

if __name__ == '__main__':
    get_sensors()
