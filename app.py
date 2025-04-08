# -*- coding: utf-8 -*-
import os
import requests
from datetime import datetime, timedelta
from functools import wraps
import time
import traceback

import mysql.connector
from mysql.connector import Error, pooling
from mysql.connector.cursor import MySQLCursorDict

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_caching import Cache
from apscheduler.schedulers.background import BackgroundScheduler
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_key')

# --- Cache Konfiguration ---
cache_config = { "CACHE_TYPE": os.getenv('CACHE_TYPE', 'SimpleCache'), "CACHE_DEFAULT_TIMEOUT": int(os.getenv('CACHE_DEFAULT_TIMEOUT', 300)) }
if cache_config['CACHE_TYPE'].lower() == 'redis': cache_config["CACHE_REDIS_URL"] = os.getenv('CACHE_REDIS_URL', 'redis://localhost:6379/0')
app.config.from_mapping(cache_config); cache = Cache(app); print(f"Cache: {app.config['CACHE_TYPE']}")

# --- Database Connection Pooling ---
db_pool = None
def init_db_pool():
    global db_pool
    try:
        pool_config = { "host": os.getenv('DB_HOST'), "user": os.getenv('DB_USER'), "password": os.getenv('DB_PASSWORD'), "database": os.getenv('DB_NAME'), "pool_name": os.getenv('DB_POOL_NAME', "flask_pool"), "pool_size": int(os.getenv('DB_POOL_SIZE', 30)), "pool_reset_session": True, }
        pool_config = {k: v for k, v in pool_config.items() if v is not None}
        print(f"Initialiserer DB pool '{pool_config.get('pool_name')}' str {pool_config.get('pool_size')}...")
        db_pool = pooling.MySQLConnectionPool(**pool_config)
        test_conn = db_pool.get_connection(); print(f"Pool Test OK (ID: {test_conn.connection_id}). Frigiver..."); test_conn.close(); print("DB pool OK.")
    except Error as e: print(f"FATAL: DB Pool Init Fejl: {e}"); db_pool = None
    except Exception as e: print(f"FATAL: Uventet DB Pool Init Fejl: {ex}"); db_pool = None
def get_db_connection():
    global db_pool;
    if db_pool is None: print("ERROR: DB pool ej init."); return None
    try: conn = db_pool.get_connection(); return conn
    except Error as e: print(f"Fejl hent DB conn: {e}"); return None
def safe_close_connection(conn):
    if conn and conn.is_connected():
        try: conn.close()
        except Error as e: print(f"Fejl frigiv DB conn: {e}")
init_db_pool()

ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'password')
login_manager = LoginManager(); login_manager.init_app(app); login_manager.login_view = 'login'
HASS_URL = os.getenv('HASS_URL')
HASS_TOKEN = os.getenv('HASS_TOKEN')

# --- GLOBALT DEFINERET HJÆLPEFUNKTION ---
def format_number(num):
    try:
        if num is None or isinstance(num, str) and num.lower() in ['n/a', 'ukendt', 'fejl', 'offline', 'unavailable']: return str(num)
        return "{:,.3f}".format(float(num)).replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError): return str(num)

# --- Andre Hjælpefunktioner ---
@cache.cached(timeout=60)
def get_power_meters():
    if not HASS_URL or not HASS_TOKEN: return []
    try:
        resp = requests.get(f"{HASS_URL}/api/states", headers={"Authorization": f"Bearer {HASS_TOKEN}"}, timeout=15)
        resp.raise_for_status(); entities = resp.json(); meters = []
        for e in entities:
            eid = e['entity_id']
            if eid.startswith('sensor.') and ('energy' in eid.lower() or 'power' in eid.lower() or 'obk' in eid.lower()):
                try:
                    s = e['state']; fs = 0.0
                    if s not in ['unavailable','unknown','']:
                        try: fs = float(s)
                        except (ValueError, TypeError): pass
                    meters.append({'id':eid,'entity_id':eid,'name':e['attributes'].get('friendly_name',eid),'state':s,'float_state':fs,'unit':e['attributes'].get('unit_of_measurement','kWh')})
                except Exception as ex: print(f"Fejl process sensor {eid}: {ex}")
        return meters
    except requests.exceptions.RequestException as e: print(f"Fejl HA meters (req): {e}"); return []
    except Exception as e: print(f"Fejl HA meters: {e}"); return []

def normalize_meter_id(meter_id, include_energy_total=True):
    if not meter_id: return None; meter_id = meter_id.strip()
    if not meter_id.startswith('sensor.'): meter_id = f"sensor.{meter_id}"
    suffixes = ['_energy_total','_power','_current','_voltage']; has_suffix = any(meter_id.endswith(s) for s in suffixes)
    if include_energy_total and not has_suffix: meter_id = f"{meter_id}_energy_total"
    return meter_id

@cache.cached(timeout=15, key_prefix='meter_value_')
def get_meter_value(meter_id_original):
    if not meter_id_original or not HASS_URL or not HASS_TOKEN: return None
    # Normalisér meter_id
    id1 = normalize_meter_id(meter_id_original, False)
    id2 = normalize_meter_id(meter_id_original, True)
    
    # Forsøg først med den mest sandsynlige version
    for meter_id in [id2, id1]:  # Prøv først med _energy_total
        try:
            print(f"DEBUG: Forsøger at hente værdi for {meter_id}")
            r = requests.get(f"{HASS_URL}/api/states/{meter_id}", 
                            headers={"Authorization": f"Bearer {HASS_TOKEN}"},
                            timeout=10)
            if r.status_code == 200:
                rj = r.json()
                if "state" in rj and rj["state"] not in ["unavailable", "unknown", None]:
                    try:
                        val = float(rj["state"])
                        print(f"SUCCESS get: Val={val} for {meter_id}")
                        return val
                    except (ValueError, TypeError):
                        print(f"WARN get: Ugyldig værdi '{rj['state']}' for {meter_id}")
                else:
                    print(f"WARN get: Ugyldig state for {meter_id}")
            else:
                print(f"WARN get: HTTP {r.status_code} for {meter_id}")
        except Exception as e:
            print(f"WARN get: Exception for {meter_id}: {e}")
    return None

def get_switch_state(switch_id):
    if not switch_id or not HASS_URL or not HASS_TOKEN: return "unknown"
    try:
        url = f"{HASS_URL}/api/states/{switch_id}"; headers = {"Authorization": f"Bearer {HASS_TOKEN}"}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200: return response.json().get('state', 'unknown')
        else: print(f"WARN get_switch_state: Fik status {response.status_code} for {switch_id}"); return "unknown"
    except requests.exceptions.RequestException as e: print(f"ERR get_switch_state ({switch_id}): {e}"); return "unknown"
    except Exception as e: print(f"ERR get_switch_state gen ({switch_id}): {e}"); return "unknown"

def get_formatted_timestamp(format_str=None):
    if not format_str:
        try:
            format_str=cache.get('timestamp_format')
            if not format_str:
                conn=get_db_connection();
                if conn: cursor=conn.cursor(dictionary=True); cursor.execute('SELECT value FROM system_settings WHERE setting_key=%s',('timestamp_format',)); setting=cursor.fetchone(); cursor.close(); safe_close_connection(conn); format_str=setting['value'] if setting else '%Y-%m-%d %H:%M:%S'; cache.set('timestamp_format',format_str,timeout=3600)
                else: format_str='%Y-%m-%d %H:%M:%S'
        except Exception as e: print(f"WARN timestamp format: {e}"); format_str='%Y-%m-%d %H:%M:%S'
    try: return datetime.now().strftime(format_str or '%Y-%m-%d %H:%M:%S')
    except ValueError: print(f"WARN: Ugyldigt timestamp format '{format_str}'. Bruger fallback."); return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def get_configured_meters():
    meters=[]; conn=None; cursor=None
    try:
        conn=get_db_connection()
        if not conn: print("ERR get_cfg_meters: No DB conn."); return []
        cursor=conn.cursor(dictionary=True); cursor.execute('SELECT * FROM meter_config WHERE is_active=1'); meters=cursor.fetchall()
    except Error as e: print(f"ERR get_cfg_meters (DB): {e}"); meters=[]
    except Exception as e: print(f"ERR get_cfg_meters (Gen): {e}"); meters=[]
    finally:
        if cursor: cursor.close()
        if conn: safe_close_connection(conn)
    return meters

# --- System Indstillinger Funktioner ---
def get_system_settings():
    settings = cache.get('system_settings_all');
    if settings is not None: return settings
    print("DEBUG: Henter sys settings fra DB (cache miss).")
    settings = {}; conn = None; cursor = None
    try:
        conn = get_db_connection()
        if conn: cursor = conn.cursor(dictionary=True); cursor.execute("SELECT setting_key, value FROM system_settings"); settings = {r['setting_key']: r['value'] for r in cursor.fetchall()}; cache.set('system_settings_all', settings, timeout=600); print(f"DEBUG: Cachede {len(settings)} sys settings.")
        else: print("ERROR get_system_settings: No DB conn.")
    except Error as db_e: print(f"FEJL hent sys settings DB: {db_e}")
    finally:
        if cursor: cursor.close()
        if conn: safe_close_connection(conn)
    return settings

def update_system_setting(key, value):
    conn = None; cursor = None; success = False
    try:
        conn = get_db_connection()
        if conn:
             cursor = conn.cursor()
             cursor.execute("REPLACE INTO system_settings (setting_key, value) VALUES (%s, %s)", (key, value))
             conn.commit(); success = True
             cache.delete('system_settings_all')
             if key == 'timestamp_format': cache.delete('timestamp_format')
             if key == 'unit_text': cache.delete('system_settings_display')
             print(f"DEBUG update_system_setting: Opdaterede {key}")
        else:
             print(f"FEJL: DB fejl ved opdatering af {key}.")
    except Error as db_e:
        print(f"FEJL DB opdatering {key}: {db_e}")
        if conn: conn.rollback()
    except Exception as e:
        print(f"FEJL opdatering {key}: {str(e)}")
        if conn: conn.rollback()
    finally:
        if cursor: cursor.close()
        if conn: safe_close_connection(conn)
    return success

