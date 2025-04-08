import os
import mysql.connector
from dotenv import load_dotenv
from mysql.connector import Error

# Indlæs miljøvariabler fra .env filen
load_dotenv()

print('Forsøger at forbinde til database...')
print(f"DB_HOST: {os.getenv('DB_HOST')}")
print(f"DB_USER: {os.getenv('DB_USER')}")
print(f"DB_NAME: {os.getenv('DB_NAME')}")

try:
    # Opret forbindelse til databasen
    conn = mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )
    
    if conn.is_connected():
        print('Forbindelse oprettet succesfuldt!')
        
        # Hent og vis alle målerkonfigurationer
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute('SELECT * FROM meter_config')
        meter_configs = cursor.fetchall()
        
        print(f"\nMålerkonfigurationer i databasen ({len(meter_configs)} rækker):")
        for i, config in enumerate(meter_configs):
            print(f"{i+1}. ID: {config['id']}, Sensor ID: {config['sensor_id']}, "
                  f"Display Name: {config.get('display_name', 'N/A')}, "
                  f"Energy Sensor ID: {config.get('energy_sensor_id', 'N/A')}, "
                  f"Is Active: {config.get('is_active', 'N/A')}")
        
        # Luk forbindelsen
        cursor.close()
        conn.close()
        print('\nForbindelse lukket.')
    else:
        print('Forbindelse kunne ikke etableres selvom ingen fejl blev rapporteret.')
        
except Error as e:
    print(f'Fejl ved forbindelse til database: {e}')
    
    # Mere detaljeret fejlinfo
    if hasattr(e, 'errno'):
        if e.errno == 2003:
            print(f"FEJL: Kunne ikke forbinde til MySQL server på '{os.getenv('DB_HOST')}' - kontroller at serveren kører og er tilgængelig.")
        elif e.errno == 1045:
            print(f"FEJL: Adgang nægtet for bruger '{os.getenv('DB_USER')}' - kontroller brugernavn og adgangskode.")
        elif e.errno == 1049:
            print(f"FEJL: Databasen '{os.getenv('DB_NAME')}' eksisterer ikke - kontroller databasenavnet.")
        else:
            print(f"FEJL: MySQL fejlkode {e.errno}: {e}")
except Exception as e:
    print(f'Uventet fejl: {e}')
