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

def check_tables():
    """Vis strukturen af relevante tabeller for at identificere problemet"""
    try:
        # Opret forbindelse til databasen
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        
        cursor = conn.cursor(dictionary=True)
        
        print("===== USERS TABEL STRUKTUR =====")
        cursor.execute("DESCRIBE users")
        users_columns = cursor.fetchall()
        for column in users_columns:
            print(f"{column['Field']} - {column['Type']} - {column['Key']}")
        
        print("\n===== PURCHASED_PACKAGES TABEL STRUKTUR =====")
        cursor.execute("DESCRIBE purchased_packages")
        packages_columns = cursor.fetchall()
        for column in packages_columns:
            print(f"{column['Field']} - {column['Type']} - {column['Key']}")
            
        print("\n===== FOREIGN KEY CONSTRAINTS =====")
        cursor.execute("""
            SELECT TABLE_NAME, COLUMN_NAME, CONSTRAINT_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = %s
            AND REFERENCED_TABLE_NAME IS NOT NULL
            AND TABLE_NAME = 'purchased_packages'
        """, (DB_NAME,))
        constraints = cursor.fetchall()
        for constraint in constraints:
            print(f"Tabel: {constraint['TABLE_NAME']}, Kolonne: {constraint['COLUMN_NAME']}")
            print(f"Reference til: {constraint['REFERENCED_TABLE_NAME']}.{constraint['REFERENCED_COLUMN_NAME']}")
            
        print("\n===== SE FAKTSIK BRUGER DATA =====")
        cursor.execute("SELECT * FROM users LIMIT 5")
        users = cursor.fetchall()
        for user in users:
            print(f"ID: {user.get('id', 'N/A')}, Username: {user.get('username', 'N/A')}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Fejl under tjek af database struktur: {e}")

if __name__ == "__main__":
    check_tables()
