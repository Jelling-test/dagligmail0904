import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

# Indlæs miljøvariabler fra .env filen
load_dotenv()

def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'camping')
        )
        if conn.is_connected():
            print("Forbindelse til database oprettet.")
            return conn
    except Error as e:
        print(f"Fejl ved forbindelse til database: {e}")
    return None

def main():
    conn = get_db_connection()
    if not conn:
        print("Kunne ikke oprette forbindelse til databasen.")
        return
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Tjek strukturen af stroem_pakker tabellen
        print("\n===== STROEM_PAKKER TABEL STRUKTUR =====")
        try:
            cursor.execute("DESCRIBE stroem_pakker")
            columns = cursor.fetchall()
            for column in columns:
                print(f"- {column['Field']}: {column['Type']} {column.get('Key', '')} {column.get('Extra', '')}")
            
            # Tjek indhold af stroem_pakker tabellen
            print("\n===== STROEM_PAKKER INDHOLD (top 5) =====")
            cursor.execute("SELECT * FROM stroem_pakker LIMIT 5")
            pakker = cursor.fetchall()
            if pakker:
                for pakke in pakker:
                    print(f"ID: {pakke.get('id')}, Navn: {pakke.get('navn')}")
            else:
                print("Ingen data fundet i stroem_pakker tabellen.")
        except Error as e:
            print(f"Fejl ved forespørgsel til stroem_pakker: {e}")
        
        # Tjek strukturen af stroem_koeb tabellen
        print("\n===== STROEM_KOEB TABEL STRUKTUR =====")
        try:
            cursor.execute("DESCRIBE stroem_koeb")
            columns = cursor.fetchall()
            for column in columns:
                print(f"- {column['Field']}: {column['Type']} {column.get('Key', '')} {column.get('Extra', '')}")
            
            # Tjek indhold af stroem_koeb tabellen
            print("\n===== STROEM_KOEB INDHOLD (top 5) =====")
            cursor.execute("SELECT * FROM stroem_koeb LIMIT 5")
            koeb = cursor.fetchall()
            if koeb:
                for k in koeb:
                    print(f"ID: {k.get('id')}, Booking ID: {k.get('booking_id')}, Pakke ID: {k.get('pakke_id')}, Måler ID: {k.get('maaler_id')}, Enheder tilbage: {k.get('enheder_tilbage')}")
            else:
                print("Ingen data fundet i stroem_koeb tabellen.")
        except Error as e:
            print(f"Fejl ved forespørgsel til stroem_koeb: {e}")
        
        # Tjek for foreign key constraints
        print("\n===== FOREIGN KEY CONSTRAINTS =====")
        try:
            cursor.execute("""
                SELECT TABLE_NAME, COLUMN_NAME, CONSTRAINT_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                WHERE REFERENCED_TABLE_SCHEMA = %s
                AND TABLE_NAME = 'stroem_koeb'
            """, (os.getenv('DB_NAME', 'camping'),))
            constraints = cursor.fetchall()
            if constraints:
                for c in constraints:
                    print(f"Tabel: {c.get('TABLE_NAME')}, Kolonne: {c.get('COLUMN_NAME')}, Constraint: {c.get('CONSTRAINT_NAME')}")
                    print(f"  Refererer til: {c.get('REFERENCED_TABLE_NAME')}.{c.get('REFERENCED_COLUMN_NAME')}")
            else:
                print("Ingen foreign key constraints fundet for stroem_koeb tabellen.")
        except Error as e:
            print(f"Fejl ved forespørgsel til constraints: {e}")
            
    except Error as e:
        print(f"Generel fejl ved forespørgsel: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
            print("\nForbindelse til database lukket.")

if __name__ == "__main__":
    main()
