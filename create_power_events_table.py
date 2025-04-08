import os
import mysql.connector
from dotenv import load_dotenv

# Indlæs miljøvariabler
load_dotenv()

# Hent database konfiguration
DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')

def create_power_events_table():
    """Opret power_events tabel til at logge strømhændelser"""
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        
        cursor = conn.cursor()
        
        # Opret tabellen hvis den ikke findes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS power_events (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                event_type ENUM('manual_power_on', 'manual_power_off', 'auto_power_off', 'auto_power_on') NOT NULL,
                meter_id VARCHAR(255) NOT NULL,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        print("Power events tabel oprettet eller findes allerede")
        
        cursor.close()
        conn.close()
        
    except mysql.connector.Error as e:
        print(f"Fejl ved oprettelse af power_events tabel: {e}")

if __name__ == "__main__":
    create_power_events_table()
