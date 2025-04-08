import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'campingdb')
        )
        return connection
    except Exception as e:
        print(f"Fejl ved forbindelse til database: {e}")
        return None

def main():
    conn = get_db_connection()
    if not conn:
        print("Kunne ikke forbinde til databasen!")
        return
    
    cursor = conn.cursor(dictionary=True)
    
    # Hent aktive målere
    cursor.execute('''
        SELECT am.*, mc.display_name, mc.location, mc.power_switch_id
        FROM active_meters am 
        LEFT JOIN meter_config mc ON am.meter_id = mc.sensor_id
    ''')
    
    results = cursor.fetchall()
    
    print("\nAKTIVE STRØMMÅLERE:")
    print("-" * 100)
    print(f"{'Booking ID':<15} {'Måler ID':<30} {'Navn':<20} {'Sted':<15} {'Start':<10} {'Pakke':<10} {'Switch ID':<20}")
    print("-" * 100)
    
    for r in results:
        print(f"{r.get('booking_id', 'N/A'):<15} {r.get('meter_id', 'N/A'):<30} {r.get('display_name', 'N/A'):<20} {r.get('location', 'N/A'):<15} {r.get('start_value', 'N/A'):<10} {r.get('package_size', 'N/A'):<10} {r.get('power_switch_id', 'N/A'):<20}")
    
    print("-" * 100)
    print(f"Total antal aktive målere: {len(results)}")
    
    # Luk forbindelser
    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
