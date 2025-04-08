import os
import mysql.connector
from dotenv import load_dotenv
from mysql.connector import Error

# Indlæs miljøvariabler fra .env filen
load_dotenv()

print('Tester login-relaterede tabeller...')
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
        
        # Test forbindelsen ved at udføre forespørgsler på login-relaterede tabeller
        cursor = conn.cursor()
        
        # Test 1: Tjek om aktive_bookinger tabellen eksisterer
        try:
            cursor.execute("SHOW TABLES LIKE 'aktive_bookinger'")
            result = cursor.fetchone()
            if result:
                print("Tabellen 'aktive_bookinger' findes i databasen.")
                
                # Tjek indhold i aktive_bookinger
                cursor.execute("SELECT COUNT(*) FROM aktive_bookinger")
                count = cursor.fetchone()[0]
                print(f"Antal rækker i aktive_bookinger: {count}")
                
                # Vis eksempler på bookinger
                if count > 0:
                    cursor.execute("SELECT booking_id, fornavn, efternavn FROM aktive_bookinger LIMIT 5")
                    bookings = cursor.fetchall()
                    print("Eksempler på bookinger:")
                    for booking in bookings:
                        print(f"  Booking ID: {booking[0]}, Navn: {booking[1]} {booking[2]}")
                    
                    # Tjek specifikt for booking 41967
                    cursor.execute("SELECT booking_id, fornavn, efternavn FROM aktive_bookinger WHERE booking_id = '41967'")
                    booking_41967 = cursor.fetchone()
                    if booking_41967:
                        print(f"Booking 41967 fundet: {booking_41967[1]} {booking_41967[2]}")
                    else:
                        print("Booking 41967 blev ikke fundet i aktive_bookinger.")
            else:
                print("ADVARSEL: Tabellen 'aktive_bookinger' findes IKKE i databasen!")
        except Error as e:
            print(f'Fejl ved forespørgsel på aktive_bookinger: {e}')
        
        # Test 2: Tjek om users tabellen eksisterer
        try:
            cursor.execute("SHOW TABLES LIKE 'users'")
            result = cursor.fetchone()
            if result:
                print("\nTabellen 'users' findes i databasen.")
                
                # Tjek indhold i users
                cursor.execute("SELECT COUNT(*) FROM users")
                count = cursor.fetchone()[0]
                print(f"Antal rækker i users: {count}")
                
                # Vis eksempler på brugere
                if count > 0:
                    cursor.execute("SELECT id, username, fornavn, efternavn FROM users LIMIT 5")
                    users = cursor.fetchall()
                    print("Eksempler på brugere:")
                    for user in users:
                        print(f"  ID: {user[0]}, Username: {user[1]}, Navn: {user[2]} {user[3]}")
                    
                    # Tjek specifikt for bruger med username 41967
                    cursor.execute("SELECT id, username, fornavn, efternavn FROM users WHERE username = '41967'")
                    user_41967 = cursor.fetchone()
                    if user_41967:
                        print(f"Bruger med username 41967 fundet: ID {user_41967[0]}, Navn: {user_41967[2]} {user_41967[3]}")
                    else:
                        print("Bruger med username 41967 blev ikke fundet i users tabellen.")
            else:
                print("\nADVARSEL: Tabellen 'users' findes IKKE i databasen!")
        except Error as e:
            print(f'Fejl ved forespørgsel på users: {e}')
        
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