# Sprog oversættelser
translations = {
    'da': { 'welcome': 'Velkommen', 'power_management': 'Strømstyring', 'manage_power': 'Administrer dit strømforbrug', 'login_prompt': 'Log ind med dit booking nummer', 'login_button': 'Log ind', 'logout_button': 'Log ud', 'current_usage': 'Aktuelt forbrug', 'daily_usage': 'Dagens forbrug', 'total_usage': 'Samlet forbrug', 'usage_history': 'Forbrugshistorik', 'updated': 'Opdateret', 'total_today': 'Total for i dag', 'total_period': 'For hele perioden', 'select_meter': 'Vælg måler', 'search_meter': 'Søg efter måler...', 'no_meter_selected': 'Ingen målere fundet', 'meter_already_active': 'Denne måler er allerede i brug', 'meter_info': 'Målerinfo', 'start_value': 'Startværdi', 'current_value': 'Nuværende værdi', 'remaining': 'Tilbage', 'last_24h_usage': 'Forbrug sidste 24t', 'package_info': 'Pakkeinformation', 'remaining_of': 'tilbage af', 'units': 'enheder', 'time': 'Tidspunkt', 'select_package': 'Vælg Strømpakke', 'buy_package': 'Køb pakke', 'buy_addon': 'Køb tillægspakke', 'addon_packages': 'Tillægspakker', 'error_no_meter': 'Ingen måler valgt', 'error_invalid_meter': 'Ugyldig måler', 'error_db_connection': 'Kunne ikke forbinde til databasen', 'success_meter_selected': 'Måler valgt med succes', 'error_reading_meter': 'Fejl ved læsning af måler', 'error_no_package': 'Ingen pakke valgt', 'error_invalid_package': 'Ugyldig pakke', 'error_no_active_package': 'Du skal have en aktiv pakke før du kan købe tillægspakker', 'success_package_purchased': 'Pakke købt med succes', 'error_no_configured_meters': 'Ingen målere konfigureret. Kontakt admin.', 'error_invalid_values': 'Ugyldige værdier for din måler.', 'error_reading_data': 'Fejl ved hentning af data.', 'login_error_missing': 'Indtast booking nr og efternavn.', 'login_error_invalid': 'Ugyldigt booking nr eller efternavn.', 'login_error_generic': 'Login fejl. Prøv igen.', 'logout_message': 'Du er nu logget ud.', 'error_general': 'Generel fejl', 'error_no_active_meter': 'Ingen aktiv måler. Vælg måler.' },
    'en': { 'welcome': 'Welcome', 'power_management': 'Power Management', 'manage_power': 'Manage Power', 'login_prompt': 'Log in with booking number', 'login_button': 'Log in', 'logout_button': 'Log out', 'current_usage': 'Current Usage', 'daily_usage': 'Daily Usage', 'total_usage': 'Total Usage', 'usage_history': 'Usage History', 'updated': 'Updated', 'total_today': 'Total today', 'total_period': 'Total period', 'select_meter': 'Select Meter', 'search_meter': 'Search meter...', 'no_meter_selected': 'No meters found', 'meter_already_active': 'Meter already in use', 'meter_info': 'Meter Info', 'start_value': 'Start Value', 'current_value': 'Current Value', 'remaining': 'Remaining', 'last_24h_usage': 'Usage last 24h', 'package_info': 'Package Info', 'remaining_of': 'remaining of', 'units': 'units', 'time': 'Time', 'select_package': 'Select Power Package', 'buy_package': 'Buy Package', 'buy_addon': 'Buy Add-on', 'addon_packages': 'Add-on Packages', 'error_no_meter': 'No meter selected', 'error_invalid_meter': 'Invalid meter', 'error_db_connection': 'DB connection failed', 'success_meter_selected': 'Meter selected', 'error_reading_meter': 'Error reading meter', 'error_no_package': 'No package selected', 'error_invalid_package': 'Invalid package', 'error_no_active_package': 'Need active package for add-ons', 'success_package_purchased': 'Package purchased', 'error_no_configured_meters': 'No meters configured. Contact admin.', 'error_invalid_values': 'Invalid DB values for meter.', 'error_reading_data': 'Error retrieving data.', 'login_error_missing': 'Enter booking nr and last name.', 'login_error_invalid': 'Invalid booking nr or last name.', 'login_error_generic': 'Login error. Try again.', 'logout_message': 'Logged out.', 'error_general': 'General Error', 'error_no_active_meter': 'No active meter. Select meter.' },
    'de': { 'welcome': 'Willkommen', 'power_management': 'Stromverwaltung', 'manage_power': 'Strom verwalten', 'login_prompt': 'Anmelden mit Buchungsnummer', 'login_button': 'Anmelden', 'logout_button': 'Abmelden', 'current_usage': 'Akt. Verbrauch', 'daily_usage': 'Tagesverbrauch', 'total_usage': 'Gesamtverbrauch', 'usage_history': 'Verlauf', 'updated': 'Aktualisiert', 'total_today': 'Gesamt heute', 'total_period': 'Gesamt Zeitraum', 'select_meter': 'Zähler wählen', 'search_meter': 'Suche Zähler...', 'no_meter_selected': 'Keine Zähler gefunden', 'meter_already_active': 'Zähler bereits aktiv', 'meter_info': 'Zählerinfo', 'start_value': 'Startwert', 'current_value': 'Akt. Wert', 'remaining': 'Verbleibend', 'last_24h_usage': 'Verbrauch 24h', 'package_info': 'Paketinfo', 'remaining_of': 'verbleibend von', 'units': 'Einheiten', 'time': 'Zeit', 'select_package': 'Strompaket wählen', 'buy_package': 'Paket kaufen', 'buy_addon': 'Add-on kaufen', 'addon_packages': 'Add-on-Pakete', 'error_no_meter': 'Kein Zähler gewählt', 'error_invalid_meter': 'Ungültiger Zähler', 'error_db_connection': 'DB Verbindung fehlgeschlagen', 'success_meter_selected': 'Zähler gewählt', 'error_reading_meter': 'Fehler Zählerstand', 'error_no_package': 'Kein Paket gewählt', 'error_invalid_package': 'Ungültiges Paket', 'error_no_active_package': 'Aktives Paket für Add-ons nötig', 'success_package_purchased': 'Paket gekauft', 'error_no_configured_meters': 'Keine Zähler konfiguriert. Admin kontaktieren.', 'error_invalid_values': 'Ungültige DB-Werte für Zähler.', 'error_reading_data': 'Fehler Datenabruf.', 'login_error_missing': 'Buchungsnr./Nachname eingeben.', 'login_error_invalid': 'Ungültige Buchungsnr./Nachname.', 'login_error_generic': 'Login Fehler. Erneut versuchen.', 'logout_message': 'Abgemeldet.', 'error_general': 'Allg. Fehler', 'error_no_active_meter': 'Kein aktiver Zähler. Zähler wählen.' }
    # Tilføj evt. flere sprog
}

# User class
class User(UserMixin):
    def __init__(self, id, username, fornavn=None, efternavn=None, email=None, is_admin=False): self.id=str(id); self.username=username; self.fornavn=fornavn; self.efternavn=efternavn; self.email=email; self.is_admin=is_admin

# --- Decorator ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args,**kwargs):
        if not current_user.is_authenticated or not getattr(current_user,'is_admin',False): flash('Admin adgang påkrævet','error'); return redirect(url_for('admin_login_or_dashboard',next=request.url))
        return f(*args,**kwargs)
    return decorated_function

# --- load_user ---
@login_manager.user_loader
def load_user(user_id):
    if user_id=="999999": return User(id="999999",username=ADMIN_USERNAME,is_admin=True)
    conn=None; cursor=None; user_obj=None
    try:
        conn=get_db_connection()
        if conn: cursor=conn.cursor(dictionary=True); cursor.execute('SELECT * FROM users WHERE id=%s',(user_id,)); data=cursor.fetchone()
        if data: user_obj=User(id=data['id'],username=data.get('username'),fornavn=data.get('fornavn'),efternavn=data.get('efternavn'),email=data.get('email'),is_admin=False) # Sæt is_admin=False
    except Error as e: print(f"Err load_user DB: {e}")
    except Exception as e: print(f"Err load_user Gen: {e}")
    finally:
        if cursor: cursor.close()
        if conn: safe_close_connection(conn)
    return user_obj


# --- ADMIN ROUTES (DEFINERES FØR ALMINDELIGE ROUTES) ---

@app.route('/systemkontrolcenter23/settings', methods=['GET', 'POST'])
@admin_required
def system_admin_settings():
    if request.method=='POST':
        updated=True; hurl=request.form.get('hass_url','').strip(); htok=request.form.get('hass_token','').strip()
        if hurl and not update_system_setting('hass_url',hurl): updated=False
        if htok and not update_system_setting('hass_token',htok): updated=False
        unit_text=request.form.get('unit_text','kWh').strip(); tformat=request.form.get('timestamp_format','%Y-%m-%d %H:%M:%S').strip()
        try: datetime.now().strftime(tformat)
        except ValueError: flash(f"Ugyldigt format: '{tformat}'. Bruger std.",'warning'); tformat='%Y-%m-%d %H:%M:%S'
        if not update_system_setting('unit_text',unit_text): updated=False
        if not update_system_setting('timestamp_format',tformat): updated=False
        global HASS_URL,HASS_TOKEN;
        if hurl: HASS_URL=hurl; os.environ['HASS_URL']=hurl
        if htok: HASS_TOKEN=htok; os.environ['HASS_TOKEN']=htok
        if updated: flash('Indstillinger opdateret.','success')
        else: flash('Fejl ved opdatering.','danger')
        return redirect(url_for('system_admin_settings'))
    # GET
    cfg=get_system_settings(); display={'hass_url':cfg.get('hass_url',os.getenv('HASS_URL','')), 'hass_token':cfg.get('hass_token',os.getenv('HASS_TOKEN','')), 'admin_username':os.getenv('ADMIN_USERNAME','admin'), 'unit_text':cfg.get('unit_text','kWh'), 'timestamp_format':cfg.get('timestamp_format','%Y-%m-%d %H:%M:%S')}
    return render_template('admin_system_settings.html', settings=display)

@app.route('/systemkontrolcenter23/test-hass-connection', methods=['POST'])
@admin_required
def test_hass_connection():
    url=request.form.get('url'); token=request.form.get('token')
    if not url or not token: flash('URL/Token mangler.','warning'); return redirect(url_for('system_admin_settings'))
    try: headers={'Authorization':f'Bearer {token}'}; api=f"{url.rstrip('/')}/api/"; resp=requests.get(api,headers=headers,timeout=10)
    except requests.exceptions.RequestException as e: flash(f'Fejl: {str(e)}','danger'); return redirect(url_for('system_admin_settings'))
    if resp.status_code==200:
         try: msg=f'Succes! HA OK. Version: {resp.json().get("version","ukendt")}'
         except: msg='Succes! HA OK, men uventet svar.'
         flash(msg,'success')
    else: flash(f'Fejl ({resp.status_code}) HA API ({api}). Svar: {resp.text}','danger')
    return redirect(url_for('system_admin_settings'))

