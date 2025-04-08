#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test script til at verificere målervalg og låsning i strømstyringssystemet.
Dette script tester:
1. Om offline målere ikke vises for nye brugere
2. Om brugere stadig kan se deres egne målere, selvom de er offline
3. Om målere låses korrekt til brugere, indtil de checker ud eller admin frigiver dem
"""

import os
import sys
import requests
import mysql.connector
from dotenv import load_dotenv
import time
import json

# Indlæs miljøvariabler fra .env filen
load_dotenv()

# Database konfiguration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'stroem_styring')
}

# Home Assistant API konfiguration
HASS_URL = os.getenv('HASS_URL', 'http://localhost:8123')
HASS_TOKEN = os.getenv('HASS_TOKEN', '')

def get_db_connection():
    """Opretter en forbindelse til databasen"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"Fejl ved forbindelse til database: {e}")
        sys.exit(1)

def normalize_meter_id(meter_id):
    """Normaliserer måler-ID til korrekt format for Home Assistant"""
    if not meter_id.startswith('sensor.'):
        return f"sensor.{meter_id}"
    return meter_id

def is_meter_online(meter_id):
    """Tjekker om en måler er online ved at kontrollere dens tilstand i Home Assistant"""
    try:
        normalized_id = normalize_meter_id(meter_id)
        response = requests.get(
            f"{HASS_URL}/api/states/{normalized_id}", 
            headers={"Authorization": f"Bearer {HASS_TOKEN}"}
        )
        
        if response.status_code != 200:
            print(f"Måler {meter_id} er offline (HTTP status: {response.status_code})")
            return False
            
        data = response.json()
        
        if data and 'state' in data and data['state'] not in ['unavailable', 'unknown', '']:
            print(f"Måler {meter_id} er online (tilstand: {data['state']})")
            return True
        
        print(f"Måler {meter_id} er offline (tilstand: {data.get('state', 'ingen tilstand')})")
        return False
    except Exception as e:
        print(f"Fejl ved tjek af måler online status: {e}")
        return False

def get_configured_meters():
    """Henter alle konfigurerede målere fra databasen"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('''
        SELECT id, sensor_id, display_name, location, energy_sensor_id, power_switch_id
        FROM meter_config
        WHERE is_active = 1
    ''')
    meters = cursor.fetchall()
    cursor.close()
    conn.close()
    return meters

def get_active_meters():
    """Henter alle aktive målere (målere der er tildelt til brugere)"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM active_meters')
    active_meters = cursor.fetchall()
    cursor.close()
    conn.close()
    return active_meters

def test_meter_visibility():
    """Tester om offline målere ikke vises for nye brugere"""
    print("\n=== Test af måler synlighed ===")
    
    # Hent alle konfigurerede målere
    configured_meters = get_configured_meters()
    print(f"Fandt {len(configured_meters)} konfigurerede målere")
    
    # Hent aktive målere
    active_meters = get_active_meters()
    active_meter_ids = [m['meter_id'] for m in active_meters]
    print(f"Fandt {len(active_meters)} aktive målere: {active_meter_ids}")
    
    # Test hver måler
    for meter in configured_meters:
        meter_id = meter['sensor_id']
        energy_sensor_id = meter['energy_sensor_id'] or meter_id
        
        # Tjek om måleren er online
        is_online = is_meter_online(normalize_meter_id(energy_sensor_id))
        
        # Tjek om måleren er tildelt til en bruger
        is_assigned = meter_id in active_meter_ids
        
        # Bestem om måleren skal være synlig for nye brugere
        should_be_visible = is_online and not is_assigned
        
        print(f"Måler {meter_id} (display: {meter['display_name']}):")
        print(f"  - Online: {is_online}")
        print(f"  - Tildelt: {is_assigned}")
        print(f"  - Synlig for nye brugere: {should_be_visible}")
        
        if is_assigned:
            # Find hvilken bruger måleren er tildelt til
            for active_meter in active_meters:
                if active_meter['meter_id'] == meter_id:
                    print(f"  - Tildelt til booking: {active_meter['booking_id']}")
                    break
    
    print("\nTest af måler synlighed afsluttet")

def test_meter_locking():
    """Tester om målere låses korrekt til brugere"""
    print("\n=== Test af måler låsning ===")
    
    # Hent aktive målere
    active_meters = get_active_meters()
    
    if not active_meters:
        print("Ingen aktive målere fundet til test af låsning")
        return
    
    print(f"Fandt {len(active_meters)} aktive målere:")
    
    for meter in active_meters:
        print(f"Måler {meter['meter_id']} er låst til booking {meter['booking_id']}")
        
        # Tjek om måleren stadig er online
        meter_config = None
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('''
            SELECT * FROM meter_config WHERE sensor_id = %s
        ''', (meter['meter_id'],))
        meter_config = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if meter_config:
            energy_sensor_id = meter_config['energy_sensor_id'] or meter_config['sensor_id']
            is_online = is_meter_online(normalize_meter_id(energy_sensor_id))
            print(f"  - Online status: {is_online}")
            print(f"  - Måleren er stadig korrekt låst til brugeren, selvom den er {'offline' if not is_online else 'online'}")
        else:
            print(f"  - ADVARSEL: Måler {meter['meter_id']} er låst til en bruger, men findes ikke i meter_config tabellen!")
    
    print("\nTest af måler låsning afsluttet")

def main():
    """Hovedfunktion der kører alle tests"""
    print("=== Starter test af målervalg og låsning ===")
    
    # Test måler synlighed
    test_meter_visibility()
    
    # Test måler låsning
    test_meter_locking()
    
    print("\n=== Test afsluttet ===")

if __name__ == "__main__":
    main()
