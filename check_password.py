import os
import mysql.connector
from dotenv import load_dotenv
from mysql.connector import Error
from werkzeug.security import check_password_hash, generate_password_hash

# Indlæs miljøvariabler fra .env filen
load_dotenv()

print('Tjekker password for bruger 41967...')
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
            print(f"Gemt password hash: {user['password']}")
            
            # Tjek om det gemte hash matcher 'Halse'
            test_password = 'Halse'
            if check_password_hash(user['password'], test_password):
                print(f"Password '{test_password}' matcher det gemte hash!")
            else:
                print(f"Password '{test_password}' matcher IKKE det gemte hash.")
                
                # Tjek med lowercase
                test_password_lower = 'halse'
                if check_password_hash(user['password'], test_password_lower):
                    print(f"Password '{test_password_lower}' matcher det gemte hash!")
                else:
                    print(f"Password '{test_password_lower}' matcher IKKE det gemte hash.")
                
                # Generer et nyt hash for 'Halse' og opdater i databasen
                print("\nOpdaterer password hash i databasen...")
                new_hash = generate_password_hash(test_password)
                update_cursor = conn.cursor()
                update_cursor.execute("UPDATE users SET password = %s WHERE id = %s", (new_hash, user['id']))
                conn.commit()
                update_cursor.close()
                print(f"Password hash opdateret for bruger {user['username']} (ID: {user['id']})")
                print(f"Nyt hash: {new_hash}")
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
