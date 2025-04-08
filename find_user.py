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

def find_user():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        
        cursor = conn.cursor(dictionary=True)
        
        # Søg efter brugere med 'Allan' eller 'Halse' i brugernavnet
        cursor.execute("SELECT * FROM users WHERE username LIKE '%Allan%' OR username LIKE '%Halse%'")
        users = cursor.fetchall()
        
        print("Brugere fundet:")
        for user in users:
            print(f"ID: {user['id']}, Brugernavn: {user['username']}")
        
        cursor.close()
        conn.close()
        
    except mysql.connector.Error as e:
        print(f"Fejl ved søgning efter bruger: {e}")

if __name__ == "__main__":
    find_user()
