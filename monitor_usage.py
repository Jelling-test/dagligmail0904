#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time
import mysql.connector
from mysql.connector import Error
import requests
from dotenv import load_dotenv
from datetime import datetime
import traceback

# Indlæs miljøvariabler
load_dotenv()

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'camping_stroem'),
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
        return connection
    except Error as e:
        print(f"Fejl ved forbindelse til database: {e}")
        return None

def normalize_meter_id_helper(meter_id, include_energy_total=True):
    """
    Normaliserer et meter_id til det korrekte format for Home Assistant API.
    Returnerer None ved ugyldigt input.
    """
    if not meter_id or not isinstance(meter_id, str):
        print(f"WARN normalize_meter_id_helper: Ugyldigt input: {meter_id}")
        return None

    normalized = meter_id.strip()

    if not normalized.startswith('sensor.'):
        normalized = f"sensor.{normalized}"

    # Forbedret logik for at tilføje _energy_total suffix
    known_suffixes = ["_energy_total", "_power", "_voltage", "_current", "_frequency", "_energy_daily", "_total_increasing"]
    has_known_suffix = any(normalized.endswith(suffix) for suffix in known_suffixes)

    if include_energy_total and not has_known_suffix:
        # Tilføj kun hvis det specifikt ønskes og der ikke allerede er en kendt suffix
        normalized = f"{normalized}_energy_total"
    elif not include_energy_total and normalized.endswith('_energy_total'):
        # Fjern hvis det *ikke* ønskes
        normalized = normalized[:-len('_energy_total')]

    return normalized

def get_meter_value(meter_id):
    """
    Henter den aktuelle værdi for en bestemt måler fra Home Assistant.
    Returnerer None ved fejl eller hvis måler er utilgængelig/ikke-numerisk.
    """
    if not meter_id: return None

    hass_url = os.getenv('HASS_URL')
    hass_token = os.getenv('HASS_TOKEN')
    if not hass_url or not hass_token:
        print(f"ERROR get_meter_value: Mangler HASS_URL/TOKEN for {meter_id}")
        return None

    # Normaliser ID FØR API kald
    normalized_id = normalize_meter_id_helper(meter_id, include_energy_total=True)
    if not normalized_id:
        print(f"ERROR get_meter_value: Kunne ikke normalisere meter_id: {meter_id}")
        return None

    api_url = f"{hass_url}/api/states/{normalized_id}"
    headers = {"Authorization": f"Bearer {hass_token}"}

    try:
        print(f"DEBUG: Henter målerværdi for {normalized_id}")
        response = requests.get(api_url, headers=headers, timeout=5)
        response.raise_for_status()

        data = response.json()
        state = data.get('state')

        if state is not None and state not in ['unavailable', 'unknown', '']:
            try:
                return float(state)
            except (ValueError, TypeError):
                print(f"WARN: Kunne ikke konvertere state '{state}' til float for {normalized_id}")
                return None

        print(f"DEBUG: Ugyldig/utilgængelig state for {normalized_id}: {state}")
        return None

    except requests.exceptions.Timeout:
        print(f"WARN: Timeout ved hentning af {normalized_id}")
        return None
    except requests.exceptions.RequestException as req_err:
        # Log specifik HTTP fejl hvis muligt
        status_code = getattr(req_err.response, 'status_code', 'N/A')
        print(f"WARN: Netværksfejl for {normalized_id} (Status: {status_code}): {req_err}")
        return None
    except Exception as e:
        print(f"ERROR: Generel fejl for {normalized_id}: {e}")
        traceback.print_exc()
        return None

def get_switch_state(switch_id):
    """
    Henter tilstanden for en kontakt fra Home Assistant.
    Returnerer None ved fejl eller hvis kontakten er utilgængelig.
    """
    if not switch_id: return None

    hass_url = os.getenv('HASS_URL')
    hass_token = os.getenv('HASS_TOKEN')
    if not hass_url or not hass_token:
        print(f"ERROR get_switch_state: Mangler HASS_URL/TOKEN for {switch_id}")
        return None

    # Normaliser ID for kontakt
    normalized_id = switch_id
    if not normalized_id.startswith('switch.'):
        normalized_id = f"switch.{normalized_id}"

    api_url = f"{hass_url}/api/states/{normalized_id}"
    headers = {"Authorization": f"Bearer {hass_token}"}

    try:
        print(f"DEBUG: Henter kontakttilstand for {normalized_id}")
        response = requests.get(api_url, headers=headers, timeout=5)
        response.raise_for_status()

        data = response.json()
        return data.get('state')

    except requests.exceptions.Timeout:
        print(f"WARN: Timeout ved hentning af kontakt {normalized_id}")
        return None
    except requests.exceptions.RequestException as req_err:
        status_code = getattr(req_err.response, 'status_code', 'N/A')
        print(f"WARN: Netværksfejl for kontakt {normalized_id} (Status: {status_code}): {req_err}")
        return None
    except Exception as e:
        print(f"ERROR: Generel fejl for kontakt {normalized_id}: {e}")
        traceback.print_exc()
        return None

