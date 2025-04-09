import os
import sys
import logging
import traceback
from datetime import datetime, timedelta
from flask_mail import Message
import mysql.connector
from mysql.connector import Error

# Konfigurer logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Funktion til at få forbindelse til databasen
def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=os.getenv('MYSQL_HOST', 'localhost'),
            user=os.getenv('MYSQL_USER', 'root'),
            password=os.getenv('MYSQL_PASSWORD', ''),
            database=os.getenv('MYSQL_DB', 'strom_db')
        )
        return connection
    except Error as e:
        logger.error(f"Database fejl: {e}")
        return None

# Funktion til at lukke forbindelsen sikkert
def safe_close_connection(connection):
    try:
        if connection.is_connected():
            connection.close()
    except:
        pass

# Funktion til at hente systemindstillinger
def get_system_settings():
    conn = None
    cursor = None
    settings = {
        'daily_report_email': '',
        'daily_report_time': '23:59'
    }
    
    try:
        conn = get_db_connection()
        if not conn:
            return settings
            
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT setting_key, setting_value FROM system_settings")
        rows = cursor.fetchall()
        
        for row in rows:
            settings[row['setting_key']] = row['setting_value']
            
    except Exception as e:
        logger.error(f"Fejl ved hentning af systemindstillinger: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            safe_close_connection(conn)
            
    return settings

# Import Flask-Mail
from flask import Flask
from flask_mail import Mail

# Initialiser en minimal Flask-app for at bruge Mail
app = Flask(__name__)

# Hent e-mail-indstillinger
try:
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT setting_key, setting_value FROM system_settings WHERE setting_key LIKE 'smtp_%'")
    mail_settings = {row['setting_key']: row['setting_value'] for row in cursor.fetchall()}
    
    # Konfigurer Flask-Mail
    app.config['MAIL_SERVER'] = mail_settings.get('smtp_host', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(mail_settings.get('smtp_port', '587'))
    app.config['MAIL_USERNAME'] = mail_settings.get('smtp_user', '')
    app.config['MAIL_PASSWORD'] = mail_settings.get('smtp_password', '')
    app.config['MAIL_USE_TLS'] = mail_settings.get('smtp_use_tls', 'true').lower() == 'true'
    app.config['MAIL_USE_SSL'] = mail_settings.get('smtp_use_ssl', 'false').lower() == 'true'
    app.config['MAIL_DEFAULT_SENDER'] = mail_settings.get('receipt_sender_email', 'noreply@example.com')
    
    cursor.close()
    safe_close_connection(conn)
except Exception as e:
    logger.error(f"Fejl ved indlæsning af e-mail-indstillinger: {e}")
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USE_SSL'] = False
    app.config['MAIL_DEFAULT_SENDER'] = 'noreply@example.com'

# Initialiser Mail
mail = Mail(app)

def send_daily_sales_report():
    """Generer og send en daglig salgsrapport med alle køb fra det seneste døgn."""
    with app.app_context():
        conn = None
        cursor = None
        
        # Hent e-mail-indstillinger fra databasen
        system_settings = get_system_settings()
        recipient_email = system_settings.get('daily_report_email')
        
        logger.info(f"Forsøger at sende rapport til: {recipient_email}")
        
        # Hvis der ikke er konfigureret en modtager-e-mail, så gør ingenting
        if not recipient_email:
            logger.info("Daglig rapport: Ingen modtager-e-mail konfigureret, springer over.")
            return
        
        try:
            logger.info(f"Genererer daglig salgsrapport til {recipient_email}")
            
            # Opdater mail konfiguration for at sikre vi bruger de rigtige indstillinger
            app.config['MAIL_SERVER'] = 'smtp.gmail.com'
            app.config['MAIL_PORT'] = 587
            app.config['MAIL_USE_TLS'] = True
            app.config['MAIL_USERNAME'] = 'peter@jellingcamping.dk'
            app.config['MAIL_PASSWORD'] = 'upjaqexllxzibret'  # App password uden mellemrum
            app.config['MAIL_DEFAULT_SENDER'] = 'peter@jellingcamping.dk'
            
            # Geninstantier mail med opdateret konfiguration
            global mail
            mail = Mail(app)
            
            logger.info(f"Mail-konfiguration opdateret med: {app.config['MAIL_USERNAME']}")
            
            # Opret forbindelse til databasen
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Hent data fra i går til i dag
            yesterday = datetime.now() - timedelta(days=1)
            yesterday_str = yesterday.strftime('%Y-%m-%d 00:00:00')
            now_str = datetime.now().strftime('%Y-%m-%d 23:59:59')
            
            # Hent alle køb fra det seneste døgn
            query = """
            SELECT pp.id, pp.purchase_date, u.fornavn, u.efternavn, u.email, 
                p.navn AS package_name, p.enheder, p.pris_dkk, am.meter_id
            FROM purchased_packages pp
            LEFT JOIN users u ON pp.user_id = u.id
            LEFT JOIN power_packages p ON pp.package_id = p.id
            LEFT JOIN active_meters am ON pp.meter_id = am.meter_id
            WHERE pp.purchase_date BETWEEN %s AND %s
            ORDER BY pp.purchase_date DESC
            """
            cursor.execute(query, (yesterday_str, now_str))
            purchases = cursor.fetchall()
            
            # Log antallet af køb for fejlfinding
            logger.info(f"Fandt {len(purchases)} køb i perioden")
            
            # Lav statistik
            total_count = len(purchases)
            total_amount = sum(float(purchase['pris_dkk']) for purchase in purchases if purchase['pris_dkk'])
            
            # Generer HTML-indhold til e-mail
            html_content = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; }}
                    h2 {{ color: #2c3e50; }}
                    table {{ border-collapse: collapse; width: 100%; }}
                    th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
                    th {{ background-color: #f2f2f2; color: #333; }}
                    tr:hover {{ background-color: #f5f5f5; }}
                    .summary {{ background-color: #eef; padding: 10px; margin-bottom: 20px; }}
                </style>
            </head>
            <body>
                <h2>Daglig Salgsrapport - Strøm App</h2>
                <div class="summary">
                    <p><strong>Periode:</strong> {yesterday.strftime('%d-%m-%Y')} til {datetime.now().strftime('%d-%m-%Y')}</p>
                    <p><strong>Antal køb:</strong> {total_count}</p>
                    <p><strong>Total beløb:</strong> {total_amount:.2f} DKK</p>
                </div>
            """
            
            if purchases:
                html_content += """
                <table>
                    <tr>
                        <th>Dato</th>
                        <th>Bruger</th>
                        <th>E-mail</th>
                        <th>Pakke</th>
                        <th>Enheder</th>
                        <th>Pris (DKK)</th>
                        <th>Måler-ID</th>
                    </tr>
                """
                
                for purchase in purchases:
                    purchase_date = purchase['purchase_date'].strftime('%d-%m-%Y %H:%M:%S') if purchase['purchase_date'] else 'N/A'
                    user_name = f"{purchase['fornavn']} {purchase['efternavn']}" if purchase['fornavn'] and purchase['efternavn'] else 'N/A'
                    email = purchase['email'] or 'N/A'
                    package_name = purchase['package_name'] or 'N/A'
                    units = f"{purchase['enheder']}" if purchase['enheder'] is not None else 'N/A'
                    price = f"{purchase['pris_dkk']:.2f}" if purchase['pris_dkk'] is not None else 'N/A'
                    meter_id = purchase['meter_id'] or 'N/A'
                    
                    html_content += f"""
                    <tr>
                        <td>{purchase_date}</td>
                        <td>{user_name}</td>
                        <td>{email}</td>
                        <td>{package_name}</td>
                        <td>{units}</td>
                        <td>{price}</td>
                        <td>{meter_id}</td>
                    </tr>
                    """
                
                html_content += "</table>"
            else:
                html_content += "<p><em>Ingen køb i perioden.</em></p>"
            
            html_content += """
            <p>Dette er en automatisk genereret e-mail. Venligst svar ikke på denne e-mail.</p>
            </body>
            </html>
            """
            
            # Send e-mail
            msg = Message(
                subject=f"Daglig Salgsrapport - Strøm App ({datetime.now().strftime('%d-%m-%Y')})",
                recipients=[recipient_email],
                html=html_content,
                sender=app.config['MAIL_DEFAULT_SENDER']
            )
            
            mail.send(msg)
            logger.info(f"Daglig salgsrapport sendt til {recipient_email} med {total_count} køb")
            print(f"Daglig salgsrapport er sendt til {recipient_email} med {total_count} køb")
            
        except Exception as e:
            logger.error(f"Fejl ved generering af daglig salgsrapport: {e}")
            tb = traceback.format_exc()
            logger.error(f"Traceback: {tb}")
            print(f"Fejl ved generering af daglig salgsrapport: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                safe_close_connection(conn)

if __name__ == "__main__":
    print("Sender daglig salgsrapport...")
    send_daily_sales_report()
    print("Rapport afsendt, tjek den konfigurerede e-mail-adresse for resultatet.")
