import os
from mysql.connector import connect, Error
from dotenv import load_dotenv

# Indlæs miljøvariabler
load_dotenv()

# Database forbindelsesparametre
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', 'stromstyring')

def create_meter_config_table():
    try:
        # Opret forbindelse til databasen
        conn = connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        
        cursor = conn.cursor()
        
        # Opret meter_config tabel
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS meter_config (
            id INT AUTO_INCREMENT PRIMARY KEY,
            sensor_id VARCHAR(100) NOT NULL,
            display_name VARCHAR(100) NOT NULL,
            location VARCHAR(255),
            is_active BOOLEAN DEFAULT 1,
            energy_sensor_id VARCHAR(100),
            power_switch_id VARCHAR(100),
            UNIQUE KEY (sensor_id)
        )
        ''')
        
        print("meter_config tabel oprettet eller eksisterer allerede")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True
    except Error as e:
        print(f"Fejl ved oprettelse af tabel: {e}")
        return False

if __name__ == "__main__":
    create_meter_config_table()
