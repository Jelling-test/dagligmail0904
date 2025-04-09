#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Script til at sende salgsrapport med alle køb fra det seneste døgn
# Dette script kan køres selvstændigt eller importeres og bruges fra app.py

import os
import logging
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask
from flask_mail import Mail, Message
import mysql.connector
from collections import defaultdict

# Konfigurer logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Indlæs miljøvariabler fra .env-fil
load_dotenv()
logger.info("Miljøvariabler indlæst fra .env fil")

# Opret en minimal Flask-app til e-mail
app = Flask(__name__)

# Konfigurer Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'peter@jellingcamping.dk'
app.config['MAIL_PASSWORD'] = 'upjaqexllxzibret'  # App password uden mellemrum
app.config['MAIL_DEFAULT_SENDER'] = 'peter@jellingcamping.dk'

# Initialiser Mail
mail = Mail(app)

def get_db_connection():
    """Opret og returnerer en forbindelse til databasen baseret på miljøvariabler."""
    try:
        conn = mysql.connector.connect(
            host=os.environ.get('DB_HOST', '192.168.1.254'),
            user=os.environ.get('DB_USER', 'windsurf'),
            password=os.environ.get('DB_PASSWORD', '7300Jelling!'),
            database=os.environ.get('DB_NAME', 'camping_aktiv'),
            port=int(os.environ.get('DB_PORT', 3306))
        )
        return conn
    except mysql.connector.Error as e:
        logger.error(f"Database fejl: {e}")
        raise

