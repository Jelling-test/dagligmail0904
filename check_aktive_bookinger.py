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

def check_aktive_bookinger():
    """Tjekker strukturen af aktive_bookinger tabellen"""
    try:
        # Opret forbindelse til databasen
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        
        cursor = conn.cursor(dictionary=True)
        
        # Tjek om tabellen eksisterer i den aktuelle database
        cursor.execute(f"SHOW TABLES LIKE 'aktive_bookinger'")
        table_exists = cursor.fetchone() is not None
        
        if table_exists:
            print("Tabellen 'aktive_bookinger' findes i den aktuelle database")
            cursor.execute("DESCRIBE aktive_bookinger")
            columns = cursor.fetchall()
            for column in columns:
                print(f"{column['Field']} - {column['Type']} - {column['Key']}")
                
            # Tjek om email kolonnen allerede findes
            has_email = any(column['Field'] == 'email' for column in columns)
            print(f"Email kolonne findes: {has_email}")
        else:
            print("Tabellen 'aktive_bookinger' findes IKKE i den aktuelle database")
            print("Tjekker om den findes i 'camping_aktiv' databasen...")
            
            # Skift til camping_aktiv databasen
            cursor.execute("USE camping_aktiv")
            cursor.execute("SHOW TABLES LIKE 'aktive_bookinger'")
            table_exists_in_camping_aktiv = cursor.fetchone() is not None
            
            if table_exists_in_camping_aktiv:
                print("Tabellen 'aktive_bookinger' findes i camping_aktiv databasen")
                cursor.execute("DESCRIBE aktive_bookinger")
                columns = cursor.fetchall()
                for column in columns:
                    print(f"{column['Field']} - {column['Type']} - {column['Key']}")
                
                # Tjek om email kolonnen allerede findes
                has_email = any(column['Field'] == 'email' for column in columns)
                print(f"Email kolonne findes: {has_email}")
            else:
                print("Tabellen 'aktive_bookinger' findes hverken i aktuel database eller i camping_aktiv")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Fejl under tjek af aktive_bookinger: {e}")

if __name__ == "__main__":
    check_aktive_bookinger()
