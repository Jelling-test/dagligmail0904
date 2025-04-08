import os
import mysql.connector
from dotenv import load_dotenv
from mysql.connector import Error
import binascii

# Indlæs miljøvariabler fra .env filen
load_dotenv()

print('Tjekker præcist password for bruger 41967...')
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
        
        cursor = conn.cursor(dictionary=True)
        
        # Hent brugerdata for 41967
        cursor.execute("SELECT id, username, fornavn, efternavn, password FROM users WHERE username = '41967'")
        user = cursor.fetchone()
        
        if user:
            print(f"Bruger fundet: ID {user['id']}, Navn: {user['fornavn']} {user['efternavn']}")
            
            # Vis det præcise password med hex-koder for at se skjulte tegn
            password = user['password']
            print(f"Gemt password (rå): '{password}'")
            print(f"Gemt password (hex): {binascii.hexlify(password.encode()).decode()}")
            print(f"Længde af password: {len(password)}")
            
            # Vis også det forventede password (Halse)
            expected = "Halse"
            print(f"Forventet password (rå): '{expected}'")
            print(f"Forventet password (hex): {binascii.hexlify(expected.encode()).decode()}")
            print(f"Længde af forventet password: {len(expected)}")
            
            # Sammenlign direkte
            print(f"Er passwords ens? {password == expected}")
            print(f"Er passwords ens (case-insensitive)? {password.lower() == expected.lower()}")
            
            # Tjek om det er et hash
            is_hash = password.startswith('pbkdf2:') or password.startswith('sha256:') or password.startswith('scrypt:')
            print(f"Er password et hash? {is_hash}")
            
            if is_hash:
                from werkzeug.security import check_password_hash
                print(f"Hash check med 'Halse': {check_password_hash(password, 'Halse')}")
                print(f"Hash check med 'halse': {check_password_hash(password, 'halse')}")
        else:
            print("Bruger med username 41967 blev ikke fundet.")
        
        # Luk forbindelsen
        cursor.close()
        conn.close()
        print('\nForbindelse lukket.')
    else:
        print('Forbindelse kunne ikke etableres selvom ingen fejl blev rapporteret.')
        
except Error as e:
    print(f'Fejl ved forbindelse til database: {e}')
except Exception as e:
    print(f'Uventet fejl: {e}')
