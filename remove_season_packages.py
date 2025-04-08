import os
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error

load_dotenv()

try:
    # Opret forbindelse til databasen
    connection = mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )
    
    if connection.is_connected():
        cursor = connection.cursor()
        
        print("Sletter sæsonpakker...")
        cursor.execute("DELETE FROM power_packages WHERE name LIKE 'Sæson%'")
        
        print(f"Antal slettede pakker: {cursor.rowcount}")
        
        connection.commit()
        
        # Vis resterende pakker
        cursor.execute("SELECT id, name, description, size, price, is_addon FROM power_packages ORDER BY id")
        packages = cursor.fetchall()
        print("\nResterende pakker:")
        for package in packages:
            print(f"ID: {package[0]}, Navn: {package[1]}, Størrelse: {package[3]}, Pris: {package[4]}, Tillæg: {'Ja' if package[5] == 1 else 'Nej'}")
        
except Error as e:
    print(f"Fejl ved sletning af sæsonpakker: {e}")
    
finally:
    if 'connection' in locals() and connection.is_connected():
        cursor.close()
        connection.close()
        print("\nDatabase forbindelse lukket")
