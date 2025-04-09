import os
import mysql.connector
from mysql.connector import Error, pooling
from dotenv import load_dotenv

load_dotenv()

# Brug samme funktion som app.py til at oprette databaseforbindelse
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )
        return conn
    except Error as e:
        print(f"Fejl ved forbindelse til database: {e}")
        return None

def check_database():
    conn = get_db_connection()
    if not conn:
        print("Kunne ikke oprette forbindelse til databasen")
        return
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Hent data for bruger 43495
        print("\n===== BRUGER 43495 DATA =====")
        
        # Aktive målere
        cursor.execute("SELECT * FROM active_meters WHERE booking_id='43495'")
        active_meters = cursor.fetchall()
        if active_meters:
            print("\nAktive målere for 43495:")
            for meter in active_meters:
                print(f"ID: {meter['id']}, Måler ID: {meter['meter_id']}, Startværdi: {meter['start_value']}, Pakke størrelse: {meter['package_size']}")
        else:
            print("Ingen aktive målere fundet for 43495")
        
        # Måler konfiguration
        if active_meters:
            meter_id = active_meters[0]['meter_id']
            cursor.execute("SELECT * FROM meter_config WHERE sensor_id=%s", (meter_id,))
            meter_config = cursor.fetchone()
            if meter_config:
                print(f"\nMåler konfiguration for {meter_id}:")
                print(f"ID: {meter_config['id']}, Sensor ID: {meter_config['sensor_id']}, Visningsnavn: {meter_config['display_name']}, Power Switch ID: {meter_config['power_switch_id']}")
            else:
                print(f"Ingen måler konfiguration fundet for {meter_id}")
        
        # Hent data for bruger 41967
        print("\n\n===== BRUGER 41967 DATA =====")
        
        # Aktive målere
        cursor.execute("SELECT * FROM active_meters WHERE booking_id='41967'")
        active_meters = cursor.fetchall()
        if active_meters:
            print("\nAktive målere for 41967:")
            for meter in active_meters:
                print(f"ID: {meter['id']}, Måler ID: {meter['meter_id']}, Startværdi: {meter['start_value']}, Pakke størrelse: {meter['package_size']}")
        else:
            print("Ingen aktive målere fundet for 41967")
        
        # Måler konfiguration
        if active_meters:
            meter_id = active_meters[0]['meter_id']
            cursor.execute("SELECT * FROM meter_config WHERE sensor_id=%s", (meter_id,))
            meter_config = cursor.fetchone()
            if meter_config:
                print(f"\nMåler konfiguration for {meter_id}:")
                print(f"ID: {meter_config['id']}, Sensor ID: {meter_config['sensor_id']}, Visningsnavn: {meter_config['display_name']}, Power Switch ID: {meter_config['power_switch_id']}")
            else:
                print(f"Ingen måler konfiguration fundet for {meter_id}")
        
        # Tjek alle meter_config indstillinger
        print("\n\n===== ALLE MÅLERE I METER_CONFIG =====")
        cursor.execute("SELECT * FROM meter_config WHERE sensor_id='F42' OR sensor_id='obkBFBFD7F0' OR sensor_id LIKE '%obk%'")
        all_configs = cursor.fetchall()
        if all_configs:
            for config in all_configs:
                print(f"ID: {config['id']}, Sensor ID: {config['sensor_id']}, Visningsnavn: {config['display_name']}, Power Switch ID: {config['power_switch_id']}")
        else:
            print("Ingen relevante målere fundet i meter_config")
            
    except Error as e:
        print(f"Fejl ved forespørgsel til database: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
            print("\nDatabaseforbindelse lukket.")

if __name__ == "__main__":
    check_database()
