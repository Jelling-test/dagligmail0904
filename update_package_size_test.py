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

def update_package_size_for_test():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        
        cursor = conn.cursor(dictionary=True)
        
        # Opdater pakke-størrelsen for bruger med bookingnummer 41967 til 0.003
        cursor.execute("""
            UPDATE active_meters 
            SET package_size = 0.003 
            WHERE booking_id = '41967'
        """)
        
        conn.commit()
        rows_affected = cursor.rowcount
        
        if rows_affected > 0:
            print(f"Bruger 41967's pakke-størrelse er opdateret til 0.003 enheder.")
        else:
            print("Ingen ændringer foretaget. Bruger 41967 har muligvis ikke en aktiv måler.")
        
        # Verificer ændringen
        cursor.execute("SELECT * FROM active_meters WHERE booking_id = '41967'")
        meter = cursor.fetchone()
        
        if meter:
            print(f"\nMåler detaljer efter opdatering:")
            print(f"Booking ID: {meter['booking_id']}")
            print(f"Måler ID: {meter['meter_id']}")
            print(f"Start værdi: {meter['start_value']}")
            print(f"Pakke størrelse: {meter['package_size']}")
        
        cursor.close()
        conn.close()
        
    except mysql.connector.Error as e:
        print(f"Fejl ved opdatering af pakke-størrelse: {e}")

if __name__ == "__main__":
    update_package_size_for_test()
