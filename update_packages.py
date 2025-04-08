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
        
        print("Sletter eksisterende strømpakker...")
        cursor.execute("DELETE FROM power_packages")
        
        print("Indsætter nye strømpakker for almindelige gæster...")
        cursor.execute("""
            INSERT INTO power_packages (name, description, size, price, is_addon)
            VALUES 
                ('Basis Pakke', 'Standard strømpakke med 100 enheder', 100, 450.00, FALSE),
                ('Stor Pakke', 'Stor strømpakke med 200 enheder', 200, 900.00, FALSE)
        """)
        
        print("Indsætter nye strømpakker for sæsongæster...")
        cursor.execute("""
            INSERT INTO power_packages (name, description, size, price, is_addon)
            VALUES 
                ('Sæson 100', 'Strømpakke for sæsongæster med 100 enheder', 100, 450.00, FALSE),
                ('Sæson 200', 'Strømpakke for sæsongæster med 200 enheder', 200, 900.00, FALSE)
        """)
        
        print("Indsætter nye tillægspakker...")
        cursor.execute("""
            INSERT INTO power_packages (name, description, size, price, is_addon)
            VALUES 
                ('Tillæg 25', 'Tillægspakke med 25 enheder', 25, 112.50, TRUE),
                ('Tillæg 50', 'Tillægspakke med 50 enheder', 50, 225.00, TRUE)
        """)
        
        connection.commit()
        
        print("Kontrollerer indsatte pakker...")
        cursor.execute("SELECT id, name, description, size, price, is_addon FROM power_packages ORDER BY id")
        packages = cursor.fetchall()
        for package in packages:
            print(f"ID: {package[0]}, Navn: {package[1]}, Beskrivelse: {package[2]}, Størrelse: {package[3]}, Pris: {package[4]}, Tillæg: {'Ja' if package[5] == 1 else 'Nej'}")
        
except Error as e:
    print(f"Fejl ved opdatering af strømpakker: {e}")
    
finally:
    if 'connection' in locals() and connection.is_connected():
        cursor.close()
        connection.close()
        print("Database forbindelse lukket")
