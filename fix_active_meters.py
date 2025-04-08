import os
import mysql.connector
from dotenv import load_dotenv
from mysql.connector import Error

# Indlæs miljøvariabler fra .env filen
load_dotenv()

print('Rydder op i aktive målere...')

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
        
        # Find aktive målere med ugyldige bookinger
        print("\nSøger efter aktive målere med ugyldige bookinger...")
        cursor.execute('''
            SELECT am.* 
            FROM active_meters am
            LEFT JOIN aktive_bookinger ab ON am.booking_id = ab.booking_id
            WHERE ab.booking_id IS NULL
        ''')
        
        invalid_meters = cursor.fetchall()
        
        if invalid_meters:
            print(f"Fandt {len(invalid_meters)} aktive målere med ugyldige bookinger:")
            
            for meter in invalid_meters:
                print(f"ID: {meter['id']}, Booking ID: {meter['booking_id']}, Måler ID: {meter['meter_id']}")
                
                # Spørg om bekræftelse før sletning
                print(f"Sletter aktiv måler med ID {meter['id']}...")
                
                delete_cursor = conn.cursor()
                delete_cursor.execute('DELETE FROM active_meters WHERE id = %s', (meter['id'],))
                delete_cursor.close()
                
                print(f"Aktiv måler med ID {meter['id']} er blevet slettet.")
            
            # Commit ændringer
            conn.commit()
            print("\nÆndringer gemt i databasen.")
        else:
            print("Ingen aktive målere med ugyldige bookinger fundet.")
        
        # Luk forbindelsen
        cursor.close()
        conn.close()
        print('\nForbindelse lukket.')
    else:
        print('Forbindelse kunne ikke etableres selvom ingen fejl blev rapporteret.')
        
except Error as e:
    print(f'Fejl ved forbindelse til database: {e}')
    if conn:
        conn.rollback()
        print("Ændringer rullet tilbage.")
except Exception as e:
    print(f'Uventet fejl: {e}')
    if conn:
        conn.rollback()
        print("Ændringer rullet tilbage.")
