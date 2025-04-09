import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()

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

def check_specific_data():
    conn = get_db_connection()
    if not conn:
        print("Kunne ikke oprette forbindelse til databasen")
        return
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Tjek data for sensor.f42
        print("\n===== DATA FOR SENSOR.F42 =====")
        cursor.execute("SELECT * FROM meter_config WHERE sensor_id='sensor.f42'")
        config = cursor.fetchone()
        if config:
            print(f"Sensor ID: {config['sensor_id']}")
            print(f"Display Name: {config['display_name']}")
            print(f"Power Switch ID: {config['power_switch_id']}")
        else:
            print("Ingen konfiguration fundet for sensor.f42")
            
        # Tjek data for obkBFBFD7F0
        print("\n===== DATA FOR obkBFBFD7F0 =====")
        cursor.execute("SELECT * FROM meter_config WHERE sensor_id='sensor.obkbfbfd7f0'")
        config = cursor.fetchone()
        if config:
            print(f"Sensor ID: {config['sensor_id']}")
            print(f"Display Name: {config['display_name']}")
            print(f"Power Switch ID: {config['power_switch_id']}")
        else:
            print("Ingen konfiguration fundet for sensor.obkbfbfd7f0")
            
        # Aktive målere for bruger 43495
        print("\n===== AKTIVE MÅLERE FOR BRUGER 43495 =====")
        cursor.execute("SELECT * FROM active_meters WHERE booking_id='43495'")
        meters = cursor.fetchall()
        for meter in meters:
            print(f"Måler ID: {meter['meter_id']}")
            print(f"Start værdi: {meter['start_value']}")
            print(f"Pakke størrelse: {meter['package_size']}")
            print(f"Oprettet: {meter['created_at']}")
            
        # Aktive målere for bruger 41967
        print("\n===== AKTIVE MÅLERE FOR BRUGER 41967 =====")
        cursor.execute("SELECT * FROM active_meters WHERE booking_id='41967'")
        meters = cursor.fetchall()
        for meter in meters:
            print(f"Måler ID: {meter['meter_id']}")
            print(f"Start værdi: {meter['start_value']}")
            print(f"Pakke størrelse: {meter['package_size']}")
            print(f"Oprettet: {meter['created_at']}")
        
    except Error as e:
        print(f"Fejl ved forespørgsel til database: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
            print("\nDatabaseforbindelse lukket.")

if __name__ == "__main__":
    check_specific_data()