@app.route('/systemkontrolcenter23/adjust-prices', methods=['POST'])
@admin_required
def admin_adjust_prices():
    """Admin: Juster priser på pakker."""
    print(f"DEBUG: Admin {current_user.username} forsøger at justere priser.")
    updated_count = 0
    error_occured = False
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn: raise Error("DB connection failed")
        cursor = conn.cursor() # Standard cursor til UPDATE

        # Iterer gennem alle form data for at finde pris inputs
        for key, value in request.form.items():
            if key.startswith('price_'):
                try:
                    package_id = int(key.split('_')[1])
                    # Håndter komma som decimaltegn og konverter til float
                    new_price = float(value.replace(',', '.'))
                    if new_price < 0:
                        print(f"WARN: Ignorerer negativ pris ({new_price}) for pakke ID {package_id}")
                        continue # Spring over ugyldige priser

                    print(f"DEBUG: Opdaterer pris for pakke ID {package_id} til {new_price}")
                    cursor.execute("""
                        UPDATE stroem_pakker
                        SET pris = %s
                        WHERE id = %s
                    """, (new_price, package_id))

                    if cursor.rowcount > 0:
                        updated_count += 1

                except (ValueError, IndexError, TypeError) as parse_err:
                    print(f"WARN: Kunne ikke parse pris eller ID fra form key '{key}' med værdi '{value}': {parse_err}")
                    error_occured = True # Markér at der skete en fejl
                    continue # Fortsæt til næste pakke

        if error_occured:
            flash('Nogle priser kunne ikke opdateres pga. ugyldigt format.', 'warning')
            if conn: conn.rollback() # Rul alle ændringer tilbage ved fejl
        elif updated_count > 0:
            conn.commit() # Commit alle ændringer samlet
            flash(f'Priserne er blevet opdateret for {updated_count} pakke(r).', 'success')
            print(f"INFO: Admin {current_user.username} opdaterede priser for {updated_count} pakker.")
        else:
            # Ingen ændringer foretaget
            flash('Ingen priser blev ændret (enten ingen ændringer sendt eller ugyldige værdier).', 'info')
            if conn: conn.rollback() # Ingen grund til commit, men rollback skader ikke

    except Error as db_err:
        print(f"ERROR admin_adjust_prices DB: {db_err}")
        flash(f'Databasefejl ved prisjustering: {db_err}', 'danger')
        if conn: conn.rollback()
    except Exception as e:
        print(f"ERROR admin_adjust_prices General: {e}")
        flash(f'Generel fejl ved prisjustering: {str(e)}', 'danger')
        if conn: conn.rollback()
    finally:
        if cursor: cursor.close()
        if conn: safe_close_connection(conn) # Frigiv forbindelse
    return redirect(url_for('admin_login_or_dashboard')) # Gå altid tilbage til admin dashboard

@app.route('/systemkontrolcenter23/get-available-meters') # Tilbage til forventet endpoint
@admin_required
def admin_get_available_configured_meters(): # Behold funktionsnavn
    print("DEBUG admin get avail API"); conn=None; cursor=None; meters=[]
    try:
        cfg=get_configured_meters();
        if not cfg: return jsonify({'success': True, 'meters': []})
        active=set(); conn=get_db_connection()
        if conn: cursor=conn.cursor(dictionary=True); cursor.execute('SELECT DISTINCT meter_id FROM active_meters WHERE meter_id IS NOT NULL'); active={r['meter_id'] for r in cursor.fetchall()}
        meters=[{'id':m['sensor_id'],'name':m.get('display_name') or f"M:{m['sensor_id']}",'location':m.get('location','')} for m in cfg if m['sensor_id'] not in active]
        return jsonify({'success':True, 'meters':meters})
    except Error as db_e: print(f"ERR admin get avail DB: {db_e}"); return jsonify({'success':False,'message':f'DB:{db_e}'}), 500
    except Exception as e: print(f"ERR admin get avail Gen: {e}"); return jsonify({'success':False,'message':f'Err:{str(e)}'}), 500
    finally:
        if cursor: cursor.close()
        if conn: safe_close_connection(conn)

@app.route('/systemkontrolcenter23/connect-meter', methods=['POST'])
@admin_required
def admin_connect_meter_sys():
    """Funktion til at forbinde en måler til en booking."""
    # Hent formulardata
    booking_id = request.form.get('connect_booking_id')
    meter_id = request.form.get('connect_meter_id')
    package_size = request.form.get('connect_package_size')
    
    # Validér input
    if not booking_id or not meter_id or not package_size:
        flash('Alle felter skal udfyldes.', 'error')
        return redirect(url_for('admin_login_or_dashboard'))
    
    # Validér at package_size er et tal
    try:
        package_size = float(package_size)
    except ValueError:
        flash('Antal enheder skal være et tal.', 'error')
        return redirect(url_for('admin_login_or_dashboard'))
    
    # Initialiser database-variabler
    conn = None
    cursor = None
    
    try:
        # Opret forbindelse til databasen
        conn = get_db_connection()
        if not conn:
            flash('Kunne ikke oprette forbindelse til databasen.', 'error')
            return redirect(url_for('admin_login_or_dashboard'))
        
        # Tjek om måleren er ledig
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM active_meters WHERE meter_id = %s", (meter_id,))
        if cursor.fetchone():
            flash('Denne måler er allerede i brug.', 'error')
            return redirect(url_for('admin_login_or_dashboard'))
        
        # Tjek om brugeren findes
        cursor.execute("SELECT * FROM aktive_bookinger WHERE booking_id = %s", (booking_id,))
        if not cursor.fetchone():
            flash('Booking ID findes ikke.', 'error')
            return redirect(url_for('admin_login_or_dashboard'))
        
        # Find meter_config_id baseret på sensor_id
        cursor.execute("SELECT id FROM meter_config WHERE sensor_id=%s", (meter_id,))
        meter_config_result = cursor.fetchone()
        meter_config_id = meter_config_result[0] if meter_config_result else 0
        
        # Hent den aktuelle målerværdi
        current_value = get_meter_value(meter_id) or 0
        
        # Indsæt måleren i active_meters tabellen
        cursor.execute(
            "INSERT INTO active_meters (booking_id, meter_id, start_value, package_size, created_at) VALUES (%s, %s, %s, %s, NOW())", 
            (booking_id, meter_id, current_value, package_size)
        )
        
        # Log handlingen i stroem_koeb tabellen
        log_note = f"Admin tilknyttede måler: {current_user.username}"
        cursor.execute(
            "INSERT INTO stroem_koeb (booking_id, pakke_id, maaler_id, enheder_tilbage) VALUES (%s, %s, %s, %s)",
            (booking_id, 1, meter_config_id, package_size)
        )
        
        # Aktivér målerens kontakt, hvis den har en
        try:
            cursor.execute("SELECT power_switch_id FROM meter_config WHERE sensor_id=%s", (meter_id,))
            cfg = cursor.fetchone()
            if cfg and cfg[0]:  # Hvis måler har en kontakt konfigureret
                psid = cfg[0]
                if HASS_URL and HASS_TOKEN:
                    requests.post(
                        f"{HASS_URL}/api/services/switch/turn_on",
                        headers={"Authorization": f"Bearer {HASS_TOKEN}"},
                        json={"entity_id": psid},
                        timeout=10
                    )
        except Exception as swe:
            print(f"WARN connect switch: {swe}")
        
        # Commit transaktionen
        conn.commit()
        flash(f'Måler {meter_id} er nu tilknyttet booking {booking_id} med {package_size} enheder.', 'success')
        
    except Error as dbe:
        # Håndter database-fejl
        print(f"ERR connect_meter DB: {dbe}")
        flash(f'Database fejl: {dbe}', 'error')
        if conn:
            conn.rollback()
    except Exception as e:
        # Håndter generelle fejl
        print(f"ERR connect_meter Gen: {e}")
        flash(f'Fejl: {str(e)}', 'error')
        if conn:
            conn.rollback()
    finally:
        # Oprydning
        if cursor:
            cursor.close()
        if conn:
            safe_close_connection(conn)
    
    # Omdiriger til admin dashboard
    return redirect(url_for('admin_login_or_dashboard'))

@app.route('/systemkontrolcenter23/add-units', methods=['POST'])
@admin_required
def admin_add_units():
    bid=request.form.get('booking_id'); ustr=request.form.get('units'); mid_input=request.form.get('meter_id_for_add'); conn=None; cursor=None
    if not all([bid,ustr,mid_input]): flash('Alle felter kræves.','warning'); return redirect(url_for('admin_login_or_dashboard'))
    try: units=float(ustr.replace(',','.')); assert units > 0
    except: flash('Ugyldigt antal.','warning'); return redirect(url_for('admin_login_or_dashboard'))
    try:
        conn=get_db_connection();
        if not conn: raise Error("DB fail")
        cursor=conn.cursor(dictionary=True); cursor.execute("SELECT id FROM active_meters WHERE booking_id=%s AND meter_id=%s",(bid,mid_input)); connection=cursor.fetchone();
        if not connection: flash(f'Måler {mid_input} ej aktiv for {bid}.','warning'); raise Exception("Conn not found")
        print(f"DEBUG: Tilføjer {units} til {mid_input} for {bid}.")
        upd_cursor=conn.cursor(); upd_cursor.execute("UPDATE active_meters SET package_size=package_size+%s WHERE id=%s",(units,connection['id'])); rows=upd_cursor.rowcount; upd_cursor.close()
        if rows>0:
            try: # Log
                 log_cursor=conn.cursor(); log_cursor.execute("""INSERT INTO package_logs (booking_id, meter_id, package_name, units_added, admin_action, notes, action_timestamp) VALUES (%s,%s,%s,%s,%s,%s,NOW())""",(bid,mid_input,'Manuel Admin Tilføjelse',units,1,f"Admin add {current_user.username}")); log_cursor.close()
            except Error as loge: print(f"WARN log add: {loge}")
            except Exception as logge: print(f"WARN log add Gen: {logge}")
            conn.commit(); flash(f'Tilføjet {units} til {mid_input} ({bid}).','success')
        else: conn.rollback(); flash(f'Opdatering fejlede for {mid_input}.','danger')
    except Error as dbe: print(f"ERR add DB: {dbe}"); flash(f'DB Fejl: {dbe}','danger'); conn.rollback()
    except Exception as e: print(f"ERR add Gen: {e}"); flash(f'Fejl: {str(e)}','danger'); conn.rollback()
    finally:
        if 'upd_cursor' in locals() and upd_cursor: upd_cursor.close()
        if 'log_cursor' in locals() and log_cursor: log_cursor.close()
        if cursor: cursor.close()
        if conn: safe_close_connection(conn)
    return redirect(url_for('admin_login_or_dashboard'))

