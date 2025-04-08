import os
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error

load_dotenv()

def get_packages():
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )
        
        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)
            cursor.execute('SELECT * FROM power_packages')
            packages = cursor.fetchall()
            
            print("\nTilgængelige strømpakker:")
            print("-" * 80)
            for package in packages:
                print(f"ID: {package['id']}")
                print(f"Navn: {package['name']}")
                print(f"Størrelse: {package['size']} enheder")
                print(f"Pris: {package['price']} kr")
                print(f"Tillægspakke: {'Ja' if package['is_addon'] else 'Nej'}")
                print(f"Beskrivelse: {package['description']}")
                print("-" * 80)

    except Error as e:
        print(f"Fejl ved forbindelse til database: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

if __name__ == "__main__":
    get_packages()
