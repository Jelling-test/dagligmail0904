import os
import time
import mysql.connector
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from send_email import send_email
from email_templates import get_low_power_template

# Indlæs miljøvariabler
load_dotenv()

# Hent konfiguration
DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')
HASS_URL = os.getenv('HASS_URL')
HASS_TOKEN = os.getenv('HASS_TOKEN')

def get_db_connection():
    """Opret forbindelse til databasen"""
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        return conn
    except mysql.connector.Error as e:
        print(f"Fejl ved forbindelse til database: {e}")
        return None

def check_package_status():
    """Tjek status på alle aktive strømpakker og sluk for dem der er opbrugt"""
    conn = get_db_connection()
    if not conn:
        print("Kunne ikke forbinde til databasen")
        return
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Hent alle aktive målere med relaterede brugerdata
        cursor.execute('''
            SELECT am.booking_id, am.meter_id, am.start_value, am.package_size, 
                   u.username, u.id as user_id, u.fornavn, u.efternavn, u.email, u.language
            FROM active_meters am
            JOIN users u ON am.booking_id = u.username
            WHERE am.meter_id IS NOT NULL
        ''')
        
        active_meters = cursor.fetchall()
        
        for meter in active_meters:
            try:
                # Hent den nuværende målerværdi fra Home Assistant
                meter_id = meter['meter_id']
                response = requests.get(
                    f"{HASS_URL}/api/states/{meter_id}",
                    headers={"Authorization": f"Bearer {HASS_TOKEN}"}
                )
                
                if response.status_code != 200:
                    print(f"Kunne ikke hente målerværdi for {meter_id}, status: {response.status_code}")
                    continue
                
                sensor_data = response.json()
                current_value = float(sensor_data['state'])
                start_value = float(meter['start_value'])
                package_size = float(meter['package_size'])
                
                # Beregn forbrug og resterende enheder
                total_usage = current_value - start_value
                remaining = package_size - total_usage
                
                print(f"Måler {meter_id} - Forbrug: {total_usage:.3f}, Resterende: {remaining:.3f}")
                
                # Tjek om vi skal sende en advarsel (når der er mindre end 3 enheder tilbage)
                if 0 < remaining <= 3:
                    user_id = meter['user_id']
                    user_email = meter['email']
                    
                    # Hent brugerens sprogpræference (brug 'da' som standard)
                    user_language = meter.get('language', 'da')
                    
                    # Tjek om vi har sendt en advarsel til denne bruger for nylig
                    cursor.execute('''
                        SELECT * FROM email_alerts 
                        WHERE user_id = %s AND meter_id = %s AND alert_type = 'low_units'
                        AND sent_at > DATE_SUB(NOW(), INTERVAL 24 HOUR)
                    ''', (user_id, meter_id))
                    
                    recent_alert = cursor.fetchone()
                    
                    # Hvis brugeren har en email og vi ikke har sendt en advarsel i de sidste 24 timer
                    if user_email and not recent_alert:
                        print(f"Sender advarsel til {meter['fornavn']} {meter['efternavn']} ({user_email}) - {remaining:.2f} enheder tilbage")
                        
                        # Hent email skabelon på brugerens foretrukne sprog
                        template = get_low_power_template(user_language)
                        
                        # Erstat pladsholdere i skabelonerne
                        formatted_html = template['html'].format(
                            fornavn=meter['fornavn'],
                            efternavn=meter['efternavn'],
                            remaining=remaining
                        )
                        
                        formatted_text = template['text'].format(
                            fornavn=meter['fornavn'],
                            efternavn=meter['efternavn'],
                            remaining=remaining
                        )
                        
                        # Send email
                        email_sent = send_email(
                            user_email, 
                            template['subject'], 
                            formatted_html,
                            formatted_text
                        )
                        
                        # Hvis emailen blev sendt, log det i databasen
                        if email_sent:
                            cursor.execute('''
                                INSERT INTO email_alerts (user_id, meter_id, alert_type, remaining_units)
                                VALUES (%s, %s, %s, %s)
                            ''', (user_id, meter_id, 'low_units', remaining))
                            conn.commit()
                
                # Hvis der ikke er flere enheder tilbage, sluk for strømmen
                if remaining <= 0:
                    print(f"Pakke opbrugt for bruger {meter['username']} - slukker for strømmen")
                    
                    # Konverter sensor-ID til switch-ID
                    meter_parts = meter_id.split('_')
                    device_id = meter_parts[0].replace('sensor.', '')
                    switch_id = f"switch.{device_id}_0"
                    
                    # Sluk for strømmen via Home Assistant
                    power_response = requests.post(
                        f"{HASS_URL}/api/services/switch/turn_off",
                        headers={"Authorization": f"Bearer {HASS_TOKEN}"},
                        json={"entity_id": switch_id}
                    )
                    
                    if power_response.status_code == 200:
                        print(f"Strøm slukket for måler {meter_id} (switch {switch_id})")
                        
                        # Log hændelsen i databasen
                        cursor.execute('''
                            INSERT INTO power_events (user_id, event_type, meter_id, details)
                            VALUES (%s, %s, %s, %s)
                        ''', (
                            meter['user_id'], 
                            'auto_power_off', 
                            meter_id, 
                            f"Automatisk slukning: Pakke opbrugt. Forbrug: {total_usage:.3f}, Pakke: {package_size:.3f}"
                        ))
                        conn.commit()
                    else:
                        print(f"Fejl ved slukning af strøm for {switch_id}, status: {power_response.status_code}")
            
            except Exception as e:
                print(f"Fejl ved behandling af måler {meter['meter_id']}: {str(e)}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Generel fejl: {str(e)}")
        if conn:
            conn.close()

if __name__ == "__main__":
    print(f"Starter kontrol af strømpakker - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    check_package_status()
    print("Kontrol afsluttet")
