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

def create_email_alerts_table():
    """Opretter email_alerts tabellen, hvis den ikke allerede findes"""
    try:
        # Opret forbindelse til databasen
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        
        cursor = conn.cursor()
        
        # Opret tabellen hvis den ikke findes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_alerts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                meter_id VARCHAR(50) NOT NULL,
                alert_type VARCHAR(50) NOT NULL,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                remaining_units DECIMAL(10, 3),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        print("Email alerts tabellen er oprettet eller eksisterer allerede")
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Fejl under oprettelse af email_alerts tabel: {e}")

if __name__ == "__main__":
    create_email_alerts_table()
