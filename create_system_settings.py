import mysql.connector
import os
from dotenv import load_dotenv

# Indlæs miljøvariabler fra .env filen
load_dotenv()

def create_system_settings():
    """Opret system_settings tabel og indsæt standardindstillinger"""
    
    try:
        # Opret forbindelse til databasen
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )
        
        cursor = connection.cursor()
        
        # Opret system_settings tabel
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_settings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            setting_key VARCHAR(50) NOT NULL UNIQUE,
            value TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        ''')
        
        # Definer standardindstillinger
        default_settings = [
            ('unit_text', 'enheder', 'Tekst der vises som enhed for strømmålinger'),
            ('timestamp_format', '%H:%M:%S', 'Format for tidsstempel på dashboardet'),
        ]
        
        # Indsæt standardindstillinger (hvis de ikke allerede eksisterer)
        for key, value, description in default_settings:
            cursor.execute('''
            INSERT IGNORE INTO system_settings (setting_key, value, description)
            VALUES (%s, %s, %s)
            ''', (key, value, description))
        
        connection.commit()
        print("System_settings tabel oprettet og indstillinger indsat!")
        
        # Vis de oprettede indstillinger
        cursor.execute("SELECT * FROM system_settings")
        for row in cursor.fetchall():
            print(f"Setting: {row[1]}, Value: {row[2]}")
        
    except mysql.connector.Error as error:
        print(f"Fejl ved oprettelse af system_settings: {error}")
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()
            print("Database-forbindelse lukket.")

if __name__ == "__main__":
    create_system_settings()