@app.route('/systemkontrolcenter23/remove-meter', methods=['POST'])
@admin_required
def admin_remove_meter():
    bid=request.form.get('booking_id'); mid=request.form.get('meter_id'); conn=None; cursor=None # Match form navne
    if not bid or not mid: flash('Udfyld felter.','warning'); return redirect(url_for('admin_login_or_dashboard'))
    try:
        conn=get_db_connection();
        if not conn: raise Error("DB fail")
        cursor=conn.cursor(); cursor.execute("DELETE FROM active_meters WHERE booking_id=%s AND meter_id=%s",(bid,mid)); rows=cursor.rowcount
        if rows>0:
            # Ryd cachen for denne måler for at sikre friske værdier
            cache.delete(f"meter_value_{mid}")
            cache.delete(f"meter_value_{normalize_meter_id(mid, True)}")
            cache.delete(f"meter_value_{normalize_meter_id(mid, False)}")
            psid=None;
            try:
                 ccfg=conn.cursor(dictionary=True); ccfg.execute("SELECT power_switch_id FROM meter_config WHERE sensor_id=%s",(mid,)); cfg=ccfg.fetchone(); ccfg.close()
                 if cfg and cfg.get('power_switch_id'): psid=cfg['power_switch_id']
                 elif mid.startswith('sensor.'): base=mid.split('.')[1].split('_')[0]; psid=f"switch.{base}_0"
                 if psid and HASS_URL and HASS_TOKEN: requests.post(f"{HASS_URL}/api/services/switch/turn_off",headers={"Authorization":f"Bearer {HASS_TOKEN}"},json={"entity_id":psid},timeout=10)
            except Exception as swe: print(f"WARN remove switch: {swe}")
            try: # Log (med korrekte parametre)
                 log_cursor=conn.cursor()
                 # FJERN switch_id fra INSERT
                 log_cursor.execute("""INSERT INTO package_logs (booking_id, meter_id, package_name, units_added, admin_action, notes, action_timestamp) VALUES (%s,%s,'Fjernet (Admin)',0,1,%s,NOW())""",(bid,mid,f"Admin remove: {current_user.username}")); log_cursor.close()
            except Error as loge: print(f"WARN remove log: {loge}")
            except Exception as logge: print(f"WARN remove log Gen: {logge}")
            conn.commit(); flash(f'Måler {mid} fjernet fra {bid}.','success')
        else: flash(f'Ingen link {mid}/{bid}.','warning'); conn.rollback()
    except Error as dbe: print(f"ERR remove DB: {dbe}"); flash(f'DB Fejl: {dbe}','danger'); conn.rollback()
    except Exception as e: print(f"ERR remove Gen: {e}"); flash(f'Fejl: {str(e)}','danger'); conn.rollback()
    finally:
        if 'ccfg' in locals() and ccfg: ccfg.close()
        if 'log_cursor' in locals() and log_cursor: log_cursor.close()
        if cursor: cursor.close()
        if conn: safe_close_connection(conn)
    return redirect(url_for('admin_login_or_dashboard'))

@app.route('/admin/meter_config', methods=['GET', 'POST'])
@admin_required
def admin_meter_config():
    conn=None; cursor=None; form_data=None; ha_sensors=[]; ha_switches=[]; cfgs=[]
    if request.method == 'POST':
        form_data=request.form; cid=form_data.get('config_id'); sid=form_data.get('sensor_id'); dname=form_data.get('display_name'); loc=form_data.get('location'); active=1 if form_data.get('is_active') else 0; esid=form_data.get('energy_sensor_id') or None; psid=form_data.get('power_switch_id') or None
        if not sid or not dname: flash('Sensor ID/Navn påkrævet.','error')
        elif not sid.startswith('sensor.'): flash('Sensor ID skal starte med "sensor."','warning')
        elif esid and not esid.startswith('sensor.'): flash('Energi ID skal starte med "sensor."','warning')
        elif psid and not psid.startswith('switch.'): flash('Switch ID skal starte med "switch."','warning')
        else:
            try:
                conn=get_db_connection();
                if not conn: raise Error("DB fail")
                cursor=conn.cursor(dictionary=True); cursor.execute("SELECT id FROM meter_config WHERE sensor_id=%s"+(" AND id!=%s" if cid else ""), (sid,cid) if cid else (sid,)); cfg=cursor.fetchone()
                if cfg: flash(f'Sensor ID {sid} eksisterer.','error')
                else: # Gem/Opdater
                    if cid: sql,params='''UPDATE meter_config SET sensor_id=%s,display_name=%s,location=%s,is_active=%s,energy_sensor_id=%s,power_switch_id=%s WHERE id=%s''', (sid,dname,loc,active,esid,psid,cid); msg='Opdateret.'
                    else: sql,params='''INSERT INTO meter_config (sensor_id,display_name,location,is_active,energy_sensor_id,power_switch_id) VALUES (%s,%s,%s,%s,%s,%s)''', (sid,dname,loc,active,esid,psid); msg='Tilføjet.'
                    cursor.execute(sql, params); conn.commit(); flash(msg,'success'); form_data=None; return redirect(url_for('admin_meter_config'))
            except Error as dbe: flash(f'DB Fejl: {dbe}','error'); print(f"ERR mtr_cfg POST DB: {dbe}"); conn.rollback()
            except Exception as e: flash(f'Fejl: {str(e)}','error'); print(f"ERR mtr_cfg POST Gen: {e}"); conn.rollback()
            finally:
                if cursor: cursor.close()
                if conn: safe_close_connection(conn)
    # GET
    try:
        if HASS_URL and HASS_TOKEN:
             resp=requests.get(f"{HASS_URL}/api/states",headers={"Authorization":f"Bearer {HASS_TOKEN}"},timeout=10)
             if resp.status_code==200:
                  entities = resp.json(); ha_sensors=[{'id':e['entity_id'],'name':e['attributes'].get('friendly_name',e['entity_id'])} for e in entities if e['entity_id'].startswith('sensor.')]; ha_sensors.sort(key=lambda x:x['id']); ha_switches=[{'id':e['entity_id'],'name':e['attributes'].get('friendly_name',e['entity_id'])} for e in entities if e['entity_id'].startswith('switch.')]; ha_switches.sort(key=lambda x:x['id'])
             else: flash(f'HA Fejl {resp.status_code}','warning')
        else: flash('HA config mangler.','warning')
        conn=get_db_connection()
        if conn: cursor=conn.cursor(dictionary=True); cursor.execute('SELECT * FROM meter_config ORDER BY display_name'); cfgs=cursor.fetchall()
        else: flash('DB Fejl hentning.','error')
    except requests.exceptions.RequestException as req_e: flash(f'HA Fejl: {req_e}','error')
    except Error as dbe: flash(f'DB Fejl: {dbe}','error')
    except Exception as e: flash(f'Fejl: {str(e)}','error')
    finally:
        if cursor: cursor.close()
        if conn: safe_close_connection(conn)
    
    # Organiser sensorer i grupper baseret på navne
    sensor_groups = {}
    for sensor in ha_sensors:
        # Opdel sensor-id'et for at få basisnavnet (f.eks. "sensor.kanal1_power" -> "kanal1")
        parts = sensor['id'].split('.')
        if len(parts) > 1:
            base_name = parts[1].split('_')[0]  # Tager første del før underscore
            if base_name not in sensor_groups:
                sensor_groups[base_name] = []
            sensor_groups[base_name].append(sensor)
    
    return render_template('admin_meter_config.html', ha_sensors=ha_sensors, ha_switches=ha_switches, configured_meters=cfgs, form_data=form_data, sensor_groups=sensor_groups)

@app.route('/admin/delete_meter_config/<int:config_id>', methods=['POST'])
@admin_required
def delete_meter_config(config_id):
    conn=None; cursor=None
    try:
        conn=get_db_connection();
        if not conn: raise Error("DB fail")
        cursor=conn.cursor(dictionary=True); cursor.execute("SELECT sensor_id FROM meter_config WHERE id=%s",(config_id,)); cfg=cursor.fetchone()
        if not cfg: flash(f'ID {config_id} ej fundet.','warning')
        else:
             sid=cfg['sensor_id']; cursor.execute("SELECT id FROM active_meters WHERE meter_id=%s LIMIT 1",(sid,))
             if cursor.fetchone(): flash(f'Fejl: {sid} i brug.','error')
             else:
                  cd=conn.cursor(); cd.execute('DELETE FROM meter_config WHERE id=%s',(config_id,)); deleted=cd.rowcount; cd.close()
                  if deleted>0: conn.commit(); flash(f'Konfig {sid} slettet.','success')
                  else: conn.rollback(); flash(f'Fejl slet {config_id}.','error')
    except Error as db_e: flash(f'DB Fejl: {db_e}','danger'); conn.rollback()
    except Exception as e: flash(f'Fejl: {str(e)}','danger'); conn.rollback()
    finally:
        if 'cd' in locals() and cd: cd.close()
        if cursor: cursor.close()
        if conn: safe_close_connection(conn)
    return redirect(url_for('admin_meter_config'))

# --- KUN admin login/dashboard route ---
@app.route('/systemkontrolcenter23', methods=['GET', 'POST'])
def admin_login_or_dashboard():
    # Hvis allerede logget ind som admin, vis dashboard
    if current_user.is_authenticated and getattr(current_user, 'is_admin', False):
        if request.method == 'POST': pass # Ignorer POST hvis logget ind
        print(f"DEBUG: Admin {current_user.username} viser dashboard.")
        packages = []; conn = None; cursor = None
        try:
            conn = get_db_connection()
            if conn: cursor = conn.cursor(dictionary=True); cursor.execute("SELECT id, navn, type, enheder, dage, pris FROM stroem_pakker WHERE aktiv = 1 ORDER BY type, enheder, dage, id"); packages = cursor.fetchall()
            else: flash('DB Fejl pakker.', 'warning')
        except Error as e: flash(f'DB Fejl pakker: {str(e)}', 'danger')
        except Exception as e: flash(f'Fejl pakker: {str(e)}', 'danger')
        finally:
            if cursor: cursor.close()
            if conn: safe_close_connection(conn)
        # KORREKT INDRYKNING HER:
        return render_template('admin_dashboard.html', packages=packages)

    # Håndter login forsøg
    if request.method == 'POST':
        username=request.form.get('username'); password=request.form.get('password')
        admin_user_env=os.getenv('ADMIN_USERNAME','admin'); admin_pass_env=os.getenv('ADMIN_PASSWORD','password')
        if username==admin_user_env and password==admin_pass_env:
            admin=User(id="999999",username=admin_user_env,is_admin=True); login_user(admin); print(f"DEBUG: Admin '{admin_user_env}' logget ind.")
            return redirect(url_for('admin_login_or_dashboard'))
        else: print(f"DEBUG: Fejl admin login '{username}'."); flash('Ugyldigt admin login.', 'danger')
        # Vis login
    print("DEBUG: Viser admin login side.")
    return render_template('systemadmin_login.html')


# --- ALMINDELIGE BRUGER ROUTES ---

@app.route('/')
def index():
    lang=session.get('language','da');
    if lang not in translations: lang='da'; session['language']=lang
    trans=translations.get(lang,translations['da'])
    if current_user.is_authenticated:
        if getattr(current_user,'is_admin',False):
             # Omdiriger til den kombinerede admin-route
            return redirect(url_for('admin_login_or_dashboard'))
        return render_template('index.html',current_time=get_formatted_timestamp(),translations=trans)
    else: return render_template('index.html',current_time=get_formatted_timestamp(),translations=trans)

