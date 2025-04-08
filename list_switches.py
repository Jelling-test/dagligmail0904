import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Home Assistant configuration
HASS_URL = os.getenv('HASS_URL')
HASS_TOKEN = os.getenv('HASS_TOKEN')

def get_switches():
    try:
        # Get all entities from Home Assistant
        response = requests.get(
            f"{HASS_URL}/api/states",
            headers={"Authorization": f"Bearer {HASS_TOKEN}"}
        )
        response.raise_for_status()
        all_entities = response.json()
        
        # Find all switches related to our power meters
        switches = []
        for entity in all_entities:
            if entity['entity_id'].startswith('switch.') and 'obk' in entity['entity_id'].lower():
                switches.append({
                    'id': entity['entity_id'],
                    'state': entity['state'],
                    'attributes': entity['attributes']
                })
        
        print("\nTilgængelige switches i Home Assistant:")
        print("-" * 100)
        if switches:
            for switch in switches:
                print(f"Switch ID: {switch['id']}")
                print(f"Tilstand: {switch['state']}")
                print(f"Attributter: {switch['attributes']}")
                print("-" * 100)
        else:
            print("Ingen switches fundet for strømmålere.")
            
        # Se også efter andre enheder, der kan tændes/slukkes
        relays = []
        for entity in all_entities:
            if 'obk' in entity['entity_id'].lower() and 'relay' in entity['entity_id'].lower():
                relays.append({
                    'id': entity['entity_id'],
                    'state': entity['state'],
                    'attributes': entity['attributes']
                })
        
        if relays:
            print("\nRelay-enheder fundet:")
            print("-" * 100)
            for relay in relays:
                print(f"Relay ID: {relay['id']}")
                print(f"Tilstand: {relay['state']}")
                print(f"Attributter: {relay['attributes']}")
                print("-" * 100)
        
    except Exception as e:
        print(f"Fejl ved hentning af data fra Home Assistant: {e}")

if __name__ == '__main__':
    get_switches()
