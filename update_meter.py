import os
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error
import requests

load_dotenv()

# Hent værdien fra Home Assistant for at være sikker på, at vi har den nyeste værdi
HASS_URL = os.getenv('HASS_URL')
HASS_TOKEN = os.getenv('HASS_TOKEN')

try:
    # Hent den aktuelle værdi fra Home Assistant
    response = requests.get(
        f"{HASS_URL}/api/states/sensor.obkbfbfd7f0_energy_total",
        headers={"Authorization": f"Bearer {HASS_TOKEN}"}
    )
    response.raise_for_status()
    state = response.json()
    current_value = float(state['state'])
    print(f"Aktuel værdi fra Home Assistant: {current_value}")
    
    # Opret forbindelse til databasen
    connection = mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )
    
    if connection.is_connected():
        cursor = connection.cursor()
        
        print("Opdaterer måler for bruger 2...")
        cursor.execute("""
            UPDATE active_meters 
            SET meter_id = 'sensor.obkbfbfd7f0_energy_total', 
                start_value = %s 
            WHERE booking_id = '2'
        """, (current_value,))
        
        connection.commit()
        
        print(f"Måler opdateret. Påvirket rækker: {cursor.rowcount}")
        
        # Vis den opdaterede måler
        cursor.execute("SELECT * FROM active_meters WHERE booking_id = '2'")
        meter = cursor.fetchone()
        if meter:
            print(f"ID: {meter[0]}, Booking ID: {meter[1]}, Måler ID: {meter[2]}, Startværdi: {meter[4]}, Pakkestørrelse: {meter[5]}")
        
except Error as e:
    print(f"Fejl ved opdatering af måler: {e}")
except Exception as e:
    print(f"Generel fejl: {e}")
    
finally:
    if 'connection' in locals() and connection.is_connected():
        cursor.close()
        connection.close()
        print("\nDatabase forbindelse lukket")