def get_report_recipient():
    """Henter e-mail-modtageren fra systemindstillingerne."""
    conn = None
    cursor = None
    try:
        # Opret forbindelse til databasen
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Hent e-mail-modtageren fra system_settings
        cursor.execute("SELECT value FROM system_settings WHERE setting_key = 'daily_report_email'")
        result = cursor.fetchone()
        
        if result and result['value']:
            return result['value']
        else:
            # Returner en standard e-mail, hvis indstillingen ikke findes
            logger.warning("Indstillingen 'daily_report_email' blev ikke fundet. Bruger standard e-mail.")
            return 'peter@jellingcamping.dk'
    
    except Exception as e:
        logger.error(f"Fejl ved hentning af rapport-modtager: {e}")
        return 'peter@jellingcamping.dk'  # Returner standard e-mail i tilfælde af fejl
    
    finally:
        # Sørg for at lukke database forbindelsen
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def send_sales_report_email(recipient_email=None):
    """Genererer og sender en salgsrapport med alle køb fra det seneste døgn."""
    conn = None
    cursor = None
    try:
        # Hvis der ikke er angivet en modtager, hent den fra indstillingerne
        if not recipient_email:
            recipient_email = get_report_recipient()
            
        logger.info(f"Genererer salgsrapport til {recipient_email}")
        
        # Opret forbindelse til databasen
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Hent dagens dato og gårsdagens dato
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        
        # Hent alle køb fra det seneste døgn (bruger de korrekte tabelnavne)
        query = """
            SELECT K.id, K.booking_id, K.maaler_id, K.pakke_id, K.start_tid as purchase_date, P.pris as price, 
                   K.status, K.start_tid as creation_time, K.id as transaction_id, K.slut_tid as expiration_time,
                   P.navn as package_name, P.pris as package_price, 
                   P.enheder as package_kwh,
                   M.navn as meter_name, M.plads_nummer as meter_number
            FROM stroem_koeb K
            JOIN stroem_pakker P ON K.pakke_id = P.id
            JOIN stroem_maalere M ON K.maaler_id = M.id
            WHERE DATE(K.start_tid) >= %s
            ORDER BY K.booking_id, K.start_tid DESC
        """
        
        cursor.execute(query, (yesterday.strftime('%Y-%m-%d'),))
        purchases = cursor.fetchall()
        
        # Hvis der ikke er nogen køb, så send en simpel e-mail
        if not purchases:
            html_content = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; }}
                    h2 {{ color: #2c3e50; }}
                    .summary {{ background-color: #eef; padding: 10px; margin-bottom: 20px; }}
                </style>
            </head>
            <body>
                <h2>Daglig Salgsrapport</h2>
                <div class="summary">
                    <p><strong>Rapportperiode:</strong> {yesterday.strftime('%d-%m-%Y')} til {today.strftime('%d-%m-%Y')}</p>
                    <p><strong>Genereret:</strong> {today.strftime('%d-%m-%Y %H:%M:%S')}</p>
                </div>
                <p>Der har ikke været nogen strømkøb i det seneste døgn.</p>
            </body>
            </html>
            """
        else:
            # Gruppér køb efter booking-nummer
            booking_purchases = defaultdict(list)
            for purchase in purchases:
                booking_id = purchase['booking_id'] if purchase['booking_id'] else 'Uden booking'
                booking_purchases[booking_id].append(purchase)
            
            # Beregn total salg
            total_sales = sum(float(purchase['price']) for purchase in purchases)
            total_kwh = sum(float(purchase['package_kwh']) for purchase in purchases)
            
            # Generer booking-sektioner
            booking_sections = ""
            for booking_id, bookings in booking_purchases.items():
                # Beregn total for denne booking
                booking_total_sales = sum(float(booking['price']) for booking in bookings)
                booking_total_kwh = sum(float(booking['package_kwh']) for booking in bookings)
                
                # Generer køb-rækker for denne booking
                purchase_rows = ""
                for purchase in bookings:
                    # Formatér datoen
                    creation_time = purchase['creation_time']
                    if isinstance(creation_time, str):
                        # Konverter til datetime hvis string
                        creation_time = datetime.fromisoformat(creation_time.replace('Z', '+00:00'))
                    
                    formatted_time = creation_time.strftime('%d-%m-%Y %H:%M:%S')
                    
                    # Tilføj til HTML
                    purchase_rows += f"""
                    <tr>
                        <td>{purchase['meter_name']} ({purchase['meter_number']})</td>
                        <td>{purchase['package_name']}</td>
                        <td>{purchase['package_kwh']} kWh</td>
                        <td>{purchase['price']} kr.</td>
                        <td>{formatted_time}</td>
                    </tr>
                    """
                
                # Tilføj denne booking-sektion til HTML
                booking_sections += f"""
                <div class="booking-section">
                    <h3>Booking: {booking_id}</h3>
                    <div class="booking-summary">
                        <p><strong>Antal køb:</strong> {len(bookings)}</p>
                        <p><strong>Total salg:</strong> {booking_total_sales} kr.</p>
                        <p><strong>Total kWh solgt:</strong> {booking_total_kwh} kWh</p>
                    </div>
                    
                    <table>
                        <thead>
                            <tr>
                                <th>Måler</th>
                                <th>Pakke</th>
                                <th>kWh</th>
                                <th>Pris</th>
                                <th>Købstidspunkt</th>
                            </tr>
                        </thead>
                        <tbody>
                            {purchase_rows}
                        </tbody>
                    </table>
                </div>
                """
            
            # Generer HTML-e-mail med købene
            html_content = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; color: #333; }}
                    h2 {{ color: #2c3e50; }}
                    h3 {{ color: #3498db; margin-top: 20px; }}
                    table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
                    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                    th {{ background-color: #f2f2f2; }}
                    tr:nth-child(even) {{ background-color: #f9f9f9; }}
                    .summary {{ background-color: #eef; padding: 10px; margin-bottom: 20px; border-radius: 5px; }}
                    .booking-section {{ margin-bottom: 30px; border-bottom: 1px solid #ddd; padding-bottom: 15px; }}
                    .booking-summary {{ background-color: #f8f8f8; padding: 10px; margin-bottom: 10px; border-radius: 5px; }}
                    .total {{ font-weight: bold; }}
                </style>
            </head>
            <body>
                <h2>Daglig Salgsrapport</h2>
                
                <div class="summary">
                    <p><strong>Rapportperiode:</strong> {yesterday.strftime('%d-%m-%Y')} til {today.strftime('%d-%m-%Y')}</p>
                    <p><strong>Genereret:</strong> {today.strftime('%d-%m-%Y %H:%M:%S')}</p>
                    <p><strong>Totalt salg:</strong> {total_sales} kr.</p>
                    <p><strong>Total kWh solgt:</strong> {total_kwh} kWh</p>
                    <p><strong>Antal booking:</strong> {len(booking_purchases)}</p>
                    <p><strong>Antal køb:</strong> {len(purchases)}</p>
                </div>
                
                {booking_sections}
                
                <p>Denne rapport er genereret automatisk af strømstyringssystemet.</p>
            </body>
            </html>
            """
        
        # Opret e-mail
        msg = Message(
            subject=f"Daglig Salgsrapport - {today.strftime('%d-%m-%Y')}",
            recipients=[recipient_email],
            html=html_content,
            sender='peter@jellingcamping.dk'
        )
        
        # Send e-mail
        with app.app_context():
            mail.send(msg)
        
        logger.info(f"Salgsrapport er blevet sendt til {recipient_email}")
        return True, "Rapport afsendt korrekt"
        
    except Exception as e:
        error_msg = f"Fejl ved generering og afsendelse af salgsrapport: {e}"
        logger.error(error_msg)
        return False, error_msg
    
    finally:
        # Sørg for at lukke database forbindelsen
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# Hvis scriptet køres direkte, send en rapport
if __name__ == "__main__":
    success, message = send_sales_report_email()
    print(f"Rapport: {message}")
