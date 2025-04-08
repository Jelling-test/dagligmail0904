import os
import mysql.connector
from dotenv import load_dotenv
from mysql.connector import Error

# Indlæs miljøvariabler fra .env filen
load_dotenv()

print('Rydder op i forkert tildelte målere...')

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
        cursor = conn.cursor(dictionary=True)
        
        # Fjern målere tildelt til admin-brugeren "peter"
        cursor.execute('DELETE FROM active_meters WHERE booking_id = %s', ('peter',))
        
        affected_rows = cursor.rowcount
        print(f"Fjernet {affected_rows} måler(e) tildelt til admin-brugeren 'peter'")
        
        # Commit ændringer
        conn.commit()
        
        # Tjek om der er andre målere med ugyldige bookinger
        cursor.execute('''
            SELECT am.* 
            FROM active_meters am
            LEFT JOIN aktive_bookinger ab ON am.booking_id = ab.booking_id
            WHERE ab.booking_id IS NULL
        ''')
        
        invalid_meters = cursor.fetchall()
        
        if invalid_meters:
            print(f"\nFandt {len(invalid_meters)} andre aktive målere med ugyldige bookinger:")
            
            for meter in invalid_meters:
                print(f"ID: {meter['id']}, Booking ID: {meter['booking_id']}, Måler ID: {meter['meter_id']}")
                
                # Slet målere med ugyldige bookinger
                delete_cursor = conn.cursor()
                delete_cursor.execute('DELETE FROM active_meters WHERE id = %s', (meter['id'],))
                delete_cursor.close()
                
                print(f"Aktiv måler med ID {meter['id']} er blevet slettet.")
            
            # Commit ændringer
            conn.commit()
        else:
            print("\nIngen andre aktive målere med ugyldige bookinger fundet.")
        
        # Tjek alle målerkonfigurationer for at sikre, at de er korrekt indstillet
        cursor.execute('SELECT * FROM meter_config')
        configs = cursor.fetchall()
        
        print("\n=== MÅLERKONFIGURATIONER ===")
        for config in configs:
            print(f"ID: {config['id']}, Sensor ID: {config['sensor_id']}, Navn: {config['display_name']}")
            print(f"  Lokation: {config['location']}, Aktiv: {config['is_active']}")
        
        # Luk forbindelsen
        cursor.close()
        conn.close()
        print('\nForbindelse lukket.')
    else:
        print('Forbindelse kunne ikke etableres selvom ingen fejl blev rapporteret.')
        
except Error as e:
    print(f'Fejl ved forbindelse til database: {e}')
    if 'conn' in locals() and conn.is_connected():
        conn.rollback()
        print("Ændringer rullet tilbage.")
except Exception as e:
    print(f'Uventet fejl: {e}')
    if 'conn' in locals() and conn.is_connected():
        conn.rollback()
        print("Ændringer rullet tilbage.")
