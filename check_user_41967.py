import os
import mysql.connector
from dotenv import load_dotenv
from mysql.connector import Error
from werkzeug.security import check_password_hash

# Indlæs miljøvariabler fra .env filen
load_dotenv()

print('Tjekker password hash for bruger 41967...')
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
            print(f"Gemt password: {user['password']}")
            
            # Tjek om det gemte password er et hash
            is_hash = user['password'].startswith('pbkdf2:') or user['password'].startswith('sha256:') or user['password'].startswith('scrypt:')
            
            if is_hash:
                print(f"Password er korrekt gemt som et hash!")
                
                # Tjek om det gemte hash matcher 'Halse'
                test_password = 'Halse'
                if check_password_hash(user['password'], test_password):
                    print(f"Password '{test_password}' matcher det gemte hash!")
                else:
                    print(f"Password '{test_password}' matcher IKKE det gemte hash.")
            else:
                print(f"ADVARSEL: Password er IKKE gemt som et hash, men som ren tekst: {user['password']}")
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
