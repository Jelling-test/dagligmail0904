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

def check_user_info():
    """Tjekker brugeroplysninger i databasen, herunder email og andre felter"""
    try:
        # Opret forbindelse til databasen
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        
        cursor = conn.cursor(dictionary=True)
        
        # 1. Tjek users tabel struktur for at se alle felter
        print("\n===== USERS TABEL STRUKTUR =====")
        cursor.execute("DESCRIBE users")
        users_columns = cursor.fetchall()
        for column in users_columns:
            print(f"{column['Field']} - {column['Type']} - {column['Key']}")
        
        # 2. Hent alle brugere med deres fulde information
        print("\n===== ALLE BRUGERE =====")
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        
        for user in users:
            print("\n--- BRUGERDETALJER ---")
            for key, value in user.items():
                # Skjul password af sikkerhedsmæssige årsager
                if key == 'password':
                    print(f"{key}: [SKJULT]")
                else:
                    print(f"{key}: {value}")
        
        # 3. Tjek om der er en email felt i tabellen
        has_email_field = any(column['Field'] == 'email' for column in users_columns)
        if not has_email_field:
            print("\nBEMÆRK: Der er ikke et dedikeret 'email' felt i users tabellen!")
            
            # Tjek om email kan være gemt i et andet felt
            print("\nUndersøger om email findes i andre felter...")
            email_pattern = "%@%"
            found_emails = False
            
            for column in users_columns:
                if column['Type'].startswith('varchar') or column['Type'].startswith('text'):
                    field_name = column['Field']
                    if field_name != 'password':  # Skip password feltet
                        cursor.execute(f"SELECT username, {field_name} FROM users WHERE {field_name} LIKE %s", (email_pattern,))
                        results = cursor.fetchall()
                        if results:
                            found_emails = True
                            print(f"Mulige email-adresser fundet i feltet '{field_name}':")
                            for result in results:
                                print(f"Bruger {result['username']}: {result[field_name]}")
            
            if not found_emails:
                print("Ingen email-lignende værdier fundet i nogen felter!")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Fejl under tjek af brugerinformation: {e}")

if __name__ == "__main__":
    check_user_info()
