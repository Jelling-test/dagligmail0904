import os
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error

load_dotenv()

def create_tables():
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )

        if connection.is_connected():
            cursor = connection.cursor()

            # Create users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    fornavn VARCHAR(100),
                    efternavn VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Bemærk: Vi opretter ikke længere testbrugere her
            # Rigtige data kommer fra booking-systemets database

            # Create active_meters table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS active_meters (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    meter_id VARCHAR(50) NOT NULL,
                    start_value DECIMAL(10,2),
                    current_value DECIMAL(10,2),
                    package_size INT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    UNIQUE (meter_id)
                )
            """)

            # Create power_packages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS power_packages (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    description TEXT,
                    size INT NOT NULL,
                    price DECIMAL(10,2) NOT NULL,
                    is_addon BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Insert default power packages if they don't exist
            cursor.execute("""
                INSERT INTO power_packages (name, description, size, price, is_addon)
                VALUES 
                    ('Basis pakke', 'Standard strømpakke til almindeligt forbrug', 100, 50.00, FALSE),
                    ('Stor pakke', 'Strømpakke til større forbrug', 200, 90.00, FALSE),
                    ('Tillægspakke 50', 'Ekstra 50 enheder', 50, 30.00, TRUE),
                    ('Tillægspakke 100', 'Ekstra 100 enheder', 100, 55.00, TRUE)
                ON DUPLICATE KEY UPDATE name=name
            """)

            # Create purchased_packages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS purchased_packages (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    package_id INT,
                    meter_id VARCHAR(50),
                    purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (package_id) REFERENCES power_packages(id),
                    FOREIGN KEY (meter_id) REFERENCES active_meters(meter_id)
                )
            """)

            connection.commit()
            print("Tabeller oprettet/opdateret succesfuldt")

    except Error as e:
        print(f"Fejl ved oprettelse af tabeller: {e}")

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            print("Database forbindelse lukket")

if __name__ == "__main__":
    create_tables()
