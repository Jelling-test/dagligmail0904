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
        # Slet testbruger
        cursor.execute("DELETE FROM users WHERE username = '41967'")
        connection.commit()
        print(f"Antal slettede brugere: {cursor.rowcount}")
        
        # Bekræft at brugeren er slettet
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        print(f"Brugere i databasen efter sletning: {len(users)}")
        print("Bruger-IDs:", [user[0] for user in users] if users else "Ingen brugere")
        
except Error as e:
    print(f"Fejl ved forbindelse til MySQL: {e}")
    
finally:
    if 'connection' in locals() and connection.is_connected():
        cursor.close()
        connection.close()
        print("Database forbindelse lukket")
