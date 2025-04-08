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

# Hent aktive målere
cursor.execute('SELECT * FROM active_meters')
active_meters = cursor.fetchall()

# Udskriv resultater
print('Aktive målere:')
if active_meters:
    for meter in active_meters:
        print(f"Booking: {meter.get('booking_id')}, Måler: {meter.get('meter_id')}")
else:
    print("Ingen aktive målere fundet")

# Luk forbindelser
cursor.close()
conn.close()