def monitor_user_usage(booking_id):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            print("Kunne ikke oprette forbindelse til databasen.")
            return
        
        cursor = conn.cursor(dictionary=True)
        
        # Find brugerens aktive måler
        cursor.execute("""
            SELECT am.meter_id, am.start_value, am.package_size, mc.power_switch_id, mc.display_name
            FROM active_meters am
            LEFT JOIN meter_config mc ON am.meter_id = mc.sensor_id
            WHERE am.booking_id = %s
        """, (booking_id,))
        
        meter_data = cursor.fetchone()
        
        if not meter_data:
            print(f"Ingen aktiv måler fundet for booking ID {booking_id}.")
            return
        
        meter_id = meter_data['meter_id']
        power_switch_id = meter_data.get('power_switch_id')
        start_value = float(meter_data.get('start_value', 0))
        package_size = float(meter_data.get('package_size', 0))
        
        print(f"\n{'=' * 50}")
        print(f"Starter overvågning af bruger {booking_id}")
        print(f"Måler: {meter_id}")
        print(f"Kontakt: {power_switch_id}")
        print(f"Startværdi: {start_value:.3f} kWh")
        print(f"Pakkestørrelse: {package_size:.3f} kWh")
        print(f"{'=' * 50}\n")
        
        # Første måling
        current_value = get_meter_value(meter_id)
        switch_state = get_switch_state(power_switch_id) if power_switch_id else "unknown"
        
        if current_value is None:
            print("Kunne ikke hente målerværdi. Afslutter.")
            return
        
        total_usage = current_value - start_value
        remaining = package_size - total_usage
        
        print(f"{datetime.now().strftime('%H:%M:%S')} - INITIAL:")
        print(f"  Målerværdi: {current_value:.3f} kWh")
        print(f"  Forbrug: {total_usage:.3f} kWh")
        print(f"  Tilbage: {remaining:.3f} kWh")
        print(f"  Kontakt status: {switch_state}")
        
        # Løbende overvågning
        previous_switch_state = switch_state
        try:
            while True:
                time.sleep(2)  # Tjek hver 2. sekund
                
                current_value = get_meter_value(meter_id)
                switch_state = get_switch_state(power_switch_id) if power_switch_id else "unknown"
                
                if current_value is None:
                    print("Kunne ikke hente målerværdi.")
                    continue
                
                total_usage = current_value - start_value
                remaining = package_size - total_usage
                
                # Vis kun hvis der er ændringer eller hver 10. gang
                if switch_state != previous_switch_state:
                    print(f"\n{datetime.now().strftime('%H:%M:%S')} - KONTAKT ÆNDRING:")
                    print(f"  Målerværdi: {current_value:.3f} kWh")
                    print(f"  Forbrug: {total_usage:.3f} kWh")
                    print(f"  Tilbage: {remaining:.3f} kWh")
                    print(f"  Kontakt status: {switch_state} (var: {previous_switch_state})")
                    
                    if previous_switch_state == "on" and switch_state == "off":
                        print(f"\n{'!' * 50}")
                        print(f"SYSTEMET HAR SLUKKET FOR STRØMMEN!")
                        print(f"Tidspunkt: {datetime.now().strftime('%H:%M:%S')}")
                        print(f"Målerværdi ved slukning: {current_value:.3f} kWh")
                        print(f"Totalt forbrug: {total_usage:.3f} kWh")
                        print(f"Pakkestørrelse: {package_size:.3f} kWh")
                        print(f"{'!' * 50}\n")
                    
                    previous_switch_state = switch_state
                else:
                    print(f"{datetime.now().strftime('%H:%M:%S')} - Status:")
                    print(f"  Målerværdi: {current_value:.3f} kWh")
                    print(f"  Forbrug: {total_usage:.3f} kWh")
                    print(f"  Tilbage: {remaining:.3f} kWh")
                    print(f"  Kontakt status: {switch_state}")
                
        except KeyboardInterrupt:
            print("\nOvervågning afbrudt af bruger.")
    
    except Error as db_err:
        print(f"Databasefejl: {db_err}")
    except Exception as e:
        print(f"Generel fejl: {e}")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

if __name__ == "__main__":
    # Overvåg bruger 41967's forbrug
    booking_id = "41967"
    
    print(f"Starter overvågning af bruger {booking_id}...")
    monitor_user_usage(booking_id)
