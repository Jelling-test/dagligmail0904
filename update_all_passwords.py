import os
import mysql.connector
from dotenv import load_dotenv
from mysql.connector import Error
from werkzeug.security import check_password_hash, generate_password_hash

# Indlæs miljøvariabler fra .env filen
load_dotenv()

print('Opdaterer password hash for alle brugere...')
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
        
        # Hent alle brugere
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, username, fornavn, efternavn, password FROM users")
        users = cursor.fetchall()
        
        if users:
            print(f"Fandt {len(users)} brugere i databasen.")
            
            # For hver bruger, opdater password hash
            update_cursor = conn.cursor()
            for user in users:
                user_id = user['id']
                username = user['username']
                efternavn = user['efternavn']
                current_password = user['password']
                
                print(f"\nBruger: {username} (ID: {user_id}), Navn: {user['fornavn']} {efternavn}")
                print(f"Nuværende password/hash: {current_password}")
                
                # Tjek om det nuværende password allerede er et hash
                is_hash = current_password.startswith('pbkdf2:') or current_password.startswith('sha256:') or current_password.startswith('scrypt:')
                
                if is_hash:
                    print(f"Password er allerede et hash, springer over.")
                    continue
                
                # Generer nyt hash baseret på efternavn (som bruges som password)
                new_hash = generate_password_hash(efternavn)
                
                # Opdater i databasen
                update_cursor.execute("UPDATE users SET password = %s WHERE id = %s", (new_hash, user_id))
                conn.commit()
                
                print(f"Password hash opdateret for bruger {username} (ID: {user_id})")
                print(f"Nyt hash baseret på efternavn '{efternavn}': {new_hash}")
            
            update_cursor.close()
            print("\nAlle brugere er blevet opdateret.")
        else:
            print("Ingen brugere fundet i databasen.")
        
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
