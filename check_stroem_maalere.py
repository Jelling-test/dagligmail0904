import os
import mysql.connector
from dotenv import load_dotenv

# Indlæs miljøvariabler
load_dotenv()

# Opret forbindelse til databasen
conn = mysql.connector.connect(
    host=os.getenv('DB_HOST'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME')
)

# Opret cursor
cursor = conn.cursor(dictionary=True)

# Tjek om tabellen eksisterer
cursor.execute("SHOW TABLES LIKE 'stroem_maalere'")
table_exists = cursor.fetchone() is not None

if table_exists:
    print("Tabellen 'stroem_maalere' eksisterer")
    # Vis struktur
    cursor.execute("DESCRIBE stroem_maalere")
    print("\nTabellens struktur:")
    for column in cursor.fetchall():
        print(f"- {column['Field']}: {column['Type']} ({column['Null']})")
else:
    print("Tabellen 'stroem_maalere' eksisterer IKKE")

# Luk forbindelser
cursor.close()
conn.close()
