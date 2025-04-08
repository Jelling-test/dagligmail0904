import os
from dotenv import load_dotenv
import requests
import json

load_dotenv()

HASS_URL = os.getenv('HASS_URL')
HASS_TOKEN = os.getenv('HASS_TOKEN')

def get_meters():
    response = requests.get(
        f"{HASS_URL}/api/states",
        headers={"Authorization": f"Bearer {HASS_TOKEN}"}
    )
    response.raise_for_status()
    all_entities = response.json()
    
    # Print alle enheder der har med strøm at gøre
    for entity in all_entities:
        if 'power' in entity['entity_id'] or 'energy' in entity['entity_id']:
            print("\nEntity ID:", entity['entity_id'])
            print("State:", entity['state'])
            print("Attributes:", json.dumps(entity['attributes'], indent=2))
            print("-" * 50)

if __name__ == '__main__':
    get_meters()
