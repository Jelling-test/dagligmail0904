import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import os

# Indlæs miljøvariabler
load_dotenv()

# Opret forbindelse til databasen
try:
    conn = mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )
    
    if conn.is_connected():
        cursor = conn.cursor()
        
        # Indsæt Stripe nøgler
        cursor.execute("""
        REPLACE INTO system_settings (setting_key, value) 
        VALUES 
        ('stripe_publishable_key_test', 'pk_test_rrtorVz0wXEqxZ2xLQq81VMS0095DFsWBk'),
        ('stripe_secret_key_test', 'sk_test_WvIACW8kIb7ihbWFeCmbJ4wq00l81tBJxx'),
        ('stripe_mode', 'test')
        """)
        
        conn.commit()
        print("Stripe nøgler indsat i databasen")
        
        # Hent alle stripe indstillinger for at bekræfte
        cursor.execute("SELECT setting_key, value FROM system_settings WHERE setting_key LIKE '%stripe%'")
        results = cursor.fetchall()
        
        print("\nStipe indstillinger i databasen:")
        for row in results:
            print(f"{row[0]}: {row[1]}")
        
        cursor.close()
        conn.close()
        
except Error as e:
    print(f"Fejl ved forbindelse til database: {e}")
