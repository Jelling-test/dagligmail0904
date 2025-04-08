import mysql.connector
import os
from dotenv import load_dotenv

# Prøv at indlæse miljøvariabler, hvis .env findes
try:
    load_dotenv()
except:
    pass

# SQL-forespørgsel
QUERY = "SELECT booking_id, fornavn, efternavn, LENGTH(efternavn) FROM aktive_bookinger WHERE booking_id = '41967'"

# Forbind til databasen
try:
    conn = mysql.connector.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        database=os.getenv('DB_NAME', 'hastighed'),
        charset='utf8mb4',
        collation='utf8mb4_unicode_ci'
    )
    
    cursor = conn.cursor(dictionary=True)
    
    # Kør forespørgslen
    print(f"\n=== KØRER FORESPØRGSEL ===")
    print(QUERY)
    print("===========================")
    
    cursor.execute(QUERY)
    results = cursor.fetchall()
    
    if results:
        # Vis kolonnenavne
        columns = list(results[0].keys())
        print("\n" + " | ".join(columns))
        print("-" * (sum([len(col) for col in columns]) + 3 * (len(columns) - 1)))
        
        # Vis resultater
        for row in results:
            print(" | ".join([str(row[col]) for col in columns]))
    else:
        print("\nIngen resultater fundet.")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"Fejl ved forbindelse til database: {e}")
