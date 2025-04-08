import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

# Indlæs miljøvariabler fra .env filen
load_dotenv()

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )
        return connection
    except Error as e:
        print(f"Fejl ved forbindelse til database: {e}")
        return None

def update_user_units(booking_id, new_units):
    conn = get_db_connection()
    if not conn:
        print("Kunne ikke oprette forbindelse til databasen.")
        return False
    
    cursor = conn.cursor()
    try:
        # Opdater package_size for den angivne bruger
        cursor.execute(
            "UPDATE active_meters SET package_size = %s WHERE booking_id = %s",
            (new_units, booking_id)
        )
        conn.commit()
        
        # Bekræft at opdateringen blev gennemført
        cursor.execute(
            "SELECT package_size FROM active_meters WHERE booking_id = %s",
            (booking_id,)
        )
        result = cursor.fetchone()
        
        if result:
            print(f"Bruger {booking_id} har nu {result[0]} enheder tilbage.")
            return True
        else:
            print(f"Ingen aktiv måler fundet for bruger {booking_id}.")
            return False
    except Error as e:
        print(f"Fejl ved opdatering af enheder: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

# Opdater bruger 41967 til at have 0 enheder tilbage
if __name__ == "__main__":
    update_user_units("41967", 0)