@app.route('/set_language/<lang>')
def set_language(lang):
    if lang in translations:
        session['language']=lang
        if current_user.is_authenticated and not getattr(current_user,'is_admin',False):
            conn=None; cursor=None
            try:
                conn=get_db_connection()
                if conn: cursor=conn.cursor(); cursor.execute("UPDATE users SET language=%s WHERE id=%s",(lang,current_user.id)); conn.commit()
            except Error as e: print(f"Err set_lang DB: {e}"); conn.rollback()
            except Exception as e: print(f"Err set_lang Gen: {e}")
            finally:
                if cursor: cursor.close()
                if conn: safe_close_connection(conn)
    return redirect(request.referrer or url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    lang=session.get('language','da'); trans=translations.get(lang,translations['da'])
    if request.method=='POST':
        username=request.form.get('booking_id'); password=request.form.get('lastname')
        if not username or not password: flash(trans['login_error_missing'],'error'); return redirect(url_for('login'))
        # Admin tjek fjernet her, sker i admin_login_or_dashboard
        conn=None; cursor=None
        try:
            conn=get_db_connection();
            if not conn: flash(trans['error_db_connection'],'error'); return redirect(url_for('login'))
            cursor=conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM aktive_bookinger WHERE booking_id=%s AND LOWER(efternavn)=LOWER(%s)",(username,password)); booking=cursor.fetchone()
            if booking:
                cursor.execute("SELECT * FROM users WHERE username=%s",(username,)); user_data=cursor.fetchone(); hashed_pw=generate_password_hash(password)
                if not user_data: cursor.execute("INSERT INTO users (username,password,fornavn,efternavn,email,language) VALUES (%s,%s,%s,%s,%s,%s)",(username,hashed_pw,booking.get('fornavn',''),booking.get('efternavn',''),booking.get('email',''),lang)); conn.commit(); uid=cursor.lastrowid; user_data={'id':uid,'username':username,'fornavn':booking.get('fornavn',''),'efternavn':booking.get('efternavn',''),'email':booking.get('email','')}
                else:
                    updates={};
                    if booking.get('email') and user_data.get('email')!=booking.get('email'): updates['email']=booking.get('email')
                    if user_data.get('language')!=lang: updates['language']=lang
                    updates['password']=hashed_pw
                    if updates: setc=", ".join([f"{k}=%s" for k in updates]); vals=list(updates.values())+[user_data['id']]; sql=f"UPDATE users SET {setc} WHERE id=%s"; cursor.execute(sql,tuple(vals)); conn.commit()
                    user_data['id']=user_data['id']
                user_obj=User(id=user_data['id'],username=user_data['username'],fornavn=user_data.get('fornavn'),efternavn=user_data.get('efternavn'),email=user_data.get('email'))
                login_user(user_obj); flash(f"{trans.get('welcome')} {user_obj.fornavn or ''} {user_obj.efternavn or ''}!",'success'); return redirect(url_for('index'))
            else: flash(trans['login_error_invalid'],'error')
        except Error as e: print(f"Login DB: {e}"); flash(trans['login_error_generic'],'error'); conn.rollback()
        except Exception as e: print(f"Login Gen: {e}"); flash(trans['login_error_generic'],'error'); conn.rollback()
        finally:
            if cursor: cursor.close()
            if conn: safe_close_connection(conn)
    return render_template('login.html',translations=trans)

@app.route('/logout')
@login_required
def logout():
    lang=session.get('language','da'); trans=translations.get(lang,translations['da'])
    logout_user(); flash(trans['logout_message'],'success'); return redirect(url_for('index'))

@app.route('/stroem_dashboard')
@login_required
def stroem_dashboard():
    lang = session.get('language', 'da'); trans = translations.get(lang, translations['da'])
    conn = None; cursor = None; meter_data = None; error_message = None; is_meter_online_flag = False
    print(f"\n===== START STRØM DASHBOARD (Bruger: {current_user.username}) =====")
    try:
        conn = get_db_connection()
        if not conn: flash(trans['error_db_connection'], 'error'); return redirect(url_for('select_meter'))
        cursor = conn.cursor(dictionary=True)
        settings = cache.get('system_settings_display') or {}
        if not settings: cursor.execute("SELECT setting_key, value FROM system_settings WHERE setting_key IN ('unit_text', 'timestamp_format')"); settings = {item['setting_key']: item['value'] for item in cursor.fetchall()}; cache.set('system_settings_display', settings, timeout=3600)
        unit_text = settings.get('unit_text', 'enheder'); time_format = settings.get('timestamp_format', '%Y-%m-%d %H:%M:%S')
        print(f"DEBUG stroem_dash: Henter måler for '{current_user.username}'")
        cursor.execute('SELECT meter_id, start_value, package_size FROM active_meters WHERE booking_id=%s',(current_user.username,))
        meter_data = cursor.fetchone(); print(f"DEBUG stroem_dash: Rå DB data: {meter_data}")
        if meter_data: meter_id, db_start, db_pkg = meter_data.get('meter_id'), meter_data.get('start_value'), meter_data.get('package_size')
        else: meter_id, db_start, db_pkg = None, None, None
        cursor.close(); cursor = None; safe_close_connection(conn); conn = None # Luk DB
        if not meter_id: print(f"DEBUG stroem_dash: Ingen meter_id for '{current_user.username}'. Redirect."); flash(trans['error_no_active_meter'], 'info'); return redirect(url_for('select_meter'))
        print(f"DEBUG stroem_dash: Fundet meter='{meter_id}'")
        try:
            start_value = float(db_start if db_start is not None else 0.0); package_size = float(db_pkg if db_pkg is not None else 0.0);
        except (ValueError, TypeError) as e: print(f"ERR stroem_dash: Invalid DB vals: {e}"); flash(trans['error_invalid_values'], 'error'); return redirect(url_for('select_meter'))
        if package_size <= 0: package_size = 0.001

        current_value = get_meter_value(meter_id)
        if current_value is None:
            error_message = trans['error_reading_meter']; is_meter_online_flag = False; flash(error_message + " Viser startværdi.", 'warning')
            current_value = start_value # Fallback
            current_value_disp = format_number(current_value) + " (Offline/Fejl)"; start_value_disp = format_number(start_value)
            total_usage_disp = "0,000"; remaining_disp = format_number(package_size); percentage = 0
        else:
            is_meter_online_flag = True; total_usage = current_value - start_value;
            if total_usage < 0: total_usage = current_value
            remaining = max(0, package_size - total_usage); percentage = int(min(100, (total_usage / package_size) * 100)) if package_size > 0.001 else 0
            current_value_disp = format_number(current_value); start_value_disp = format_number(start_value); total_usage_disp = format_number(total_usage); remaining_disp = format_number(remaining)

        power_switch_id = cache.get(f'meter_config_switch_{meter_id}')
        if not power_switch_id:
             conn_sw = get_db_connection()
             if conn_sw: cursor_sw = conn_sw.cursor(dictionary=True); cursor_sw.execute("SELECT power_switch_id FROM meter_config WHERE sensor_id=%s",(meter_id,)); cfg=cursor_sw.fetchone(); cursor_sw.close(); safe_close_connection(conn_sw)
             if cfg and cfg.get('power_switch_id'): power_switch_id = cfg['power_switch_id']; cache.set(f'meter_config_switch_{meter_id}',power_switch_id,timeout=3600)
        if not power_switch_id and meter_id.startswith('sensor.'): base=meter_id.split('.')[1].split('_')[0]; power_switch_id=f"switch.{base}_0"

        power_switch_state = get_switch_state(power_switch_id)
        if is_meter_online_flag and power_switch_state in ['unavailable', 'unknown']: 
            print(f"WARN stroem_dash: Sensor {meter_id} online, men switch {power_switch_id} er {power_switch_state}")
            flash(f"Advarsel: Kan ikke styre strøm, kontakt ({power_switch_id}) utilgængelig.","warning")
        return render_template('stroem_dashboard.html', translations=trans, error_message=error_message, current_value=current_value_disp, start_value=start_value_disp, total_usage=total_usage_disp, remaining=remaining_disp, meter_id=meter_id, unit_text=unit_text, percentage=percentage, package_size=package_size, power_switch_state=power_switch_state, power_switch_id=power_switch_id, updated=get_formatted_timestamp(time_format), is_meter_online=is_meter_online_flag)
    except Error as db_e_main: print(f"FATAL stroem_dash DB: {db_e_main}"); flash(trans['error_db_connection'],'error'); return redirect(url_for('select_meter'))
    except Exception as e_main: print(f"FATAL stroem_dash Gen: {str(e_main)}"); traceback.print_exc(); flash(f"{trans['error_reading_data']}: {str(e_main)}",'error'); return redirect(url_for('select_meter'))
    finally:
         if cursor: cursor.close()
         if conn: safe_close_connection(conn)
         print(f"===== END STRØM DASHBOARD finally =====")


@app.route('/select_meter', methods=['GET', 'POST'])
@login_required
def select_meter():
    lang=session.get('language','da'); trans=translations.get(lang,translations['da'])
    if request.method == 'POST':
        mid=request.form.get('meter_id')
        if not mid: flash(trans['error_no_meter'],'error'); return redirect(url_for('select_meter'))
        conn=None; cursor=None
        try:
            conn=get_db_connection()
            if not conn: flash('Database forbindelse fejlede.','error'); raise Exception("DB fail")
            cursor=conn.cursor(dictionary=True); cursor.execute("SELECT * FROM meter_config WHERE sensor_id=%s AND is_active=1",(mid,)); cfg=cursor.fetchone()
            if not cfg: flash(trans['error_invalid_meter'],'error'); raise Exception(f"No config {mid}")
            cursor.execute("SELECT booking_id FROM active_meters WHERE meter_id=%s AND booking_id!=%s",(mid,current_user.username))
            if cursor.fetchone(): flash(trans['meter_already_active'],'error'); session.pop('selected_meter',None); raise Exception("Meter taken")
            
            # Hent målerværdi fra Home Assistant - Detaljeret fejlsøgning
            sread=cfg.get('energy_sensor_id') or cfg['sensor_id']
            print(f"DEBUG SELECT_METER VIGTIG: Bruger={current_user.username}, Måler ID from form={mid}, Måler ID for læsning={sread}")
            
            # Ryd cache for alle relaterede målerværdier før vi henter
            cache.delete(f"meter_value_{sread}")
            cache.delete(f"meter_value_{normalize_meter_id(sread, True)}")
            cache.delete(f"meter_value_{normalize_meter_id(sread, False)}")
            
            # Hent målerværdi direkte (uden caching)
            print(f"DEBUG SELECT_METER DIREKTE KALD: Henter målerværdi for {sread} uden brug af cache")
            curr = None
            for meter_variant in [sread, normalize_meter_id(sread, True), normalize_meter_id(sread, False)]:
                if curr is not None:
                    break
                try:
                    print(f"DEBUG SELECT_METER: Prøver variant {meter_variant}")
                    r = requests.get(f"{HASS_URL}/api/states/{meter_variant}", 
                                    headers={"Authorization": f"Bearer {HASS_TOKEN}"},
                                    timeout=10)
                    if r.status_code == 200:
                        rj = r.json()
                        if "state" in rj and rj["state"] not in ["unavailable", "unknown", None]:
                            try:
                                curr_val = float(rj["state"])
                                print(f"DEBUG SELECT_METER SUCCESS: Variant {meter_variant} gav værdi {curr_val}")
                                curr = curr_val
                            except (ValueError, TypeError) as e:
                                print(f"DEBUG SELECT_METER ERROR: Kunne ikke konvertere værdi for {meter_variant}: {e}")
                        else:
                            print(f"DEBUG SELECT_METER ERROR: Ugyldig state for {meter_variant}: {rj.get('state')}")
                    else:
                        print(f"DEBUG SELECT_METER ERROR: HTTP {r.status_code} for {meter_variant}")
                except Exception as e:
                    print(f"DEBUG SELECT_METER ERROR: Exception for {meter_variant}: {e}")
            
            # Brug normal get_meter_value som fallback
            if curr is None:
                print(f"DEBUG SELECT_METER FALLBACK: Direkte kald fejlede, prøver normal get_meter_value")
                curr = get_meter_value(sread)
                
            print(f"DEBUG SELECT_METER ENDELIG VÆRDI: {curr}, type: {type(curr)}")
            
            if curr is None or not isinstance(curr,(int,float)): 
                flash(f"Måler '{cfg.get('display_name',mid)}' er offline eller returnerer en ugyldig værdi. Prøv igen senere eller kontakt administrator hvis problemet fortsætter.",'error')
                session.pop('selected_meter', None)  # Ryd session hvis værdien er ugyldig
                raise Exception("Invalid start value")
                
            # Gem måler information i sessionen
            print(f"DEBUG SELECT_METER SESSION GEM: Gemmer måler i session med startværdi: {curr}")
            session['selected_meter'] = {
                'meter_config_id': cfg['id'],
                'sensor_id': cfg['sensor_id'],
                'display_name': cfg.get('display_name', cfg['sensor_id']),
                'start_value': curr,
                'sensor_read_for_start': sread
            }
            flash(f"Måler '{cfg.get('display_name',mid)}' valgt med startværdi {curr}",'success')
            return redirect(url_for('select_package'))
        except Exception as e:
            print(f"ERR select_meter POST: {e}"); session.pop('selected_meter',None); return redirect(url_for('select_meter'))
        finally:
            if cursor: cursor.close()
            if conn: safe_close_connection(conn)
    # GET
    else:
        meters_disp=[];
        try:
            cfg_meters=get_configured_meters();
            if not cfg_meters: flash(trans['error_no_configured_meters'],'warning')
            else:
                active_ids=set(); conn=get_db_connection()
                if conn: cursor=conn.cursor(dictionary=True); cursor.execute('SELECT DISTINCT meter_id FROM active_meters WHERE meter_id IS NOT NULL'); active_ids={r['meter_id'] for r in cursor.fetchall()}
                meters=[]
                for m in cfg_meters:
                    if m['sensor_id'] not in active_ids:
                        # Tjek om måleren er online ved at hente dens værdi
                        sensor_id = m.get('energy_sensor_id') or m['sensor_id']
                        value = get_meter_value(sensor_id)
                        status = 'Online' if value is not None and isinstance(value, (int, float)) else 'Offline'
                        meters.append({
                            'id': m['sensor_id'],
                            'name': m.get('display_name') or f"M:{m['sensor_id']}",
                            'location': m.get('location', ''),
                            'state': status,
                            'unit': 'kWh',
                            'value': value
                        })
                meters_disp=meters
                if not meters and cfg_meters: flash("Alle tilgængelige målere er offline eller i brug.","info")
        except Error as dbeg: print(f"ERR select_meter GET DB: {dbeg}"); flash(trans['error_db_connection'],'error')
        except Exception as eg: print(f"ERR select_meter GET Gen: {eg}"); flash(f"{trans['error_general']}: {str(eg)}",'error')
        finally:
            if cursor: cursor.close()
            if conn: safe_close_connection(conn)
        return render_template('select_meter.html',meters=meters_disp,translations=trans)

@app.route('/toggle_power', methods=['POST'])
@login_required
def toggle_power():
    lang=session.get('language','da'); trans=translations.get(lang,translations['da']); action=request.form.get('action'); switch_id=request.form.get('switch_id'); conn=None; cursor=None; meter_display_name="Ukendt"; meter_id=None
    print(f"DEBUG toggle_power: Act={action}, SwID={switch_id}, User={current_user.username}")
    if not action or action not in ['on','off']: flash('Ugyldig handling.','error'); return redirect(url_for('stroem_dashboard'))
    if not switch_id: flash('Mangler switch ID.','error'); return redirect(url_for('stroem_dashboard'))
    if not HASS_URL or not HASS_TOKEN: flash('HA config mangler.','error'); return redirect(url_for('stroem_dashboard'))
    try:
        owns=False; conn=get_db_connection()
        if not conn: raise Error("DB fail access")
        cursor=conn.cursor(dictionary=True); cursor.execute("SELECT am.meter_id,mc.power_switch_id,mc.display_name FROM active_meters am JOIN meter_config mc ON am.meter_id = mc.sensor_id WHERE am.booking_id=%s",(current_user.username,)); cfgs=cursor.fetchall(); safe_close_connection(conn); conn=None; cursor=None
        found=False
        for cfg in cfgs:
            mid_temp=cfg.get('meter_id'); dname_temp=cfg.get('display_name') or f"M:{mid_temp}"
            if cfg.get('power_switch_id')==switch_id: found=True; meter_id=mid_temp; meter_display_name=dname_temp; break
            if mid_temp and mid_temp.startswith('sensor.'): base=mid_temp.split('.')[1].split('_')[0]; guessed=f"switch.{base}_0";
            if guessed==switch_id: found=True; meter_id=mid_temp; meter_display_name=dname_temp; break
        if not found: flash('Ikke adgang.','error'); return redirect(url_for('stroem_dashboard'))
        cstate=get_switch_state(switch_id); print(f"DEBUG toggle: Switch state {switch_id}: {cstate}")
        if cstate in ['unavailable','unknown']: flash(f"Kan ikke styre: Kontakt ({switch_id}) utilgængelig.","error"); return redirect(url_for('stroem_dashboard'))
        service="turn_on" if action=="on" else "turn_off"; api=f"{HASS_URL}/api/services/switch/{service}"; head={"Authorization":f"Bearer {HASS_TOKEN}","Content-Type":"application/json"}; pay={"entity_id":switch_id}
        resp=requests.post(api,headers=head,json=pay,timeout=10)
        if resp.status_code==200:
            atext='tændt' if action=='on' else 'slukket'; flash(f'Strømmen for måler "{meter_display_name}" er nu {atext}.','success')
            conn_log=get_db_connection() # Log
            if conn_log:
                lcur=conn_log.cursor(); uid=None
                try: uid=int(current_user.id)
                except: pass
                try:
                    # FJERN switch_id fra INSERT
                    lcur.execute("INSERT INTO power_events (user_id,event_type,meter_id,details,event_timestamp) VALUES (%s,%s,%s,%s,NOW())",(uid,f"manual_power_{action}",meter_id,f"Bruger {current_user.username} satte {atext}")) ; conn_log.commit()
                except Error as loge: print(f"ERR toggle log: {loge}")
                except Exception as logge: print(f"ERR toggle log Gen: {logge}")
                finally:
                    if lcur: lcur.close()
                    safe_close_connection(conn_log)
            else: print("ERR toggle log: DB fail.")
        else: flash(f'Fejl ({resp.status_code}) ved ændring.','error'); print(f"ERR toggle HA: {resp.status_code}-{resp.text}")
    except Error as dbe: print(f"ERR toggle DB: {dbe}"); flash('DB fejl.','error')
    except requests.exceptions.RequestException as reqe: print(f"ERR toggle HA: {reqe}"); flash(f'HA fejl: {reqe}','error')
    except Exception as e: print(f"ERR toggle Gen: {e}"); flash(f'Fejl: {str(e)}','error'); traceback.print_exc()
    finally:
        if cursor: cursor.close()
        if conn: safe_close_connection(conn)
    return redirect(url_for('stroem_dashboard'))

# --- API endpoints til admin dashboard for at hente målerdata ---
@app.route('/systemkontrolcenter23/get-meter', methods=['GET'])
@admin_required
def get_meter():
    booking_id = request.args.get('booking_id')
    if not booking_id:
        return jsonify({"success": False, "message": "Booking ID mangler"}), 400
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "message": "Databaseforbindelsesfejl"}), 500
        
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT am.meter_id, mc.display_name as name 
            FROM active_meters am 
            LEFT JOIN meter_config mc ON am.meter_id = mc.sensor_id
            WHERE am.booking_id = %s LIMIT 1
        """, (booking_id,))
        
        meter = cursor.fetchone()
        if meter:
            return jsonify({"success": True, "meter": meter})
        else:
            return jsonify({"success": False, "message": "Ingen måler fundet for denne booking"}), 404
            
    except Error as e:
        print(f"ERR get_meter DB: {e}")
        return jsonify({"success": False, "message": f"Databasefejl: {str(e)}"}), 500
    except Exception as e:
        print(f"ERR get_meter Gen: {e}")
        return jsonify({"success": False, "message": f"Fejl: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            safe_close_connection(conn)

@app.route('/systemkontrolcenter23/get-map', methods=['GET'])
@admin_required
def get_map():
    # Dette endpoint kunne returnere kortdata hvis det var relevant.
    # For nu returnerer vi bare en tom respons
    return jsonify({"success": True, "data": {}}), 200

@app.route('/systemkontrolcenter23/get-user-meters', methods=['GET'])
@admin_required
def get_user_meters():
    booking_id = request.args.get('booking_id')
    if not booking_id:
        return jsonify({"success": False, "message": "Booking ID mangler"}), 400
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "message": "Databaseforbindelsesfejl"}), 500
        
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT am.meter_id, mc.display_name as name, mc.location
            FROM active_meters am 
            LEFT JOIN meter_config mc ON am.meter_id = mc.sensor_id
            WHERE am.booking_id = %s
        """, (booking_id,))
        
        meters = cursor.fetchall()
        return jsonify({"success": True, "meters": meters})
            
    except Error as e:
        print(f"ERR get_user_meters DB: {e}")
        return jsonify({"success": False, "message": f"Databasefejl: {str(e)}"}), 500
    except Exception as e:
        print(f"ERR get_user_meters Gen: {e}")
        return jsonify({"success": False, "message": f"Fejl: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            safe_close_connection(conn)

@app.route('/systemkontrolcenter23/get-available-meters', methods=['GET'])
@admin_required
def get_available_meters():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "message": "Databaseforbindelsesfejl"}), 500
        
        cursor = conn.cursor(dictionary=True)
        # Henter konfigurerede målere som ikke allerede er i brug
        cursor.execute("""
            SELECT mc.sensor_id as meter_id, mc.display_name as name, mc.location
            FROM meter_config mc
            WHERE mc.is_active = 1
            AND mc.sensor_id NOT IN (
                SELECT meter_id FROM active_meters
            )
            ORDER BY mc.display_name
        """)
        
        available_meters = cursor.fetchall()
        return jsonify({"success": True, "meters": available_meters})
            
    except Error as e:
        print(f"ERR get_available_meters DB: {e}")
        return jsonify({"success": False, "message": f"Databasefejl: {str(e)}"}), 500
    except Exception as e:
        print(f"ERR get_available_meters Gen: {e}")
        return jsonify({"success": False, "message": f"Fejl: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            safe_close_connection(conn)

# --- Baggrundsjobs ---
def check_package_status():
    print(f"BG JOB: check_pkg Start - {datetime.now()}"); conn=None; cursor=None
    if not HASS_URL or not HASS_TOKEN: print("ERR check_pkg: No HASS cfg."); return
    try:
        conn=get_db_connection();
        if not conn: print("ERR check_pkg: DB fail."); return
        cursor=conn.cursor(dictionary=True); cursor.execute("""SELECT am.*,u.id as uid,mc.power_switch_id FROM active_meters am JOIN users u ON am.booking_id=u.username LEFT JOIN meter_config mc ON am.meter_id=mc.sensor_id WHERE am.meter_id IS NOT NULL AND am.package_size>0""")
        meters=cursor.fetchall();
        for m in meters:
             mid=m['meter_id']; bid=m['booking_id']; uid=m['uid']
             try:
                 curr=get_meter_value(mid);
                 if curr is None: print(f"WARN check_pkg: No value {mid}"); continue
                 start,pkg=float(m.get('start_value',0)),float(m.get('package_size',0)); usage=curr-start;
                 if usage<0: usage=curr # Reset
                 rem=pkg-usage;
                 if rem<=0.01: # Empty
                      print(f"INFO check_pkg: Pakke tom for {mid} ({bid}). Slukker.")
                      psid=m.get('power_switch_id');
                      if not psid and mid.startswith('sensor.'): base=mid.split('.')[1].split('_')[0]; psid=f"switch.{base}_0"
                      if not psid: print(f"WARN check_pkg: No switch ID {mid}"); continue
                      try: # Check state
                           sr=requests.get(f"{HASS_URL}/api/states/{psid}",headers={"Authorization":f"Bearer {HASS_TOKEN}"},timeout=5)
                           if sr.status_code==200 and sr.json().get('state')=='on':
                                pr=requests.post(f"{HASS_URL}/api/services/switch/turn_off",headers={"Authorization":f"Bearer {HASS_TOKEN}"},json={"entity_id":psid},timeout=10)
                                if pr.status_code==200:
                                     print(f"SUCCESS check_pkg: Off {psid}");
                                     try: # Log
                                         lcur = conn.cursor()
                                         # FJERN switch_id fra INSERT
                                         lcur.execute("""INSERT INTO power_events (user_id,event_type,meter_id,details,event_timestamp) VALUES (%s,'auto_power_off_empty',%s,%s,NOW())""", (uid,mid,f"Pakke tom. Brug:{usage:.3f}, Pkg:{pkg:.3f}")); lcur.close()
                                     except Error as loge: print(f"WARN check_pkg log DB: {loge}"); conn.rollback()
                                     except Exception as logge: print(f"WARN check_pkg log Gen: {logge}"); conn.rollback()
                                else: print(f"ERR check_pkg: Off fail {psid} ({pr.status_code})")
                           # elif sr.status_code!=200: print(f"WARN check_pkg: Get state fail {psid} ({sr.status_code})")
                      except Exception as swe: print(f"ERR check_pkg switch {psid}: {swe}")
             except Exception as me: print(f"ERR check_pkg meter {mid}: {me}")
    except Error as dbe: print(f"FATAL check_pkg DB: {dbe}")
    except Exception as e: print(f"FATAL check_pkg Gen: {e}"); traceback.print_exc()
    finally:
        if 'lcur' in locals() and lcur: lcur.close()
        if cursor: cursor.close()
        if conn: safe_close_connection(conn)

def check_and_remove_inactive_users():
    print(f"BG JOB: inactive Start - {datetime.now()}"); conn=None; cursor=None
    if not HASS_URL or not HASS_TOKEN: print("ERR inactive: No HASS cfg."); return
    try:
        conn=get_db_connection();
        if not conn: print("ERR inactive: DB fail."); return
        cursor=conn.cursor(dictionary=True); cursor.execute("""SELECT u.id as uid,u.username as bid,am.id as amid,am.meter_id,mc.power_switch_id FROM users u JOIN active_meters am ON u.username=am.booking_id LEFT JOIN aktive_bookinger ab ON u.username=ab.booking_id LEFT JOIN meter_config mc ON am.meter_id=mc.sensor_id WHERE ab.booking_id IS NULL AND u.username!=%s""",(ADMIN_USERNAME,))
        users=cursor.fetchall();
        if not users: return
        for u in users:
             uid=u['uid']; bid=u['bid']; mid=u['meter_id'];
             try: # Turn off... Log... Delete... Commit...
                 psid=u.get('power_switch_id');
                 if not psid and mid and mid.startswith('sensor.'): base=mid.split('.')[1].split('_')[0]; psid=f"switch.{base}_0"
                 if psid:
                    try: requests.post(f"{HASS_URL}/api/services/switch/turn_off", headers={"Authorization":f"Bearer {HASS_TOKEN}"}, json={"entity_id":psid}, timeout=10)
                    except Exception as swe: print(f"WARN inactive switch {psid}: {swe}")
                 try: # Log (med korrekte parametre)
                     log_cursor=conn.cursor()
                     # FJERN switch_id fra INSERT
                     log_cursor.execute("""INSERT INTO power_events (user_id,event_type,meter_id,details,event_timestamp) VALUES (%s,'auto_release_inactive',%s,%s,NOW())""", (uid,mid,f"Bruger {bid} ej aktiv. Måler frigivet.")); log_cursor.close()
                 except Error as loge: print(f"WARN inactive log: {loge}")
                 cd=conn.cursor(); cd.execute("DELETE FROM active_meters WHERE id=%s",(u['amid'],)); deleted=cd.rowcount; cd.close()
                 if deleted>0: conn.commit(); print(f"SUCCESS inactive: Removed {mid} for {bid}")
                 else: conn.rollback(); print(f"WARN inactive: Delete fail {u['amid']}")
             except Exception as ue: print(f"ERROR inactive user {bid}: {ue}"); conn.rollback()
    except Error as dbe: print(f"FATAL inactive DB: {dbe}")
    except Exception as e: print(f"FATAL inactive Gen: {e}"); traceback.print_exc()
    finally:
        if 'cd' in locals() and cd: cd.close()
        if 'log_cursor' in locals() and log_cursor: log_cursor.close()
        if cursor: cursor.close()
        if conn: safe_close_connection(conn)

# Start scheduler
scheduler = None
if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    print("Attempting scheduler start...")
    try:
        scheduler = BackgroundScheduler(daemon=True); scheduler.add_job(func=check_package_status, trigger="interval", minutes=5, id='check_pkg_job', replace_existing=True); scheduler.add_job(func=check_and_remove_inactive_users, trigger="interval", hours=1, id='inactive_user_job', replace_existing=True); scheduler.start(); print("Scheduler started.")
        import atexit; atexit.register(lambda: scheduler.shutdown() if scheduler and scheduler.running else None)
    except Exception as se: print(f"ERROR Scheduler start: {se}")
else: print("Scheduler not started (debug/reload).")

@app.route('/select_package', methods=['GET', 'POST'])
@login_required
def select_package():
    lang=session.get('language','da'); trans=translations.get(lang,translations['da']); sel=session.get('selected_meter')
    conn=None; cursor=None
    print(f"\n===== START SELECT_PACKAGE (Bruger: {current_user.username}) =====")
    print(f"DEBUG SELECT_PACKAGE SESSION DATA: {sel}")
    
    # Robust tjek om alle nødvendige nøgler findes i session
    if not sel or 'sensor_id' not in sel or 'start_value' not in sel or 'meter_config_id' not in sel:
        print(f"DEBUG SELECT_PACKAGE ERROR: Manglende eller ukomplet måler i session. Session indhold: {sel}")
        flash('Der mangler vigtig information om måleren. Vælg venligst måleren igen.', 'error')
        session.pop('selected_meter', None)  # Ryd session hvis data er ukomplet
        return redirect(url_for('select_meter'))
    
    # Hvis der ikke er en valgt måler i sessionen, men brugeren har en aktiv måler i databasen,
    # så hentes måler informationen fra databasen og gemmes i sessionen
    if not sel:
        try:
            conn=get_db_connection()
            if conn:
                cursor=conn.cursor(dictionary=True)
                cursor.execute('SELECT meter_id, start_value, package_size FROM active_meters WHERE booking_id=%s',(current_user.username,))
                active_meter=cursor.fetchone()
                if active_meter:
                    # Hent målerens displaynavn
                    cursor.execute('SELECT display_name FROM meter_config WHERE sensor_id=%s',(active_meter['meter_id'],))
                    display_info = cursor.fetchone()
                    display_name = display_info['display_name'] if display_info else active_meter['meter_id']
                    
                    # Gem måler informationen i sessionen
                    sel = {
                        'meter_config_id': active_meter['meter_config_id'],
                        'sensor_id': active_meter['meter_id'],
                        'start_value': active_meter['start_value'],
                        'display_name': display_name
                    }
                    session['selected_meter'] = sel
                    print(f"DEBUG: Fundet aktiv måler for {current_user.username} og gemt i session: {sel}")
                else:
                    flash('Ingen aktiv måler fundet.','warning')
                    return redirect(url_for('select_meter'))
        except Error as dbe:
            print(f"ERR select_pkg initDB: {dbe}")
            flash(f"DB Fejl: {dbe}",'error')
        except Exception as e:
            print(f"ERR select_pkg init: {e}")
            flash(f"Fejl: {str(e)}",'error')
        finally:
            if cursor: cursor.close()
            if conn: safe_close_connection(conn)
    
    # Resten af den oprindelige kode
    if not sel: 
        flash('Ingen måler valgt.','warning')
        return redirect(url_for('select_meter'))
    conn=None; cursor=None
    if request.method=='POST':
        pid=request.form.get('package_id')
        if not pid: flash('Vælg pakke.','error'); return redirect(url_for('select_package'))
        try:
            conn=get_db_connection();
            if not conn: raise Error("DB fail")
            cursor=conn.cursor(dictionary=True); cursor.execute('SELECT * FROM stroem_pakker WHERE id=%s AND aktiv=1',(pid,)); pkg=cursor.fetchone()
            if not pkg: flash('Ugyldig pakke.','error'); raise Exception("Invalid package")
            psize=float(pkg['enheder']); pname=pkg['navn']; cfg_id=sel['meter_config_id']; sid=sel['sensor_id']; start=sel['start_value']
            
            print(f"DEBUG SELECT_PACKAGE KØB: Pakke ID={pid}, Størrelse={psize}, Måler ID={sid}, Startværdi={start}")
            
            # Double-tjek startværdien ved at hente den direkte igen for at se, om der er forskel
            sensor_read = sel.get('sensor_read_for_start') or sid
            print(f"DEBUG SELECT_PACKAGE VERIFIKATION: Henter målerværdi igen for {sensor_read} for at sammenligne")
            
            # Ryd cache for sikkerhedens skyld
            cache.delete(f"meter_value_{sensor_read}")
            cache.delete(f"meter_value_{normalize_meter_id(sensor_read, True)}")
            cache.delete(f"meter_value_{normalize_meter_id(sensor_read, False)}")
            
            current_value = get_meter_value(sensor_read)
            print(f"DEBUG SELECT_PACKAGE VERIFIKATION: Original startværdi={start}, Nuværende værdi={current_value}")
            
            if current_value is not None and abs(float(start) - float(current_value)) > 0.5:
                print(f"DEBUG SELECT_PACKAGE ADVARSEL: Stor forskel mellem startværdi ({start}) og nuværende værdi ({current_value})!")
            
            cursor.execute("SELECT booking_id FROM active_meters WHERE meter_id=%s AND booking_id!=%s",(sid,current_user.username))
            if cursor.fetchone(): flash(trans['meter_already_active'],'error'); session.pop('selected_meter',None); raise Exception("Meter taken")
            mod_cursor = conn.cursor(); mod_cursor.execute("SELECT id, package_size FROM active_meters WHERE booking_id=%s",(current_user.username,)); existing=mod_cursor.fetchone()
            
            if existing: 
                # Ved køb af tillægspakke: Læg den nye pakkes enheder oven i de eksisterende
                current_package_size = float(existing[1])
                new_package_size = current_package_size + psize
                mod_cursor.execute("UPDATE active_meters SET meter_id=%s,start_value=%s,package_size=%s WHERE id=%s",(sid,start,new_package_size,existing[0]))
                print(f"DEBUG SELECT_PACKAGE UPDATE: Opdaterer eksisterende måler. ID={existing[0]}, Måler={sid}, Start={start}, Ny pakke={new_package_size}")
            else: 
                mod_cursor.execute("INSERT INTO active_meters (booking_id, meter_id, start_value, package_size, created_at) VALUES (%s, %s, %s, %s, NOW())",(current_user.username,sid,start,psize))
                print(f"DEBUG SELECT_PACKAGE INSERT: Indsætter ny måler. Bruger={current_user.username}, Måler={sid}, Start={start}, Pakke={psize}")
            rows_affected = mod_cursor.rowcount; mod_cursor.close()
            if rows_affected > 0:
                 try: # Log (standard cursor)
                     log_cursor=conn.cursor()
                     # FJERN koebs_tidspunkt
                     log_cursor.execute('INSERT INTO stroem_koeb (booking_id,pakke_id,maaler_id,enheder_tilbage) VALUES (%s,%s,%s,%s)',(current_user.username,pid,cfg_id,psize))
                     log_cursor.close()
                 except Error as loge: print(f"WARN select_pkg log: {loge}") # Fortsæt selvom log fejler
                 except Exception as logge: print(f"WARN select_pkg log Gen: {logge}")
                 conn.commit(); session.pop('selected_meter',None); flash(f'Måler {sid} ({sel["display_name"]}) og pakke "{pname}" aktiveret!','success')
                 if cursor: cursor.close(); cursor=None
                 if conn: safe_close_connection(conn); conn=None
                 return redirect(url_for('stroem_dashboard'))
            else: conn.rollback(); flash("Fejl: Kunne ikke opdatere målerinfo.", "danger")
        except Error as dbe: print(f"ERR select_pkg POST DB: {dbe}"); flash(f"DB Fejl: {dbe}",'error'); conn.rollback()
        except Exception as e: print(f"ERR select_pkg POST Gen: {e}"); flash(f"Fejl: {str(e)}",'error'); conn.rollback()
        finally:
            if 'mod_cursor' in locals() and mod_cursor: mod_cursor.close()
            if 'log_cursor' in locals() and log_cursor: log_cursor.close()
            if cursor: cursor.close()
            if conn: safe_close_connection(conn)
        return redirect(url_for('select_package'))
    # GET
    else:
        pkgs=[]; gtype='Ukendt'
        try:
            conn=get_db_connection()
            if conn:
                 cursor=conn.cursor(dictionary=True); cursor.execute('SELECT plads_type FROM aktive_bookinger WHERE booking_id=%s',(current_user.username,)); b=cursor.fetchone(); gtype=b['plads_type'].upper() if b and b.get('plads_type') else 'KØRENDE'
                 ptype='SAESON' if gtype=='SÆSON' else 'DAGS'; cursor.execute("SELECT * FROM stroem_pakker WHERE type=%s AND aktiv=1 ORDER BY enheder,dage,pris",(ptype,)); pkgs=cursor.fetchall()
            else: flash(trans['error_db_connection'],'error')
        except Error as dbe: print(f"ERR select_pkg GET DB: {dbe}"); flash(f"DB Fejl: {dbe}",'error')
        except Exception as e: print(f"ERR select_pkg GET Gen: {e}"); flash(f"Fejl: {str(e)}",'error')
        finally:
            if cursor: cursor.close()
            if conn: safe_close_connection(conn)
        return render_template('select_package.html',packages=pkgs, selected_meter=sel, translations=trans, guest_type=gtype)

@app.route('/admin_connect_meter', methods=['POST'])
@admin_required
def admin_connect_meter():
    """Funktion til at forbinde en måler til en booking."""
    # Hent formulardata
    booking_id = request.form.get('connect_booking_id')
    meter_id = request.form.get('connect_meter_id')
    package_size = request.form.get('connect_package_size')
    
    # Validér input
    if not booking_id or not meter_id or not package_size:
        flash('Alle felter skal udfyldes.', 'error')
        return redirect(url_for('admin_login_or_dashboard'))
    
    # Validér at package_size er et tal
    try:
        package_size = float(package_size)
    except ValueError:
        flash('Antal enheder skal være et tal.', 'error')
        return redirect(url_for('admin_login_or_dashboard'))
    
    # Initialiser database-variabler
    conn = None
    cursor = None
    
    try:
        # Opret forbindelse til databasen
        conn = get_db_connection()
        if not conn:
            flash('Kunne ikke oprette forbindelse til databasen.', 'error')
            return redirect(url_for('admin_login_or_dashboard'))
        
        # Tjek om måleren er ledig
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM active_meters WHERE meter_id = %s", (meter_id,))
        if cursor.fetchone():
            flash('Denne måler er allerede i brug.', 'error')
            return redirect(url_for('admin_login_or_dashboard'))
        
        # Tjek om brugeren findes
        cursor.execute("SELECT * FROM aktive_bookinger WHERE booking_id = %s", (booking_id,))
        if not cursor.fetchone():
            flash('Booking ID findes ikke.', 'error')
            return redirect(url_for('admin_login_or_dashboard'))
        
        # Find meter_config_id baseret på sensor_id
        cursor.execute("SELECT id FROM meter_config WHERE sensor_id=%s", (meter_id,))
        meter_config_result = cursor.fetchone()
        meter_config_id = meter_config_result[0] if meter_config_result else 0
        
        # Hent den aktuelle målerværdi
        current_value = get_meter_value(meter_id) or 0
        
        # Indsæt måleren i active_meters tabellen
        cursor.execute(
            "INSERT INTO active_meters (booking_id, meter_id, start_value, package_size, created_at) VALUES (%s, %s, %s, %s, NOW())", 
            (booking_id, meter_id, current_value, package_size)
        )
        
        # Log handlingen i stroem_koeb tabellen
        log_note = f"Admin tilknyttede måler: {current_user.username}"
        cursor.execute(
            "INSERT INTO stroem_koeb (booking_id, pakke_id, maaler_id, enheder_tilbage) VALUES (%s, %s, %s, %s)",
            (booking_id, 1, meter_config_id, package_size)
        )
        
        # Aktivér målerens kontakt, hvis den har en
        try:
            cursor.execute("SELECT power_switch_id FROM meter_config WHERE sensor_id=%s", (meter_id,))
            cfg = cursor.fetchone()
            if cfg and cfg[0]:  # Hvis måler har en kontakt konfigureret
                psid = cfg[0]
                if HASS_URL and HASS_TOKEN:
                    requests.post(
                        f"{HASS_URL}/api/services/switch/turn_on",
                        headers={"Authorization": f"Bearer {HASS_TOKEN}"},
                        json={"entity_id": psid},
                        timeout=10
                    )
        except Exception as swe:
            print(f"WARN connect switch: {swe}")
        
        # Commit transaktionen
        conn.commit()
        flash(f'Måler {meter_id} er nu tilknyttet booking {booking_id} med {package_size} enheder.', 'success')
        
    except Error as dbe:
        # Håndter database-fejl
        print(f"ERR connect_meter DB: {dbe}")
        flash(f'Database fejl: {dbe}', 'error')
        if conn:
            conn.rollback()
    except Exception as e:
        # Håndter generelle fejl
        print(f"ERR connect_meter Gen: {e}")
        flash(f'Fejl: {str(e)}', 'error')
        if conn:
            conn.rollback()
    finally:
        # Oprydning
        if cursor:
            cursor.close()
        if conn:
            safe_close_connection(conn)
    
    # Omdiriger til admin dashboard
    return redirect(url_for('admin_login_or_dashboard'))

# Original Flask redirect funktion
from flask import redirect as flask_redirect

# Override redirect for at tilføje logging
def redirect(location, **kwargs):
    print(f"REDIRECT LOG: Omdirigerer til {location}")
    return flask_redirect(location, **kwargs)

# Erstat Flask's redirect i modulet
import flask
flask.redirect = redirect

# --- App Execution ---
if __name__ == '__main__':
    print("Starter Flask app...")
    app.run(host='0.0.0.0', port=5000, debug=True)