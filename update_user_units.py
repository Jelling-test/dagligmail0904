#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

# Indlæs miljøvariabler
load_dotenv()

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'camping_stroem'),
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
        return connection
    except Error as e:
        print(f"Fejl ved forbindelse til database: {e}")
        return None

def update_user_units(booking_id, new_units):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            print("Kunne ikke oprette forbindelse til databasen.")
            return False
        
        cursor = conn.cursor(dictionary=True)
        
        # Find brugerens aktive måler
        cursor.execute("SELECT id, meter_id, package_size FROM active_meters WHERE booking_id = %s", (booking_id,))
        connection = cursor.fetchone()
        
        if not connection:
            print(f"Ingen aktiv måler fundet for booking ID {booking_id}.")
            return False
        
        old_package_size = connection.get('package_size', 0)
        meter_id = connection.get('meter_id')
        
        print(f"Fundet aktiv måler: {meter_id} for booking {booking_id}")
        print(f"Nuværende enhedsbeholdning: {old_package_size}")
        
        # Opdater enhedsbeholdningen
        update_cursor = conn.cursor()
        update_cursor.execute(
            "UPDATE active_meters SET package_size = %s WHERE id = %s",
            (new_units, connection['id'])
        )
        rows_affected = update_cursor.rowcount
        update_cursor.close()
        
        if rows_affected > 0:
            conn.commit()
            print(f"Succes: Enhedsbeholdning for {booking_id} er nu sat til {new_units} enheder.")
            return True
        else:
            conn.rollback()
            print(f"Fejl: Kunne ikke opdatere enheder for {booking_id}.")
            return False
            
    except Error as db_err:
        print(f"Databasefejl: {db_err}")
        if conn: conn.rollback()
        return False
    except Exception as e:
        print(f"Generel fejl: {e}")
        if conn: conn.rollback()
        return False
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

if __name__ == "__main__":
    # Opdater bruger 41967's enhedsbeholdning til 0,02
    booking_id = "41967"
    new_units = 0.02
    
    print(f"Opdaterer enhedsbeholdning for bruger {booking_id} til {new_units} enheder...")
    success = update_user_units(booking_id, new_units)
    
    if success:
        print("Opdatering gennemført.")
    else:
        print("Opdatering fejlede.")
