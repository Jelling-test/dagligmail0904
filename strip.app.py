```python
# -*- coding: utf-8 -*-
import os
import requests
from datetime import datetime, timedelta
from functools import wraps
import time
import traceback
import stripe # NYT
from decimal import Decimal # Kan være nyttigt til priser

import mysql.connector
from mysql.connector import Error, pooling
from mysql.connector.cursor import MySQLCursorDict

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, abort
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_caching import Cache
from apscheduler.schedulers.background import BackgroundScheduler
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from flask_mail import Mail, Message # NYT

load_dotenv()

app = Flask(__name__) # Rettet fra name til __name__
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
    except Exception as ex: print(f"FATAL: Uventet DB Pool Init Fejl: {ex}"); db_pool = None # Rettet variabelnavn

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

# --- Flask-Mail Konfiguration ---
# Henter primært fra .env, men kan overskrives af DB-indstillinger via get_system_settings() senere
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', 'false').lower() == 'true'
# MAIL_DEFAULT_SENDER vil typisk blive sat fra DB-settings
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('RECEIPT_SENDER_EMAIL', 'noreply@example.com')
mail = Mail(app)


# --- Stripe Konfiguration ---
# Funktion til at hente Stripe nøgler (DB first, .env fallback)
def get_stripe_keys():
    settings = get_system_settings() # Antager denne funktion henter DB settings
    mode = settings.get('stripe_mode', os.getenv('STRIPE_MODE', 'test'))
    if mode == 'live':
        pub_key = settings.get('stripe_publishable_key_live', os.getenv('STRIPE_PUBLISHABLE_KEY_LIVE'))
        sec_key = settings.get('stripe_secret_key_live', os.getenv('STRIPE_SECRET_KEY_LIVE'))
        hook_secret = settings.get('stripe_webhook_secret_live', os.getenv('STRIPE_WEBHOOK_SECRET_LIVE'))
    else: # Default to test
        pub_key = settings.get('stripe_publishable_key_test', os.getenv('STRIPE_PUBLISHABLE_KEY_TEST'))
        sec_key = settings.get('stripe_secret_key_test', os.getenv('STRIPE_SECRET_KEY_TEST'))
        hook_secret = settings.get('stripe_webhook_secret_test', os.getenv('STRIPE_WEBHOOK_SECRET_TEST'))
    return pub_key, sec_key, hook_secret, mode

# Sæt Stripe API nøgle ved opstart
_, stripe_secret_key, stripe_webhook_secret, stripe_mode = get_stripe_keys()
if stripe_secret_key:
    stripe.api_key = stripe_secret_key
    print(f"Stripe initialiseret i {stripe_mode} mode.")
else:
    print("ADVARSEL: Stripe Secret Key mangler! Betaling vil ikke fungere.")

# Funktion til at opdatere Flask-Mail config fra DB settings
def update_mail_config():
    settings = get_system_settings()
    app.config['MAIL_SERVER'] = settings.get('smtp_host', os.getenv('MAIL_SERVER'))
    app.config['MAIL_PORT'] = int(settings.get('smtp_port', os.getenv('MAIL_PORT', 587)))
    app.config['MAIL_USERNAME'] = settings.get('smtp_user', os.getenv('MAIL_USERNAME'))
    app.config['MAIL_PASSWORD'] = settings.get('smtp_password', os.getenv('MAIL_PASSWORD'))
    app.config['MAIL_USE_TLS'] = str(settings.get('smtp_use_tls', os.getenv('MAIL_USE_TLS', 'true'))).lower() == 'true'
    app.config['MAIL_USE_SSL'] = str(settings.get('smtp_use_ssl', os.getenv('MAIL_USE_SSL', 'false'))).lower() == 'true'
    app.config['MAIL_DEFAULT_SENDER'] = settings.get('receipt_sender_email', os.getenv('RECEIPT_SENDER_EMAIL', 'noreply@example.com'))
    global mail
    mail = Mail(app) # Reinitialiser med nye settings
    print("Flask-Mail konfiguration opdateret fra system settings.")

# Kald ved opstart
update_mail_config()

# --- GLOBALT DEFINERET HJÆLPEFUNKTION ---
def format_number(num):
    # ... (uændret)
    try:
        if num is None or isinstance(num, str) and num.lower() in ['n/a', 'ukendt', 'fejl', 'offline', 'unavailable']: return str(num)
        # Use Decimal for potentially better precision if needed, but float is likely fine here
        # return "{:,.3f}".format(Decimal(num)).replace(",", "X").replace(".", ",").replace("X", ".")
        return "{:,.3f}".format(float(num)).replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError): return str(num)

# --- Andre Hjælpefunktioner ---
# ... (get_power_meters, normalize_meter_id, get_meter_value, get_switch_state uændret) ...
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
    # ... (uændret, med debug prints) ...
    if not meter_id_original or not HASS_URL or not HASS_TOKEN: return None
    id1 = normalize_meter_id(meter_id_original, False)
    id2 = normalize_meter_id(meter_id_original, True)
    for meter_id in [id2, id1]:
        try:
            # print(f"DEBUG: Forsøger at hente værdi for {meter_id}") # Fjernet for mindre støj
            r = requests.get(f"{HASS_URL}/api/states/{meter_id}",
                            headers={"Authorization": f"Bearer {HASS_TOKEN}"},
                            timeout=10)
            if r.status_code == 200:
                rj = r.json()
                if "state" in rj and rj["state"] not in ["unavailable", "unknown", None]:
                    try:
                        val = float(rj["state"])
                        # print(f"SUCCESS get: Val={val} for {meter_id}") # Fjernet for mindre støj
                        return val
                    except (ValueError, TypeError):
                        print(f"WARN get: Ugyldig værdi '{rj['state']}' for {meter_id}")
                # else: print(f"WARN get: Ugyldig state for {meter_id}") # Fjernet for mindre støj
            # else: print(f"WARN get: HTTP {r.status_code} for {meter_id}") # Fjernet for mindre støj
        except Exception as e:
            print(f"WARN get: Exception for {meter_id}: {e}")
    return None

def get_switch_state(switch_id):
    # ... (uændret) ...
    if not switch_id or not HASS_URL or not HASS_TOKEN: return "unknown"
    try:
        url = f"{HASS_URL}/api/states/{switch_id}"; headers = {"Authorization": f"Bearer {HASS_TOKEN}"}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200: return response.json().get('state', 'unknown')
        else: print(f"WARN get_switch_state: Fik status {response.status_code} for {switch_id}"); return "unknown"
    except requests.exceptions.RequestException as e: print(f"ERR get_switch_state ({switch_id}): {e}"); return "unknown"
    except Exception as e: print(f"ERR get_switch_state gen ({switch_id}): {e}"); return "unknown"


def get_formatted_timestamp(format_str=None):
    # ... (uændret) ...
    if not format_str:
        try:
            # Brug cache for format
            format_str = cache.get('timestamp_format')
            if not format_str:
                 # Hent fra DB hvis ikke cachet
                 settings = get_system_settings()
                 format_str = settings.get('timestamp_format', '%Y-%m-%d %H:%M:%S')
                 cache.set('timestamp_format', format_str, timeout=3600)
        except Exception as e:
            print(f"WARN timestamp format fetch: {e}")
            format_str = '%Y-%m-%d %H:%M:%S' # Fallback

    # Anvend format
    try:
        return datetime.now().strftime(format_str or '%Y-%m-%d %H:%M:%S')
    except ValueError:
        print(f"WARN: Ugyldigt timestamp format '{format_str}'. Bruger fallback.")
        # Gem fallback format så vi ikke fejler igen med det samme
        cache.set('timestamp_format', '%Y-%m-%d %H:%M:%S', timeout=3600)
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def get_configured_meters():
    # ... (uændret) ...
    meters = []; conn = None; cursor = None
    try:
        conn = get_db_connection()
        if not conn: print("ERR get_cfg_meters: No DB conn."); return []
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM meter_config WHERE is_active=1 ORDER BY display_name')
        meters = cursor.fetchall()
    except Error as e: print(f"ERR get_cfg_meters (DB): {e}"); meters=[]
    except Exception as e: print(f"ERR get_cfg_meters (Gen): {e}"); meters=[]
    finally:
        if cursor: cursor.close()
        if conn: safe_close_connection(conn)
    return meters

# --- System Indstillinger Funktioner ---
# Brug cache for alle systemindstillinger
@cache.memoize(timeout=600) # Cache resultatet af hele funktionen
def get_system_settings():
    print("DEBUG: Henter systemindstillinger (DB eller .env fallback).")
    settings_from_db = {}
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT setting_key, value FROM system_settings")
            settings_from_db = {r['setting_key']: r['value'] for r in cursor.fetchall()}
            print(f"DEBUG: Fundet {len(settings_from_db)} indstillinger i DB.")
        else:
            print("ERROR get_system_settings: No DB conn.")
    except Error as db_e:
        print(f"FEJL hent sys settings DB: {db_e}")
    finally:
        if cursor: cursor.close()
        if conn: safe_close_connection(conn)

    # Fallback til .env for specifikke nøgler hvis ikke i DB
    # Tilføj alle nye nøgler her for fallback
    env_fallbacks = {
        'hass_url': os.getenv('HASS_URL'),
        'hass_token': os.getenv('HASS_TOKEN'),
        'unit_text': os.getenv('UNIT_TEXT', 'kWh'),
        'timestamp_format': os.getenv('TIMESTAMP_FORMAT', '%Y-%m-%d %H:%M:%S'),
        'stripe_publishable_key_test': os.getenv('STRIPE_PUBLISHABLE_KEY_TEST'),
        'stripe_secret_key_test': os.getenv('STRIPE_SECRET_KEY_TEST'),
        'stripe_webhook_secret_test': os.getenv('STRIPE_WEBHOOK_SECRET_TEST'),
        'stripe_publishable_key_live': os.getenv('STRIPE_PUBLISHABLE_KEY_LIVE'),
        'stripe_secret_key_live': os.getenv('STRIPE_SECRET_KEY_LIVE'),
        'stripe_webhook_secret_live': os.getenv('STRIPE_WEBHOOK_SECRET_LIVE'),
        'stripe_mode': os.getenv('STRIPE_MODE', 'test'),
        'admin_report_email': os.getenv('ADMIN_REPORT_EMAIL'),
        'receipt_sender_email': os.getenv('RECEIPT_SENDER_EMAIL'),
        'smtp_host': os.getenv('MAIL_SERVER'),
        'smtp_port': os.getenv('MAIL_PORT', 587),
        'smtp_user': os.getenv('MAIL_USERNAME'),
        'smtp_password': os.getenv('MAIL_PASSWORD'),
        'smtp_use_tls': os.getenv('MAIL_USE_TLS', 'true'),
        'smtp_use_ssl': os.getenv('MAIL_USE_SSL', 'false'),
    }

    final_settings = {}
    for key, env_value in env_fallbacks.items():
        # Prioriter DB-værdi, men brug .env hvis DB-værdi er None eller tom streng
        db_value = settings_from_db.get(key)
        final_settings[key] = db_value if db_value else env_value

    # Tilføj resterende DB-indstillinger som ikke har env fallback
    for key, db_value in settings_from_db.items():
        if key not in final_settings:
            final_settings[key] = db_value

    return final_settings

def update_system_setting(key, value):
    conn = None; cursor = None; success = False
    try:
        conn = get_db_connection()
        if conn:
             cursor = conn.cursor()
             # Brug INSERT ... ON DUPLICATE KEY UPDATE for at indsætte eller opdatere
             cursor.execute("""
                 INSERT INTO system_settings (setting_key, value)
                 VALUES (%s, %s)
                 ON DUPLICATE KEY UPDATE value = VALUES(value)
             """, (key, value))
             conn.commit(); success = True
             # Ryd relevante caches efter opdatering
             cache.delete_memoized(get_system_settings) # Ryd den overordnede settings cache
             if key == 'timestamp_format': cache.delete('timestamp_format')
             if key == 'unit_text': cache.delete('system_settings_display') # Evt. fjern denne specifikke cache
             # Ryd Stripe/Mail config hvis relevante nøgler ændres
             if key.startswith('stripe_') or key.startswith('smtp_') or key in ['admin_report_email', 'receipt_sender_email']:
                 # Genindlæs konfigurationen
                 global stripe_secret_key, stripe_webhook_secret, stripe_mode
                 _, stripe_secret_key, stripe_webhook_secret, stripe_mode = get_stripe_keys()
                 if stripe_secret_key:
                     stripe.api_key = stripe_secret_key
                     print(f"Stripe API nøgle opdateret til {stripe_mode} mode.")
                 else:
                     print("ADVARSEL: Stripe Secret Key fjernet/mangler efter opdatering!")
                 update_mail_config() # Opdater mail konfig

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
    # ... (uændret - tilføj evt. Stripe/betalingsrelaterede tekster)
     'da': {
        # ... eksisterende ...
        'confirm_purchase': 'Bekræft Køb',
        'package_details': 'Pakkedetaljer',
        'price': 'Pris',
        'pay_with_stripe': 'Betal med Kort',
        'payment_processing': 'Behandler betaling...',
        'payment_successful': 'Betaling gennemført!',
        'payment_failed': 'Betaling mislykkedes',
        'payment_canceled': 'Betaling annulleret',
        'receipt_sent': 'En kvittering er sendt til din e-mail.',
        'error_creating_payment': 'Fejl ved oprettelse af betalings-session.',
        'error_verifying_payment': 'Fejl ved verificering af betaling.',
        'error_activating_package': 'Fejl ved aktivering af pakke efter betaling.',
        'purchase_already_processed': 'Dette køb er allerede behandlet.',
        # Admin
        'stripe_settings': 'Stripe Indstillinger',
        'stripe_mode': 'Stripe Tilstand',
        'test_mode': 'Test',
        'live_mode': 'Live',
        'publishable_key': 'Publishable Key',
        'secret_key': 'Secret Key',
        'webhook_secret': 'Webhook Signing Secret',
        'email_settings': 'E-mail Indstillinger',
        'admin_report_email': 'Admin Rapport E-mail',
        'receipt_sender_email': 'Kvittering Afsender E-mail',
        'smtp_settings': 'SMTP Indstillinger',
        'smtp_host': 'SMTP Vært',
        'smtp_port': 'SMTP Port',
        'smtp_user': 'SMTP Brugernavn',
        'smtp_password': 'SMTP Adgangskode',
        'smtp_use_tls': 'Brug TLS',
        'smtp_use_ssl': 'Brug SSL',
     },
     'en': {
        # ... other languages ...
     },
     'de': {
         # ... other languages ...
     }
}

# User class
class User(UserMixin):
    # ... (init uændret) ...
    def __init__(self, id, username, fornavn=None, efternavn=None, email=None, is_admin=False): self.id=str(id); self.username=username; self.fornavn=fornavn; self.efternavn=efternavn; self.email=email; self.is_admin=is_admin

# --- Decorator ---
# ... (admin_required uændret) ...
def admin_required(f):
    @wraps(f)
    def decorated_function(*args,**kwargs):
        if not current_user.is_authenticated or not getattr(current_user,'is_admin',False): flash('Admin adgang påkrævet','error'); return redirect(url_for('admin_login_or_dashboard',next=request.url))
        return f(*args,**kwargs)
    return decorated_function

# --- load_user ---
# ... (uændret) ...
@login_manager.user_loader
def load_user(user_id):
    if user_id=="999999": return User(id="999999",username=ADMIN_USERNAME,is_admin=True)
    conn=None; cursor=None; user_obj=None
    try:
        conn=get_db_connection()
        if conn:
            cursor=conn.cursor(dictionary=True)
            cursor.execute('SELECT * FROM users WHERE id=%s',(user_id,))
            data=cursor.fetchone()
            if data:
                # Sørg for at hente email her, så current_user.email virker
                user_obj=User(id=data['id'],
                              username=data.get('username'),
                              fornavn=data.get('fornavn'),
                              efternavn=data.get('efternavn'),
                              email=data.get('email'), # VIGTIGT!
                              is_admin=False)
    except Error as e: print(f"Err load_user DB: {e}")
    except Exception as e: print(f"Err load_user Gen: {e}")
    finally:
        if cursor: cursor.close()
        if conn: safe_close_connection(conn)
    return user_obj


# --- ADMIN ROUTES ---

@app.route('/systemkontrolcenter23/settings', methods=['GET', 'POST'])
@admin_required
def system_admin_settings():
    if request.method == 'POST':
        settings_to_update = [
            'hass_url', 'hass_token', 'unit_text', 'timestamp_format',
            # Stripe settings
            'stripe_mode',
            'stripe_publishable_key_test', 'stripe_secret_key_test', 'stripe_webhook_secret_test',
            'stripe_publishable_key_live', 'stripe_secret_key_live', 'stripe_webhook_secret_live',
            # Email settings
            'admin_report_email', 'receipt_sender_email',
            'smtp_host', 'smtp_port', 'smtp_user', 'smtp_password',
            'smtp_use_tls', 'smtp_use_ssl'
        ]
        updated_count = 0
        error_occured = False

        for key in settings_to_update:
            if key in request.form:
                value = request.form[key].strip()
                # Særlig håndtering for checkbox (TLS/SSL)
                if key in ['smtp_use_tls', 'smtp_use_ssl']:
                    value = 'true' if request.form.get(key) else 'false'
                # Særlig håndtering for timestamp format validering
                if key == 'timestamp_format':
                    try:
                        datetime.now().strftime(value or '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        flash(f"Ugyldigt timestamp format: '{value}'. Bruger standard.", 'warning')
                        value = '%Y-%m-%d %H:%M:%S' # Reset til default ved fejl

                # Undlad at gemme tomme strenge for sensitive felter hvis de ikke var udfyldt?
                # Eller stol på at admin ved hvad de gør. For nu: Gemmer vi hvad der sendes.
                if update_system_setting(key, value):
                    updated_count += 1
                else:
                    error_occured = True
                    flash(f"Fejl ved opdatering af '{key}'.", 'danger')

        # Opdater globale variabler for HASS (hvis de blev ændret)
        global HASS_URL, HASS_TOKEN
        new_hass_url = request.form.get('hass_url','').strip()
        new_hass_token = request.form.get('hass_token','').strip()
        if new_hass_url: HASS_URL = new_hass_url; os.environ['HASS_URL'] = new_hass_url
        if new_hass_token: HASS_TOKEN = new_hass_token; os.environ['HASS_TOKEN'] = new_hass_token

        if not error_occured:
            flash(f'{updated_count} indstillinger opdateret.', 'success')
        else:
             flash('Nogle indstillinger kunne ikke opdateres.', 'warning')

        return redirect(url_for('system_admin_settings'))

    # GET request
    settings = get_system_settings() # Henter fra cache eller DB/env
    # Tilføj admin username som ikke er i DB
    settings['admin_username'] = ADMIN_USERNAME

    # Sørg for at alle nøgler findes, selvom de er None (til template)
    all_keys = [
            'hass_url', 'hass_token', 'admin_username', 'unit_text', 'timestamp_format',
            'stripe_mode', 'stripe_publishable_key_test', 'stripe_secret_key_test', 'stripe_webhook_secret_test',
            'stripe_publishable_key_live', 'stripe_secret_key_live', 'stripe_webhook_secret_live',
            'admin_report_email', 'receipt_sender_email',
            'smtp_host', 'smtp_port', 'smtp_user', 'smtp_password', 'smtp_use_tls', 'smtp_use_ssl'
     ]
    for k in all_keys:
        settings.setdefault(k, '') # Sæt til tom streng hvis None/mangler

    # Konverter boolske strenge for TLS/SSL til faktiske booleans for template
    settings['smtp_use_tls_bool'] = str(settings.get('smtp_use_tls')).lower() == 'true'
    settings['smtp_use_ssl_bool'] = str(settings.get('smtp_use_ssl')).lower() == 'true'

    lang = session.get('language', 'da')
    trans = translations.get(lang, translations['da'])

    # Send BÅDE settings dict og translations dict til template
    return render_template('admin_system_settings.html', settings=settings, translations=trans)


# ... (test_hass_connection, admin_adjust_prices, admin_get_available_configured_meters,
#      admin_connect_meter_sys, admin_add_units, admin_remove_meter,
#      admin_meter_config, delete_meter_config uændret) ...
# --- Disse funktioner forbliver som de var ---
@app.route('/systemkontrolcenter23/test-hass-connection', methods=['POST'])
@admin_required
def test_hass_connection():
    # ... (uændret) ...
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
    # ... (uændret) ...
    print(f"DEBUG: Admin {current_user.username} forsøger at justere priser.")
    updated_count = 0
    error_occured = False
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn: raise Error("DB connection failed")
        cursor = conn.cursor() # Standard cursor til UPDATE

        for key, value in request.form.items():
            if key.startswith('price_'):
                try:
                    package_id = int(key.split('_')[1])
                    new_price = float(value.replace(',', '.'))
                    if new_price < 0:
                        print(f"WARN: Ignorerer negativ pris ({new_price}) for pakke ID {package_id}")
                        continue

                    print(f"DEBUG: Opdaterer pris for pakke ID {package_id} til {new_price}")
                    cursor.execute("UPDATE stroem_pakker SET pris = %s WHERE id = %s", (new_price, package_id))
                    if cursor.rowcount > 0: updated_count += 1

                except (ValueError, IndexError, TypeError) as parse_err:
                    print(f"WARN: Kunne ikke parse pris/ID fra form key '{key}' værdi '{value}': {parse_err}")
                    error_occured = True
                    continue

        if error_occured:
            flash('Nogle priser kunne ikke opdateres pga. ugyldigt format.', 'warning')
            if conn: conn.rollback()
        elif updated_count > 0:
            conn.commit()
            flash(f'Priserne er blevet opdateret for {updated_count} pakke(r).', 'success')
            print(f"INFO: Admin {current_user.username} opdaterede priser for {updated_count} pakker.")
        else:
            flash('Ingen priser blev ændret.', 'info')
            if conn: conn.rollback()

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
        if conn: safe_close_connection(conn)
    return redirect(url_for('admin_login_or_dashboard'))

# Note: Du har to endpoints med '/systemkontrolcenter23/get-available-meters'. Jeg beholder den sidste definition.
# Hvis den første var tiltænkt noget andet, skal den have et unikt route navn.
# @app.route('/systemkontrolcenter23/get-available-meters')
# @admin_required
# def admin_get_available_configured_meters(): # Behold funktionsnavn
#     # ... (uændret, som den var før)

@app.route('/systemkontrolcenter23/connect-meter', methods=['POST'])
@admin_required
def admin_connect_meter_sys():
    # ... (uændret) ...
    booking_id = request.form.get('connect_booking_id')
    meter_id = request.form.get('connect_meter_id')
    package_size_str = request.form.get('connect_package_size') # Hent som streng først
    conn = None; cursor = None

    if not all([booking_id, meter_id, package_size_str]):
        flash('Alle felter (Booking ID, Måler ID, Antal Enheder) skal udfyldes.', 'error')
        return redirect(url_for('admin_login_or_dashboard'))

    try:
        package_size = float(package_size_str.replace(',', '.')) # Håndter komma
        if package_size <= 0:
             raise ValueError("Antal enheder skal være positivt.")
    except ValueError as ve:
        flash(f'Ugyldigt antal enheder: {ve}', 'error')
        return redirect(url_for('admin_login_or_dashboard'))

    try:
        conn = get_db_connection()
        if not conn: raise Error("DB connection failed")
        cursor = conn.cursor(dictionary=True) # Brug dictionary cursor for nemmere adgang

        # Tjek om måler er ledig
        cursor.execute("SELECT booking_id FROM active_meters WHERE meter_id = %s", (meter_id,))
        existing_meter = cursor.fetchone()
        if existing_meter:
            flash(f'Måler {meter_id} er allerede i brug af booking {existing_meter["booking_id"]}.', 'error')
            return redirect(url_for('admin_login_or_dashboard'))

        # Tjek om booking ID findes
        cursor.execute("SELECT fornavn, efternavn FROM aktive_bookinger WHERE booking_id = %s", (booking_id,))
        booking_info = cursor.fetchone()
        if not booking_info:
            flash(f'Booking ID {booking_id} findes ikke i aktive bookinger.', 'error')
            return redirect(url_for('admin_login_or_dashboard'))

        # Find meter_config_id og evt. switch ID
        cursor.execute("SELECT id, power_switch_id, energy_sensor_id FROM meter_config WHERE sensor_id=%s AND is_active=1", (meter_id,))
        meter_config = cursor.fetchone()
        if not meter_config:
             flash(f'Måler konfiguration for {meter_id} ikke fundet eller er inaktiv.', 'error')
             return redirect(url_for('admin_login_or_dashboard'))
        meter_config_id = meter_config['id']
        power_switch_id = meter_config.get('power_switch_id')
        energy_sensor_id = meter_config.get('energy_sensor_id') or meter_id # Brug primær sensor hvis energy sensor ikke er sat

        # Hent den aktuelle målerværdi (brug den korrekte sensor)
        current_value = get_meter_value(energy_sensor_id)
        if current_value is None:
            flash(f'Kunne ikke læse startværdi fra måler {energy_sensor_id}. Måler er muligvis offline. Handlingen blev afbrudt.', 'error')
            return redirect(url_for('admin_login_or_dashboard'))

        # Start DB transaktion
        conn.start_transaction()
        std_cursor = conn.cursor() # Brug standard cursor til INSERT/UPDATE

        # Indsæt i active_meters
        sql_insert_active = """
            INSERT INTO active_meters (booking_id, meter_id, start_value, package_size, created_at)
            VALUES (%s, %s, %s, %s, NOW())
        """
        std_cursor.execute(sql_insert_active, (booking_id, meter_id, current_value, package_size))

        # Log handlingen i stroem_koeb (Antager pakke_id 1 er "Admin Tilføjelse" eller lignende)
        # **VIGTIGT**: Tilpas pakke_id og tabelstruktur hvis nødvendigt!
        # Her antager vi at 'stroem_koeb' nu har 'pris_betalt_ore' og 'koebs_tidspunkt'
        sql_insert_log = """
            INSERT INTO stroem_koeb (booking_id, pakke_id, maaler_id, enheder_tilbage, pris_betalt_ore, koebs_tidspunkt, stripe_checkout_session_id)
            VALUES (%s, %s, %s, %s, %s, NOW(), %s)
        """
        admin_note = f"AdminConnect:{current_user.id}" # Gem admin ID i stripe feltet evt.
        # Vi sætter pris til 0 for admin-tilføjelse
        std_cursor.execute(sql_insert_log, (booking_id, 1, meter_config_id, package_size, 0, admin_note)) # Pakke ID 1, Pris 0

        # Aktivér switch hvis konfigureret
        if power_switch_id and HASS_URL and HASS_TOKEN:
            try:
                print(f"DEBUG: Forsøger at tænde switch {power_switch_id} for {meter_id}")
                requests.post(
                    f"{HASS_URL}/api/services/switch/turn_on",
                    headers={"Authorization": f"Bearer {HASS_TOKEN}"},
                    json={"entity_id": power_switch_id},
                    timeout=10
                )
            except Exception as swe:
                # Log fejl, men fortsæt processen (måske HASS er nede)
                print(f"WARN admin_connect_meter: Kunne ikke tænde switch {power_switch_id}: {swe}")
                flash(f"Advarsel: Kunne ikke tænde for strømmen via Home Assistant ({power_switch_id}). Manuel aktivering kan være nødvendig.", "warning")

        # Commit transaktionen
        conn.commit()
        std_cursor.close()
        flash(f'Måler {meter_id} er nu tilknyttet booking {booking_id} med {package_size:.3f} enheder. Startværdi: {current_value:.3f}.', 'success')
        print(f"INFO: Admin {current_user.username} tilknyttede måler {meter_id} til booking {booking_id}")

    except Error as dbe:
        print(f"ERR admin_connect_meter DB: {dbe}")
        flash(f'Database fejl: {dbe}', 'error')
        if conn: conn.rollback()
    except Exception as e:
        print(f"ERR admin_connect_meter Gen: {e}")
        flash(f'Generel fejl: {str(e)}', 'error')
        if conn: conn.rollback()
    finally:
        if 'std_cursor' in locals() and std_cursor: std_cursor.close()
        if cursor: cursor.close()
        if conn: safe_close_connection(conn)

    return redirect(url_for('admin_login_or_dashboard'))

@app.route('/systemkontrolcenter23/add-units', methods=['POST'])
@admin_required
def admin_add_units():
    # ... (uændret) ...
    bid=request.form.get('booking_id'); ustr=request.form.get('units'); mid_input=request.form.get('meter_id_for_add'); conn=None; cursor=None
    if not all([bid,ustr,mid_input]): flash('Alle felter kræves.','warning'); return redirect(url_for('admin_login_or_dashboard'))
    try: units=float(ustr.replace(',','.')); assert units > 0
    except: flash('Ugyldigt antal enheder. Skal være et positivt tal.','warning'); return redirect(url_for('admin_login_or_dashboard'))

    try:
        conn=get_db_connection();
        if not conn: raise Error("DB fail")
        conn.start_transaction() # Start transaktion
        cursor=conn.cursor(dictionary=True);
        # Hent aktiv forbindelse OG meter config id
        cursor.execute("""
            SELECT am.id, mc.id as meter_config_id
            FROM active_meters am
            LEFT JOIN meter_config mc ON am.meter_id = mc.sensor_id
            WHERE am.booking_id=%s AND am.meter_id=%s
            """,(bid,mid_input))
        connection=cursor.fetchone();
        if not connection:
            flash(f'Måler {mid_input} er ikke aktiv for booking {bid}.','warning');
            raise Exception("Connection not found")
        active_meter_id = connection['id']
        meter_config_id = connection.get('meter_config_id') # Kan være None hvis config slettet

        print(f"DEBUG: Tilføjer {units} enheder til {mid_input} (active_id: {active_meter_id}) for booking {bid}.")
        upd_cursor=conn.cursor();
        upd_cursor.execute("UPDATE active_meters SET package_size=package_size+%s WHERE id=%s",(units,active_meter_id));
        rows=upd_cursor.rowcount;
        upd_cursor.close()

        if rows > 0:
            try: # Log købet/tilføjelsen
                 log_cursor=conn.cursor();
                 # Brug pakke_id 2 for "Admin Tilføj Enheder" eller lignende
                 # Antager `stroem_koeb` har pris og stripe id felter
                 sql_log = """
                     INSERT INTO stroem_koeb (booking_id, pakke_id, maaler_id, enheder_tilbage, pris_betalt_ore, koebs_tidspunkt, stripe_checkout_session_id)
                     VALUES (%s, %s, %s, %s, %s, NOW(), %s)
                 """
                 admin_note = f"AdminAddUnits:{current_user.id}"
                 log_cursor.execute(sql_log, (bid, 2, meter_config_id, units, 0, admin_note)) # Pakke ID 2, Pris 0
                 log_cursor.close()
                 conn.commit(); # Commit hele transaktionen
                 flash(f'Tilføjet {units:.3f} enheder til måler {mid_input} for booking {bid}.','success')
                 print(f"INFO: Admin {current_user.username} tilføjede {units} enheder til {mid_input} ({bid})")

            except Error as loge:
                print(f"WARN add_units log DB: {loge}")
                conn.rollback() # Rul tilbage hvis log fejler
                flash(f'Fejl ved logning af tilføjelse: {loge}. Handlingen blev annulleret.', 'danger')
            except Exception as logge:
                 print(f"WARN add_units log Gen: {logge}")
                 conn.rollback()
                 flash(f'Generel fejl ved logning: {logge}. Handlingen blev annulleret.', 'danger')

        else:
            conn.rollback(); # Rul tilbage hvis UPDATE fejlede
            flash(f'Opdatering af enheder fejlede for måler {mid_input}.','danger')

    except Error as dbe:
        print(f"ERR add_units DB: {dbe}");
        flash(f'Database Fejl: {dbe}','danger');
        if conn: conn.rollback()
    except Exception as e:
        print(f"ERR add_units Gen: {e}");
        flash(f'Generel Fejl: {str(e)}','danger');
        if conn: conn.rollback()
    finally:
        if 'upd_cursor' in locals() and upd_cursor: upd_cursor.close()
        if 'log_cursor' in locals() and log_cursor: log_cursor.close()
        if cursor: cursor.close()
        if conn: safe_close_connection(conn)
    return redirect(url_for('admin_login_or_dashboard'))

@app.route('/systemkontrolcenter23/remove-meter', methods=['POST'])
@admin_required
def admin_remove_meter():
    # ... (uændret, men tjek logning) ...
    bid=request.form.get('booking_id'); mid=request.form.get('meter_id'); conn=None; cursor=None
    if not bid or not mid: flash('Booking ID og Måler ID skal udfyldes.','warning'); return redirect(url_for('admin_login_or_dashboard'))

    try:
        conn=get_db_connection();
        if not conn: raise Error("DB connection failed")
        conn.start_transaction() # Start transaktion

        # Find måler config ID før sletning for logning
        cursor=conn.cursor(dictionary=True)
        cursor.execute("SELECT mc.id as meter_config_id, mc.power_switch_id, am.id as active_meter_id FROM active_meters am LEFT JOIN meter_config mc ON am.meter_id = mc.sensor_id WHERE am.booking_id=%s AND am.meter_id=%s", (bid, mid))
        meter_info = cursor.fetchone()

        if not meter_info:
            flash(f'Ingen aktiv forbindelse fundet for måler {mid} og booking {bid}.', 'warning')
            conn.rollback() # Ingen grund til at fortsætte
            return redirect(url_for('admin_login_or_dashboard'))

        active_meter_id = meter_info['active_meter_id']
        meter_config_id = meter_info.get('meter_config_id') # Kan være None
        power_switch_id = meter_info.get('power_switch_id')

        # Slet den aktive forbindelse
        del_cursor = conn.cursor()
        del_cursor.execute("DELETE FROM active_meters WHERE id=%s", (active_meter_id,))
        rows = del_cursor.rowcount
        del_cursor.close()

        if rows > 0:
            # Ryd cache for måleren
            cache.delete(f"meter_value_{mid}")
            cache.delete(f"meter_value_{normalize_meter_id(mid, True)}")
            cache.delete(f"meter_value_{normalize_meter_id(mid, False)}")
            cache.delete(f"meter_config_switch_{mid}") # Ryd også switch cache

            # Forsøg at slukke for strømmen
            if not power_switch_id and mid.startswith('sensor.'): # Prøv at gætte switch ID
                 base=mid.split('.')[1].split('_')[0]; power_switch_id=f"switch.{base}_0"

            if power_switch_id and HASS_URL and HASS_TOKEN:
                try:
                    print(f"DEBUG remove_meter: Forsøger at slukke switch {power_switch_id}")
                    requests.post(f"{HASS_URL}/api/services/switch/turn_off",headers={"Authorization":f"Bearer {HASS_TOKEN}"},json={"entity_id":power_switch_id},timeout=10)
                except Exception as swe:
                    print(f"WARN remove_meter switch off failed for {power_switch_id}: {swe}")
                    flash(f"Advarsel: Kunne ikke slukke for strømmen ({power_switch_id}). Manuel deaktivering kan være nødvendig.", "warning")

            try: # Log fjernelsen (brug pakke_id 3 for "Admin Fjernet"?)
                 log_cursor=conn.cursor()
                 sql_log = """
                     INSERT INTO stroem_koeb (booking_id, pakke_id, maaler_id, enheder_tilbage, pris_betalt_ore, koebs_tidspunkt, stripe_checkout_session_id)
                     VALUES (%s, %s, %s, %s, %s, NOW(), %s)
                 """
                 admin_note = f"AdminRemove:{current_user.id}"
                 # Log med 0 enheder og 0 pris
                 log_cursor.execute(sql_log, (bid, 3, meter_config_id, 0, 0, admin_note)) # Pakke ID 3
                 log_cursor.close()
                 conn.commit(); # Commit hele transaktionen
                 flash(f'Måler {mid} fjernet fra booking {bid}.','success')
                 print(f"INFO: Admin {current_user.username} fjernede måler {mid} fra booking {bid}")

            except Error as loge:
                print(f"WARN remove_meter log DB: {loge}")
                conn.rollback() # Rul tilbage hvis log fejler
                flash(f'Måler fjernet, men fejl ved logning: {loge}.', 'danger')
            except Exception as logge:
                 print(f"WARN remove_meter log Gen: {logge}")
                 conn.rollback()
                 flash(f'Måler fjernet, men generel fejl ved logning: {logge}.', 'danger')

        else:
            # Dette burde ikke ske hvis vi fandt meter_info, men for en sikkerheds skyld
            flash(f'Kunne ikke finde eller slette forbindelsen for måler {mid} / booking {bid}.','error');
            conn.rollback()

    except Error as dbe:
        print(f"ERR remove_meter DB: {dbe}"); flash(f'Database Fejl: {dbe}','danger');
        if conn: conn.rollback()
    except Exception as e:
        print(f"ERR remove_meter Gen: {e}"); flash(f'Generel Fejl: {str(e)}','danger');
        if conn: conn.rollback()
    finally:
        if 'del_cursor' in locals() and del_cursor: del_cursor.close()
        if 'log_cursor' in locals() and log_cursor: log_cursor.close()
        if cursor: cursor.close()
        if conn: safe_close_connection(conn)
    return redirect(url_for('admin_login_or_dashboard'))

@app.route('/admin/meter_config', methods=['GET', 'POST'])
@admin_required
def admin_meter_config():
    # ... (uændret) ...
    conn=None; cursor=None; form_data=None; ha_sensors=[]; ha_switches=[]; cfgs=[]
    if request.method == 'POST':
        form_data=request.form; cid=form_data.get('config_id'); sid=form_data.get('sensor_id','').strip(); dname=form_data.get('display_name','').strip(); loc=form_data.get('location','').strip(); active=1 if form_data.get('is_active') else 0; esid=form_data.get('energy_sensor_id','').strip() or None; psid=form_data.get('power_switch_id','').strip() or None

        if not sid or not dname: flash('Sensor ID og Visningsnavn er påkrævet.','error')
        elif not sid.startswith('sensor.'): flash('Sensor ID skal starte med "sensor."','warning')
        elif esid and not esid.startswith('sensor.'): flash('Energi Sensor ID skal starte med "sensor."','warning')
        elif psid and not psid.startswith('switch.'): flash('Power Switch ID skal starte med "switch."','warning')
        else:
            try:
                conn=get_db_connection();
                if not conn: raise Error("DB connection failed")
                cursor=conn.cursor(dictionary=True);
                # Tjek om sensor ID allerede bruges af en *anden* konfiguration
                check_sql = "SELECT id FROM meter_config WHERE sensor_id=%s"
                check_params = [sid]
                if cid: # Hvis vi redigerer, ekskluder den nuværende config ID
                    check_sql += " AND id!=%s"
                    check_params.append(cid)
                cursor.execute(check_sql, tuple(check_params))
                existing_cfg=cursor.fetchone()

                if existing_cfg:
                    flash(f'Sensor ID {sid} er allerede i brug af en anden konfiguration (ID: {existing_cfg["id"]}).','error')
                else: # Gem/Opdater
                    if cid: # Opdater
                        sql='''UPDATE meter_config SET sensor_id=%s,display_name=%s,location=%s,is_active=%s,energy_sensor_id=%s,power_switch_id=%s WHERE id=%s'''
                        params=(sid,dname,loc,active,esid if esid else None,psid if psid else None,cid) # Sørg for at gemme NULL hvis tom
                        msg=f'Konfiguration for "{dname}" opdateret.'
                    else: # Indsæt ny
                        sql='''INSERT INTO meter_config (sensor_id,display_name,location,is_active,energy_sensor_id,power_switch_id) VALUES (%s,%s,%s,%s,%s,%s)'''
                        params=(sid,dname,loc,active,esid if esid else None,psid if psid else None) # Sørg for at gemme NULL hvis tom
                        msg=f'Konfiguration for "{dname}" tilføjet.'

                    update_cursor = conn.cursor() # Brug standard cursor til INSERT/UPDATE
                    update_cursor.execute(sql, params)
                    update_cursor.close()
                    conn.commit();
                    flash(msg,'success');
                    form_data=None; # Ryd formulardata ved succes
                    # Ryd cache for switch ID hvis det blev ændret
                    if psid: cache.delete(f"meter_config_switch_{sid}")
                    return redirect(url_for('admin_meter_config')) # Redirect for at undgå re-POST

            except Error as dbe: flash(f'Database Fejl: {dbe}','error'); print(f"ERR mtr_cfg POST DB: {dbe}"); conn.rollback()
            except Exception as e: flash(f'Generel Fejl: {str(e)}','error'); print(f"ERR mtr_cfg POST Gen: {e}"); conn.rollback()
            finally:
                if 'update_cursor' in locals() and update_cursor: update_cursor.close()
                if cursor: cursor.close()
                if conn: safe_close_connection(conn)
    # GET request (eller hvis POST fejlede og vi render igen)
    try:
        # Hent HA entities
        if HASS_URL and HASS_TOKEN:
             resp=requests.get(f"{HASS_URL}/api/states",headers={"Authorization":f"Bearer {HASS_TOKEN}"},timeout=15) # Øget timeout lidt
             if resp.status_code==200:
                  entities = resp.json()
                  ha_sensors=[{'id':e['entity_id'],'name':e['attributes'].get('friendly_name',e['entity_id'])} for e in entities if e['entity_id'].startswith('sensor.')]
                  ha_sensors.sort(key=lambda x:x['id'])
                  ha_switches=[{'id':e['entity_id'],'name':e['attributes'].get('friendly_name',e['entity_id'])} for e in entities if e['entity_id'].startswith('switch.')]
                  ha_switches.sort(key=lambda x:x['id'])
             else: flash(f'Home Assistant API fejl: Status {resp.status_code}','warning'); print(f"WARN HA fetch states: {resp.status_code}")
        else: flash('Home Assistant URL eller Token mangler i konfigurationen. Kan ikke hente sensor/switch liste.','warning')

        # Hent konfigurerede målere fra DB
        conn=get_db_connection()
        if conn:
            cursor=conn.cursor(dictionary=True);
            cursor.execute('SELECT * FROM meter_config ORDER BY display_name')
            cfgs=cursor.fetchall()
        else: flash('Databaseforbindelse fejlede. Kunne ikke hente gemte konfigurationer.','error')

    except requests.exceptions.RequestException as req_e: flash(f'Netværksfejl ved kommunikation med Home Assistant: {req_e}','error'); print(f"ERR HA fetch states: {req_e}")
    except Error as dbe: flash(f'Database Fejl ved hentning af konfigurationer: {dbe}','error'); print(f"ERR mtr_cfg GET DB: {dbe}")
    except Exception as e: flash(f'Generel Fejl: {str(e)}','error'); print(f"ERR mtr_cfg GET Gen: {e}")
    finally:
        if cursor: cursor.close()
        if conn: safe_close_connection(conn)

    # Organiser sensorer i grupper (uændret)
    sensor_groups = {}
    for sensor in ha_sensors:
        parts = sensor['id'].split('.')
        if len(parts) > 1:
            base_name = parts[1].split('_')[0]
            if base_name not in sensor_groups: sensor_groups[base_name] = []
            sensor_groups[base_name].append(sensor)

    return render_template('admin_meter_config.html', ha_sensors=ha_sensors, ha_switches=ha_switches, configured_meters=cfgs, form_data=form_data, sensor_groups=sensor_groups)

@app.route('/admin/delete_meter_config/<int:config_id>', methods=['POST'])
@admin_required
def delete_meter_config(config_id):
    # ... (uændret) ...
    conn=None; cursor=None
    try:
        conn=get_db_connection();
        if not conn: raise Error("DB fail")
        cursor=conn.cursor(dictionary=True);
        # Hent sensor ID før sletning for at rydde cache
        cursor.execute("SELECT sensor_id FROM meter_config WHERE id=%s",(config_id,))
        cfg=cursor.fetchone()

        if not cfg:
            flash(f'Konfiguration med ID {config_id} blev ikke fundet.','warning')
        else:
             sid=cfg['sensor_id'];
             # Tjek om måleren er i brug i active_meters
             cursor.execute("SELECT id FROM active_meters WHERE meter_id=%s LIMIT 1",(sid,))
             if cursor.fetchone():
                  flash(f'Kan ikke slette: Måleren {sid} er aktivt i brug. Fjern den fra bookingen først.','error')
             else:
                  # Slet konfigurationen
                  cd=conn.cursor();
                  cd.execute('DELETE FROM meter_config WHERE id=%s',(config_id,))
                  deleted=cd.rowcount;
                  cd.close()
                  if deleted>0:
                       conn.commit();
                       cache.delete(f"meter_config_switch_{sid}") # Ryd cache for switch
                       flash(f'Konfiguration for {sid} blev slettet.','success')
                       print(f"INFO: Admin {current_user.username} slettede meter config ID {config_id} ({sid})")
                  else:
                       conn.rollback();
                       flash(f'Fejl: Kunne ikke slette konfiguration ID {config_id}.','error')
    except Error as db_e: flash(f'Database Fejl: {db_e}','danger'); conn.rollback()
    except Exception as e: flash(f'Generel Fejl: {str(e)}','danger'); conn.rollback()
    finally:
        if 'cd' in locals() and cd: cd.close()
        if cursor: cursor.close()
        if conn: safe_close_connection(conn)
    return redirect(url_for('admin_meter_config'))

# --- KUN admin login/dashboard route ---
@app.route('/systemkontrolcenter23', methods=['GET', 'POST'])
def admin_login_or_dashboard():
    # ... (login/vis dashboard logik uændret) ...
    if current_user.is_authenticated and getattr(current_user, 'is_admin', False):
        if request.method == 'POST': pass # Ignorer POST hvis allerede logget ind

        print(f"DEBUG: Admin {current_user.username} viser dashboard.")
        packages = []; active_meters_data = []; conn = None; cursor = None
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor(dictionary=True)
                # Hent pakker
                cursor.execute("SELECT id, navn, type, enheder, dage, pris FROM stroem_pakker WHERE aktiv = 1 ORDER BY type, enheder, dage, id")
                packages = cursor.fetchall()
                # Hent aktive målere med booking info
                cursor.execute("""
                    SELECT am.id, am.booking_id, am.meter_id, am.start_value, am.package_size, am.created_at,
                           mc.display_name as meter_name, mc.location,
                           ab.fornavn, ab.efternavn, ab.plads_nr
                    FROM active_meters am
                    LEFT JOIN meter_config mc ON am.meter_id = mc.sensor_id
                    LEFT JOIN aktive_bookinger ab ON am.booking_id = ab.booking_id
                    ORDER BY ab.plads_nr, am.booking_id
                """)
                active_meters_data = cursor.fetchall()

            else: flash('Databaseforbindelse fejlede. Kunne ikke hente data.', 'warning')
        except Error as e: flash(f'Database Fejl ved hentning af dashboard data: {str(e)}', 'danger')
        except Exception as e: flash(f'Generel Fejl ved hentning af dashboard data: {str(e)}', 'danger')
        finally:
            if cursor: cursor.close()
            if conn: safe_close_connection(conn)

        lang = session.get('language', 'da')
        trans = translations.get(lang, translations['da'])

        return render_template('admin_dashboard.html',
                                packages=packages,
                                active_meters=active_meters_data,
                                translations=trans) # Send translations med

    # Håndter login forsøg
    if request.method == 'POST':
        username=request.form.get('username'); password=request.form.get('password')
        admin_user_env=os.getenv('ADMIN_USERNAME','admin'); admin_pass_env=os.getenv('ADMIN_PASSWORD','password')
        # Brug en mere sikker sammenligning hvis password var hashed
        if username == admin_user_env and password == admin_pass_env: # Simpel sammenligning her
            admin=User(id="999999",username=admin_user_env,is_admin=True); login_user(admin);
            print(f"DEBUG: Admin '{admin_user_env}' logget ind.")
            next_page = request.args.get('next') # Håndter redirect efter login
            return redirect(next_page or url_for('admin_login_or_dashboard'))
        else:
            print(f"DEBUG: Fejl admin login for '{username}'.");
            flash('Ugyldigt admin brugernavn eller adgangskode.', 'danger')

    print("DEBUG: Viser admin login side.")
    lang = session.get('language', 'da')
    trans = translations.get(lang, translations['da'])
    return render_template('systemadmin_login.html', translations=trans)


# --- ALMINDELIGE BRUGER ROUTES ---

@app.route('/')
def index():
    # ... (uændret) ...
    lang=session.get('language','da');
    if lang not in translations: lang='da'; session['language']=lang
    trans=translations.get(lang,translations['da'])
    if current_user.is_authenticated:
        if getattr(current_user,'is_admin',False):
            return redirect(url_for('admin_login_or_dashboard'))
        # Bruger er logget ind, men ikke admin
        return render_template('index.html', current_time=get_formatted_timestamp(), translations=trans)
    else: # Ikke logget ind
        return render_template('index.html', current_time=get_formatted_timestamp(), translations=trans)

@app.route('/set_language/<lang>')
def set_language(lang):
    # ... (uændret) ...
    if lang in translations:
        session['language']=lang
        if current_user.is_authenticated and not getattr(current_user,'is_admin',False):
            conn=None; cursor=None
            try:
                conn=get_db_connection()
                if conn:
                    cursor=conn.cursor()
                    cursor.execute("UPDATE users SET language=%s WHERE id=%s",(lang,current_user.id))
                    conn.commit()
            except Error as e: print(f"Err set_lang DB: {e}"); conn.rollback()
            except Exception as e: print(f"Err set_lang Gen: {e}")
            finally:
                if cursor: cursor.close()
                if conn: safe_close_connection(conn)
    # Redirect tilbage til forrige side eller index
    return redirect(request.referrer or url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    # ... (uændret - bruger User class med email nu) ...
    lang=session.get('language','da'); trans=translations.get(lang,translations['da'])
    if request.method=='POST':
        username=request.form.get('booking_id'); password=request.form.get('lastname')
        if not username or not password: flash(trans['login_error_missing'],'error'); return redirect(url_for('login'))

        conn=None; cursor=None
        try:
            conn=get_db_connection();
            if not conn: flash(trans['error_db_connection'],'error'); return redirect(url_for('login'))
            cursor=conn.cursor(dictionary=True)
            # Find booking
            cursor.execute("SELECT * FROM aktive_bookinger WHERE booking_id=%s AND LOWER(efternavn)=LOWER(%s)",(username,password)); booking=cursor.fetchone()
            if booking:
                # Find eller opret bruger
                cursor.execute("SELECT * FROM users WHERE username=%s",(username,)); user_data=cursor.fetchone();
                hashed_pw=generate_password_hash(password) # Hash altid password ved login/opret

                if not user_data: # Opret bruger hvis ikke findes
                    print(f"DEBUG Login: Opretter ny bruger for {username}")
                    insert_sql = """
                        INSERT INTO users (username, password, fornavn, efternavn, email, language)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(insert_sql, (username, hashed_pw, booking.get('fornavn',''), booking.get('efternavn',''), booking.get('email',''), lang))
                    conn.commit();
                    user_id = cursor.lastrowid
                    user_data = {'id': user_id, 'username': username, 'fornavn': booking.get('fornavn',''), 'efternavn': booking.get('efternavn',''), 'email': booking.get('email',''), 'language': lang}
                else: # Opdater eksisterende brugerinfo hvis nødvendigt
                    updates = {}
                    # Opdater email hvis den er forskellig OG findes i booking
                    if booking.get('email') and user_data.get('email') != booking.get('email'):
                        updates['email'] = booking.get('email')
                    # Opdater sprog hvis forskelligt
                    if user_data.get('language') != lang:
                        updates['language'] = lang
                    # Opdater altid password hash ved login
                    updates['password'] = hashed_pw
                    # Opdater fornavn/efternavn hvis de er tomme i DB men findes i booking
                    if not user_data.get('fornavn') and booking.get('fornavn'):
                        updates['fornavn'] = booking.get('fornavn')
                    if not user_data.get('efternavn') and booking.get('efternavn'):
                        updates['efternavn'] = booking.get('efternavn')

                    if updates:
                        print(f"DEBUG Login: Opdaterer bruger {username} med: {updates.keys()}")
                        set_clauses = ", ".join([f"{k}=%s" for k in updates])
                        update_values = list(updates.values()) + [user_data['id']]
                        sql = f"UPDATE users SET {set_clauses} WHERE id=%s"
                        cursor.execute(sql, tuple(update_values))
                        conn.commit()
                    # Opdater user_data dict med ændringer til User objektet
                    user_data.update(updates)


                # Opret User objekt og log ind
                user_obj = User(id=user_data['id'], username=user_data['username'],
                                fornavn=user_data.get('fornavn'), efternavn=user_data.get('efternavn'),
                                email=user_data.get('email')) # Email hentes fra user_data
                login_user(user_obj);
                flash(f"{trans.get('welcome')} {user_obj.fornavn or ''} {user_obj.efternavn or ''}!",'success')
                # Ryd evt. gammel 'pending purchase' hvis brugeren logger ind igen
                session.pop('pending_purchase', None)
                session.pop('selected_meter', None)
                return redirect(url_for('index'))
            else: # Booking ikke fundet
                flash(trans['login_error_invalid'],'error')
        except Error as e: print(f"Login DB Error: {e}"); flash(trans['login_error_generic'],'error'); conn.rollback()
        except Exception as e: print(f"Login General Error: {e}"); flash(trans['login_error_generic'],'error'); conn.rollback()
        finally:
            if cursor: cursor.close()
            if conn: safe_close_connection(conn)

    # GET request
    return render_template('login.html',translations=trans)

@app.route('/logout')
@login_required
def logout():
    # ... (uændret) ...
    lang=session.get('language','da'); trans=translations.get(lang,translations['da'])
    print(f"INFO: Bruger {current_user.username} logger ud.")
    logout_user();
    # Ryd session data relateret til køb/måler ved logout
    session.pop('pending_purchase', None)
    session.pop('selected_meter', None)
    flash(trans['logout_message'],'success');
    return redirect(url_for('index'))

@app.route('/stroem_dashboard')
@login_required
def stroem_dashboard():
    # ... (Stort set uændret, henter nu settings via get_system_settings) ...
    lang = session.get('language', 'da'); trans = translations.get(lang, translations['da'])
    conn = None; cursor = None; meter_data = None; error_message = None; is_meter_online_flag = False
    print(f"\n===== START STRØM DASHBOARD (Bruger: {current_user.username}) =====")
    try:
        # Hent systemindstillinger (fra cache eller DB/env)
        settings = get_system_settings()
        unit_text = settings.get('unit_text', 'enheder')
        time_format = settings.get('timestamp_format', '%Y-%m-%d %H:%M:%S')

        conn = get_db_connection()
        if not conn: flash(trans['error_db_connection'], 'error'); return redirect(url_for('index')) # Gå til index ved DB fejl her?
        cursor = conn.cursor(dictionary=True)

        print(f"DEBUG stroem_dash: Henter aktiv måler for '{current_user.username}'")
        cursor.execute("""
            SELECT am.meter_id, am.start_value, am.package_size, mc.power_switch_id, mc.display_name, mc.energy_sensor_id
            FROM active_meters am
            LEFT JOIN meter_config mc ON am.meter_id = mc.sensor_id
            WHERE am.booking_id=%s
            LIMIT 1
        """,(current_user.username,))
        meter_data = cursor.fetchone()
        print(f"DEBUG stroem_dash: Rå DB data: {meter_data}")

        safe_close_connection(conn); conn = None; cursor = None # Luk DB hurtigt

        if not meter_data or not meter_data.get('meter_id'):
            print(f"DEBUG stroem_dash: Ingen aktiv meter_id for '{current_user.username}'. Redirect til valg.")
            flash(trans['error_no_active_meter'], 'info')
            return redirect(url_for('select_meter'))

        meter_id = meter_data['meter_id']
        db_start = meter_data.get('start_value')
        db_pkg = meter_data.get('package_size')
        power_switch_id = meter_data.get('power_switch_id')
        meter_display_name = meter_data.get('display_name', meter_id)
        # Brug den specifikke energy sensor til aflæsning hvis den er sat, ellers hovedsensoren
        sensor_to_read = meter_data.get('energy_sensor_id') or meter_id
        print(f"DEBUG stroem_dash: Fundet meter='{meter_id}', læser fra='{sensor_to_read}', switch='{power_switch_id}'")

        try:
            start_value = float(db_start if db_start is not None else 0.0)
            package_size = float(db_pkg if db_pkg is not None else 0.0)
        except (ValueError, TypeError) as e:
            print(f"ERR stroem_dash: Ugyldige DB værdier for start/pakke: {e}")
            flash(trans['error_invalid_values'], 'error')
            # Overvej hvad der skal ske her. Måske redirect til admin? Eller index?
            return redirect(url_for('index')) # Går til index for nu

        # Sæt en lille minimumsværdi for at undgå division med nul
        effective_package_size = max(package_size, 0.001)

        # Hent NUVÆRENDE værdi (brug den korrekte sensor)
        current_value = get_meter_value(sensor_to_read)

        if current_value is None:
            error_message = trans['error_reading_meter']
            is_meter_online_flag = False
            flash(error_message + f" ({sensor_to_read}). Viser sidst kendte data eller startværdi.", 'warning')
            # Hvad viser vi? Vi kan ikke beregne forbrug. Viser 0 forbrug og pakken som remaining?
            current_value_fallback = start_value # Fallback til startværdi for visning
            current_value_disp = f"{format_number(current_value_fallback)} ({trans.get('offline','Offline')})"
            start_value_disp = format_number(start_value)
            total_usage_disp = format_number(0.0) # Kan ikke beregnes
            remaining_disp = format_number(package_size) # Viser hele pakken som tilbage
            percentage = 0 # Viser 0% brugt
            print(f"WARN stroem_dash: Kunne ikke læse værdi fra {sensor_to_read}. Fallback.")
        else:
            is_meter_online_flag = True
            total_usage = current_value - start_value
            # Håndter måler reset eller udskiftning (hvis current < start)
            if total_usage < -0.01: # Tillad en lille negativ afvigelse pga. float præcision
                print(f"WARN stroem_dash: Negativt forbrug detekteret ({total_usage:.3f}) for {meter_id}. Mulig måler reset/udskiftning. Behandler som 0 forbrug fra start.")
                # Hvad skal ske her? Nulstille startværdi? For nu viser vi 0 forbrug.
                # Overvej at logge dette og/eller notificere admin.
                total_usage = 0 # Sæt forbrug til 0 i dette tilfælde for visning
                # Alternativt: current_value (hvis det giver mening at starte forfra)
                # start_value = current_value # Nulstil startværdi (kræver DB update!)

            # Sikrer at forbrug ikke er negativt for beregning
            total_usage = max(0, total_usage)
            remaining = max(0, package_size - total_usage)
            # Beregn procentdel baseret på den effektive pakkestørrelse
            percentage = int(min(100, (total_usage / effective_package_size) * 100))

            current_value_disp = format_number(current_value)
            start_value_disp = format_number(start_value)
            total_usage_disp = format_number(total_usage)
            remaining_disp = format_number(remaining)

        # Hent switch state
        # Prøv at gætte switch ID hvis ikke fundet i DB (som før)
        if not power_switch_id and meter_id.startswith('sensor.'):
            base=meter_id.split('.')[1].split('_')[0]; power_switch_id=f"switch.{base}_0"
            print(f"DEBUG stroem_dash: Gættet switch ID: {power_switch_id}")

        power_switch_state = "unknown" # Default
        if power_switch_id:
            power_switch_state = get_switch_state(power_switch_id)
            if is_meter_online_flag and power_switch_state in ['unavailable', 'unknown']:
                print(f"WARN stroem_dash: Sensor {sensor_to_read} online, men switch {power_switch_id} er {power_switch_state}")
                flash(f"Advarsel: Kan ikke fjernstyre strømmen, kontakten ({power_switch_id}) er utilgængelig i Home Assistant.","warning")
            elif not is_meter_online_flag and power_switch_state == 'on':
                print(f"WARN stroem_dash: Sensor {sensor_to_read} offline, men switch {power_switch_id} er tændt.")
                flash(f"Advarsel: Måleren ({sensor_to_read}) ser ud til at være offline, men kontakten ({power_switch_id}) er tændt. Kontakt evt. admin.", "warning")
        else:
            print(f"DEBUG stroem_dash: Ingen power_switch_id fundet eller gættet for {meter_id}.")
            flash(f"Info: Ingen kontakt tilknyttet denne måler ({meter_display_name}). Fjernstyring af strøm er ikke mulig.", "info")


        return render_template('stroem_dashboard.html',
                               translations=trans,
                               error_message=error_message,
                               current_value=current_value_disp,
                               start_value=start_value_disp,
                               total_usage=total_usage_disp,
                               remaining=remaining_disp,
                               meter_id=meter_id, # Selve målerens ID
                               meter_display_name=meter_display_name, # Visningsnavn
                               unit_text=unit_text,
                               percentage=percentage,
                               package_size=format_number(package_size), # Vis formateret
                               power_switch_state=power_switch_state,
                               power_switch_id=power_switch_id,
                               updated=get_formatted_timestamp(time_format),
                               is_meter_online=is_meter_online_flag)

    except Error as db_e_main: print(f"FATAL stroem_dash DB: {db_e_main}"); flash(trans['error_db_connection'],'error'); return redirect(url_for('index'))
    except Exception as e_main: print(f"FATAL stroem_dash Gen: {str(e_main)}"); traceback.print_exc(); flash(f"{trans['error_reading_data']}: {str(e_main)}",'error'); return redirect(url_for('index'))
    finally:
         if cursor: cursor.close()
         if conn: safe_close_connection(conn)
         print(f"===== END STRØM DASHBOARD =====")


@app.route('/select_meter', methods=['GET', 'POST'])
@login_required
def select_meter():
    # ... (POST del er stort set uændret, gemmer i session['selected_meter']) ...
    lang=session.get('language','da'); trans=translations.get(lang,translations['da'])
    if request.method == 'POST':
        mid = request.form.get('meter_id')
        if not mid: flash(trans['error_no_meter'],'error'); return redirect(url_for('select_meter'))
        conn=None; cursor=None
        try:
            conn=get_db_connection()
            if not conn: flash(trans['error_db_connection'],'error'); raise Exception("DB fail")
            cursor=conn.cursor(dictionary=True);
            # Hent meter config
            cursor.execute("SELECT * FROM meter_config WHERE sensor_id=%s AND is_active=1",(mid,))
            cfg=cursor.fetchone()
            if not cfg: flash(trans['error_invalid_meter'],'error'); raise Exception(f"No active config for {mid}")

            # Tjek om måler allerede er aktiv for EN ANDEN bruger
            cursor.execute("SELECT booking_id FROM active_meters WHERE meter_id=%s AND booking_id!=%s",(mid, current_user.username))
            active_for_other = cursor.fetchone()
            if active_for_other:
                flash(f"{trans['meter_already_active']} (Booking: {active_for_other['booking_id']})", 'error');
                session.pop('selected_meter', None)
                raise Exception("Meter taken by other user")

            # Tjek om DENNE bruger allerede HAR denne måler aktiv
            cursor.execute("SELECT id FROM active_meters WHERE meter_id=%s AND booking_id=%s", (mid, current_user.username))
            active_for_self = cursor.fetchone()
            if active_for_self:
                flash(f"Du har allerede denne måler ({cfg.get('display_name', mid)}) aktiv. Gå til dashboardet eller vælg en tillægspakke.", 'info')
                # Send brugeren videre til dashboardet i stedet for pakkervalg?
                return redirect(url_for('stroem_dashboard'))

            # Hent startværdi - brug energy_sensor_id hvis sat, ellers primær sensor_id
            sread = cfg.get('energy_sensor_id') or cfg['sensor_id']
            print(f"DEBUG SELECT_METER POST: Bruger={current_user.username}, Måler valgt={mid}, Læser startværdi fra={sread}")

            # Ryd cache for den specifikke sensor vi skal læse
            cache.delete(f"meter_value_{sread}")
            cache.delete(f"meter_value_{normalize_meter_id(sread, True)}")
            cache.delete(f"meter_value_{normalize_meter_id(sread, False)}")

            # Hent startværdi (get_meter_value prøver flere varianter)
            curr = get_meter_value(sread)
            print(f"DEBUG SELECT_METER POST: Startværdi hentet for {sread}: {curr} (type: {type(curr)})")

            if curr is None or not isinstance(curr,(int, float)):
                error_msg = f"Måler '{cfg.get('display_name',mid)}' ({sread}) er offline eller returnerer en ugyldig værdi. "
                error_msg += "Prøv igen om et øjeblik. Kontakt administrator hvis problemet fortsætter."
                flash(error_msg,'error')
                session.pop('selected_meter', None)
                raise Exception("Invalid start value from meter")

            # Gem i session til næste step (pakkervalg)
            session['selected_meter'] = {
                'meter_config_id': cfg['id'],
                'sensor_id': cfg['sensor_id'], # Det ID der skal gemmes i active_meters
                'display_name': cfg.get('display_name', cfg['sensor_id']),
                'location': cfg.get('location', ''),
                'start_value': curr,
                'sensor_read_for_start': sread # Hvilken sensor vi brugte til at få startværdien
            }
            print(f"DEBUG SELECT_METER POST: Gemmer i session['selected_meter']: {session['selected_meter']}")
            flash(f"Måler '{cfg.get('display_name',mid)}' valgt. Startværdi: {format_number(curr)}. Vælg nu en pakke.",'success')
            # Ryd evt. gammel pending purchase, hvis brugeren starter forfra
            session.pop('pending_purchase', None)
            return redirect(url_for('select_package'))

        except Error as dbe:
            print(f"ERR select_meter POST DB: {dbe}");
            flash(f"Databasefejl: {dbe}", 'error')
            session.pop('selected_meter',None);
            return redirect(url_for('select_meter'))
        except Exception as e:
            print(f"ERR select_meter POST Gen: {e}");
            # Undgå at vise interne exceptions til brugeren direkte
            flash(f"Der skete en uventet fejl ved valg af måler. Prøv venligst igen.", 'error')
            session.pop('selected_meter',None);
            return redirect(url_for('select_meter'))
        finally:
            if cursor: cursor.close()
            if conn: safe_close_connection(conn)

    # GET request
    else:
        meters_disp=[]; conn=None; cursor=None
        print(f"DEBUG SELECT_METER GET: Viser ledige målere for {current_user.username}")
        try:
            cfg_meters = get_configured_meters(); # Henter KUN aktive configs
            if not cfg_meters:
                flash(trans['error_no_configured_meters'],'warning')
            else:
                active_meter_ids=set();
                conn=get_db_connection()
                if conn:
                    cursor=conn.cursor(dictionary=True)
                    # Hent ID'er for målere der er aktive for ENHVER bruger
                    cursor.execute('SELECT DISTINCT meter_id FROM active_meters WHERE meter_id IS NOT NULL')
                    active_meter_ids={r['meter_id'] for r in cursor.fetchall()}
                    safe_close_connection(conn); conn = None; cursor = None # Luk hurtigt
                else:
                    flash(trans['error_db_connection'],'error')

                print(f"DEBUG SELECT_METER GET: Aktive måler IDs: {active_meter_ids}")
                available_meters = []
                for m_cfg in cfg_meters:
                    sensor_id = m_cfg['sensor_id']
                    if sensor_id not in active_meter_ids:
                        # Tjek om måleren er online (brug energy sensor hvis sat)
                        sensor_to_read = m_cfg.get('energy_sensor_id') or sensor_id
                        value = get_meter_value(sensor_to_read) # Denne funktion cacher
                        is_online = value is not None and isinstance(value, (int, float))
                        status = trans.get('online', 'Online') if is_online else trans.get('offline', 'Offline')

                        available_meters.append({
                            'id': sensor_id, # ID der skal sendes med form
                            'name': m_cfg.get('display_name') or f"M:{sensor_id}",
                            'location': m_cfg.get('location', ''),
                            'state': status,
                             # Tilføj is_online flag til evt. styling/deaktivering i template
                            'is_online': is_online
                        })
                meters_disp = available_meters
                if not meters_disp and cfg_meters:
                     flash("Alle konfigurerede målere er enten i brug eller offline.", "info")
                elif not meters_disp and not cfg_meters:
                     # Skete allerede i starten
                     pass

        except Error as dbeg: print(f"ERR select_meter GET DB: {dbeg}"); flash(trans['error_db_connection'],'error')
        except Exception as eg: print(f"ERR select_meter GET Gen: {eg}"); flash(f"{trans['error_general']}: {str(eg)}",'error'); traceback.print_exc()
        finally:
            if cursor: cursor.close()
            if conn: safe_close_connection(conn)

        # Ryd session data hvis brugeren lander her igen
        session.pop('selected_meter', None)
        session.pop('pending_purchase', None)
        return render_template('select_meter.html', meters=meters_disp, translations=trans)

@app.route('/select_package', methods=['GET', 'POST'])
@login_required
def select_package():
    lang=session.get('language','da'); trans=translations.get(lang,translations['da'])
    sel_meter = session.get('selected_meter') # Måler valgt i forrige step
    conn=None; cursor=None

    print(f"\n===== START SELECT_PACKAGE (Bruger: {current_user.username}) =====")
    print(f"DEBUG SELECT_PACKAGE Session['selected_meter']: {sel_meter}")

    # Tjek om der ER en valgt måler i sessionen
    if not sel_meter or 'sensor_id' not in sel_meter or 'start_value' not in sel_meter or 'meter_config_id' not in sel_meter:
        print(f"DEBUG SELECT_PACKAGE ERROR: Manglende/ukomplet måler i session. Redirect til select_meter.")
        flash('Du skal vælge en måler først.', 'warning')
        session.pop('selected_meter', None) # Ryd evt. ukomplet data
        session.pop('pending_purchase', None)
        return redirect(url_for('select_meter'))

    # Håndter POST (Når brugeren trykker "Vælg denne pakke")
    if request.method == 'POST':
        package_id = request.form.get('package_id')
        if not package_id:
            flash(trans.get('error_no_package', 'Vælg venligst en pakke.'), 'error')
            return redirect(url_for('select_package'))

        try:
            package_id = int(package_id)
        except ValueError:
            flash(trans.get('error_invalid_package', 'Ugyldigt pakke ID.'), 'error')
            return redirect(url_for('select_package'))

        print(f"DEBUG SELECT_PACKAGE POST: Bruger valgte pakke ID: {package_id}")

        conn = get_db_connection()
        if not conn: flash(trans['error_db_connection'],'error'); return redirect(url_for('select_package'))
        cursor = conn.cursor(dictionary=True)

        try:
            # Hent pakkedetaljer
            cursor.execute('SELECT * FROM stroem_pakker WHERE id=%s AND aktiv=1', (package_id,))
            pkg = cursor.fetchone()
            if not pkg:
                flash(trans.get('error_invalid_package', 'Pakken findes ikke eller er inaktiv.'), 'error')
                raise Exception("Invalid or inactive package")

            # Hent pris og enheder
            package_price = pkg.get('pris')
            package_units = pkg.get('enheder')
            package_name = pkg.get('navn', f'Pakke ID {package_id}')

            # Valider pris og enheder
            if package_price is None or package_units is None:
                 flash('Fejl i pakkedata (mangler pris eller enheder). Kontakt admin.', 'error')
                 raise Exception("Missing price or units in package data")
            try:
                package_price_float = float(package_price)
                package_units_float = float(package_units)
                if package_price_float < 0 or package_units_float <= 0:
                     raise ValueError("Pris kan ikke være negativ, enheder skal være positive.")
            except (ValueError, TypeError) as val_err:
                flash(f'Fejl i pakkedata: {val_err}. Kontakt admin.', 'error')
                raise Exception("Invalid price or units format")

            # Gem valgt pakke og måler i session til bekræftelse/betaling
            session['pending_purchase'] = {
                'meter': sel_meter, # Indeholder id, config_id, display_name, start_value etc.
                'package': {
                    'id': pkg['id'],
                    'navn': package_name,
                    'enheder': package_units_float,
                    'pris': package_price_float # Gem prisen som float
                }
            }
            print(f"DEBUG SELECT_PACKAGE POST: Gemmer i session['pending_purchase']: {session['pending_purchase']}")

            # Gå til bekræftelsessiden
            return redirect(url_for('confirm_purchase'))

        except Error as dbe:
            print(f"ERR select_pkg POST DB: {dbe}"); flash(f"Database Fejl: {dbe}",'error');
        except Exception as e:
            print(f"ERR select_pkg POST Gen: {e}"); flash(f"Generel Fejl: {str(e)}",'error');
        finally:
            if cursor: cursor.close()
            if conn: safe_close_connection(conn)

        # Hvis noget gik galt, redirect tilbage til pakkervalg
        return redirect(url_for('select_package'))

    # GET request (Viser pakker til den valgte måler)
    else:
        pkgs=[]; gtype='Ukendt'; conn=None; cursor=None
        try:
            conn=get_db_connection()
            if conn:
                 cursor=conn.cursor(dictionary=True);
                 # Find gæstetype for at vise korrekte pakker
                 cursor.execute('SELECT plads_type FROM aktive_bookinger WHERE booking_id=%s',(current_user.username,))
                 b=cursor.fetchone();
                 gtype_raw = b.get('plads_type') if b else None
                 # Bestem pakketype baseret på gæstetype
                 if gtype_raw and 'sæson' in gtype_raw.lower():
                      ptype='SAESON'
                      gtype = 'Sæson'
                 else:
                      ptype='DAGS' # Default til Dags/Kørende
                      gtype = 'Dags/Kørende' # Visningstekst

                 print(f"DEBUG SELECT_PACKAGE GET: Gæstetype for {current_user.username}: '{gtype_raw}', Pakketype: '{ptype}'")
                 # Hent relevante pakker
                 cursor.execute("SELECT * FROM stroem_pakker WHERE type=%s AND aktiv=1 ORDER BY enheder, pris",(ptype,));
                 pkgs=cursor.fetchall()
                 if not pkgs:
                      flash(f"Der er desværre ingen aktive '{ptype}' strømpakker tilgængelige i øjeblikket. Kontakt admin.", "warning")

            else: flash(trans['error_db_connection'],'error')
        except Error as dbe: print(f"ERR select_pkg GET DB: {dbe}"); flash(f"DB Fejl: {dbe}",'error')
        except Exception as e: print(f"ERR select_pkg GET Gen: {e}"); flash(f"Fejl: {str(e)}",'error')
        finally:
            if cursor: cursor.close()
            if conn: safe_close_connection(conn)

        # Ryd evt. gammel pending purchase
        session.pop('pending_purchase', None)
        return render_template('select_package.html',
                               packages=pkgs,
                               selected_meter=sel_meter, # Send valgt måler info til view
                               translations=trans,
                               guest_type=gtype)


# --- NYE ROUTES FOR BETALING ---

@app.route('/confirm_purchase')
@login_required
def confirm_purchase():
    """Viser en side hvor brugeren kan bekræfte købet før betaling."""
    lang = session.get('language', 'da')
    trans = translations.get(lang, translations['da'])
    pending = session.get('pending_purchase')

    print(f"DEBUG CONFIRM_PURCHASE: Viser bekræftelse for: {pending}")

    if not pending or 'meter' not in pending or 'package' not in pending:
        flash("Ingen ventende køb fundet. Start venligst forfra ved at vælge en måler.", "warning")
        return redirect(url_for('select_meter'))

    # Hent publicerbar nøgle til frontend (ikke strengt nødvendigt for redirect-baseret Checkout)
    stripe_pub_key, _, _, stripe_mode = get_stripe_keys()
    if not stripe_pub_key:
         flash("Betalingssystemet er ikke konfigureret korrekt (mangler publishable key). Kontakt admin.", "error")
         # Skal vi redirecte? Lad brugeren se fejlen først.
         # return redirect(url_for('index'))

    return render_template('confirm_purchase.html', # DU SKAL LAVE DENNE TEMPLATE
                           purchase_details=pending,
                           stripe_publishable_key=stripe_pub_key,
                           stripe_mode=stripe_mode,
                           translations=trans)


@app.route('/create-checkout-session', methods=['POST'])
@login_required
def create_stripe_checkout():
    """Opretter en Stripe Checkout Session og redirecter brugeren."""
    lang = session.get('language', 'da')
    trans = translations.get(lang, translations['da'])
    pending = session.get('pending_purchase')

    print(f"DEBUG CREATE_CHECKOUT: Forsøger at oprette session for: {pending}")

    if not pending or 'meter' not in pending or 'package' not in pending:
        flash(trans.get('error_general', "Der skete en fejl. Prøv at vælge måler og pakke igen."), "error")
        return redirect(url_for('select_meter'))

    # Hent nøgler igen for at være sikker på de er up-to-date
    _, stripe_secret_key, _, stripe_mode = get_stripe_keys()
    if not stripe_secret_key:
        flash(trans.get('error_payment_config', "Betalingsgateway er ikke konfigureret korrekt. Kontakt admin."), "error")
        return redirect(url_for('confirm_purchase'))
    stripe.api_key = stripe_secret_key

    package = pending['package']
    meter = pending['meter']

    try:
        # Konverter pris til øre (int)
        pris_ore = int(package['pris'] * 100)
        if pris_ore <= 0: # Stripe kræver positivt beløb
             flash("Prisen for pakken er 0 eller negativ. Kan ikke fortsætte. Kontakt admin.", "error")
             return redirect(url_for('confirm_purchase'))

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'dkk', # Eller din valuta
                    'product_data': {
                        'name': f"{package['navn']} ({package['enheder']:.0f} {trans.get('units','enheder')})",
                        'description': f"Til måler: {meter['display_name']} ({meter['sensor_id']})",
                        'metadata': { # Ekstra data knyttet til produktet i Stripe
                            'package_id': package['id'],
                            'meter_sensor_id': meter['sensor_id']
                        }
                    },
                    'unit_amount': pris_ore,
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=url_for('stripe_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('stripe_cancel', _external=True),
            # Gem VIGTIG data til at fuldføre købet efter betaling
            metadata={
                'user_id': current_user.id,
                'username': current_user.username, # booking_id
                'meter_sensor_id': meter['sensor_id'],
                'meter_config_id': meter['meter_config_id'],
                'meter_start_value': str(meter['start_value']), # Skal være string
                'meter_display_name': meter['display_name'], # Til kvittering
                'package_id': package['id'],
                'package_name': package['navn'], # Til kvittering
                'package_units': str(package['enheder']), # Skal være string
                'package_price_paid_ore': str(pris_ore) # Gem hvad der blev betalt
            },
            # Prøv at pre-fill email
            customer_email=current_user.email if current_user.email else None,
            # Locale for checkout page
            locale=lang if lang in ['da', 'en', 'de'] else 'da' # Understøttede Stripe locales
        )
        print(f"INFO: Oprettet Stripe Checkout Session {checkout_session.id} for bruger {current_user.username}")
        # Redirect til Stripe
        return redirect(checkout_session.url, code=303)

    except stripe.error.StripeError as e:
        print(f"ERROR: Stripe API Fejl ved oprettelse af checkout: {e}")
        flash(f"{trans.get('error_creating_payment', 'Fejl ved oprettelse af betalings-session:')} {e.user_message or str(e)}", "error")
    except Exception as e:
        print(f"ERROR: Generel Fejl ved oprettelse af checkout: {e}")
        flash(trans.get('error_general', "Der skete en uventet fejl. Prøv igen."), "error")
        traceback.print_exc()

    # Hvis fejl, gå tilbage til bekræftelsessiden
    return redirect(url_for('confirm_purchase'))

@app.route('/stripe-success')
@login_required
def stripe_success():
    """Callback side efter succesfuld Stripe betaling."""
    lang = session.get('language', 'da')
    trans = translations.get(lang, translations['da'])
    stripe_session_id = request.args.get('session_id')

    print(f"INFO: Stripe Success callback for session {stripe_session_id}, bruger {current_user.username}")

    if not stripe_session_id:
        flash(trans.get('error_verifying_payment', "Fejl: Manglende session ID fra Stripe."), "warning")
        return redirect(url_for('index'))

    try:
        # Hent session fra Stripe API for at verificere
        _, stripe_secret_key, _, _ = get_stripe_keys()
        if not stripe_secret_key: raise Exception("Stripe secret key mangler")
        stripe.api_key = stripe_secret_key
        checkout_session = stripe.checkout.Session.retrieve(stripe_session_id)

        # Kald fælles funktion til at behandle ordren
        success, message = fulfill_order(checkout_session)

        if success:
            flash(message or trans.get('payment_successful', "Betaling gennemført! Din pakke er aktiveret."), 'success')
            # Ryd session data relateret til dette køb
            session.pop('pending_purchase', None)
            session.pop('selected_meter', None)
            return redirect(url_for('stroem_dashboard'))
        else:
            flash(message or trans.get('error_activating_package', "Betaling modtaget, men fejl ved aktivering af pakke. Kontakt admin."), 'danger')
            # Behøver vi rydde session her? Måske ikke hvis aktivering fejlede.
            return redirect(url_for('index')) # Gå til index ved fejl

    except stripe.error.StripeError as e:
        print(f"ERROR: Stripe API Fejl ved hentning af success session {stripe_session_id}: {e}")
        flash(f"{trans.get('error_verifying_payment', 'Fejl ved verificering af betaling:')} {e.user_message or str(e)}", "error")
    except Exception as e:
        print(f"ERROR: Generel Fejl i stripe_success for session {stripe_session_id}: {e}")
        flash(trans.get('error_general', "Der skete en uventet fejl under behandling af betaling."), "error")
        traceback.print_exc()

    # Gå til index ved fejl
    return redirect(url_for('index'))


@app.route('/stripe-cancel')
@login_required
def stripe_cancel():
    """Callback side hvis brugeren annullerer Stripe betaling."""
    lang = session.get('language', 'da')
    trans = translations.get(lang, translations['da'])
    print(f"INFO: Stripe Cancel callback for bruger {current_user.username}")
    flash(trans.get('payment_canceled', "Betaling annulleret. Du er ikke blevet opkrævet."), 'info')
    # Ryd session data
    session.pop('pending_purchase', None)
    session.pop('selected_meter', None)
    return redirect(url_for('select_package')) # Gå tilbage til pakkervalg


@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    """
    Endpoint til at modtage events fra Stripe (f.eks. checkout.session.completed).
    Dette er den mest robuste måde at håndtere ordrefuldførelse.
    """
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    # Hent den korrekte webhook secret baseret på mode
    _, _, webhook_secret, mode = get_stripe_keys()

    print(f"INFO: Stripe Webhook modtaget ({request.content_length} bytes), mode: {mode}")

    if not webhook_secret:
        print("ERROR: Stripe Webhook Secret er ikke konfigureret!")
        return jsonify(error="Webhook secret mangler"), 500 # Intern fejl

    event = None
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
        print(f"INFO: Stripe Webhook event type: {event['type']}")
    except ValueError as e:
        # Ugyldig payload
        print(f"ERROR: Stripe Webhook - Ugyldig payload: {e}")
        return jsonify(error="Invalid payload"), 400
    except stripe.error.SignatureVerificationError as e:
        # Ugyldig signatur
        print(f"ERROR: Stripe Webhook - Ugyldig signatur: {e}")
        return jsonify(error="Invalid signature"), 400
    except Exception as e:
        print(f"ERROR: Stripe Webhook - Fejl ved construct_event: {e}")
        return jsonify(error="Webhook construction error"), 500

    # Håndter checkout.session.completed event
    if event['type'] == 'checkout.session.completed':
        checkout_session = event['data']['object']
        print(f"INFO: Webhook - Behandler checkout.session.completed for ID: {checkout_session.id}")

        # Kald den fælles funktion til at fuldføre ordren
        success, message = fulfill_order(checkout_session)

        if success:
            print(f"INFO: Webhook - Ordre {checkout_session.id} fuldført succesfuldt.")
        else:
            print(f"WARN: Webhook - Fejl eller allerede behandlet for ordre {checkout_session.id}: {message}")
            # Returner 200 OK selvom vi ikke gjorde noget (f.eks. hvis allerede behandlet)
            # for at undgå at Stripe sender webhooken igen.
            # Hvis det var en reel fejl, er den logget i fulfill_order.

    elif event['type'] == 'payment_intent.succeeded':
         payment_intent = event['data']['object']
         print(f"INFO: Webhook - Modtog payment_intent.succeeded: {payment_intent.id}")
         # Du kan evt. logge dette, men checkout.session.completed er typisk nok.

    # Tilføj andre events du vil lytte til her (f.eks. payment_intent.payment_failed)

    else:
        print(f"WARN: Webhook - Ubehandlet event type: {event['type']}")

    # Fortæl Stripe at vi har modtaget og behandlet (eller ignoreret) eventet
    return jsonify(success=True)


# --- FÆLLES FUNKTION TIL AT FULDFØRE ORDREN ---

def fulfill_order(checkout_session):
    """
    Behandler en succesfuld Stripe Checkout Session.
    Aktiverer måler, logger køb, sender kvittering.
    Returnerer (bool: success, str: message).
    Denne funktion SKAL være idempotent (kunne kaldes flere gange for samme session uden sideeffekter).
    """
    stripe_session_id = checkout_session.id
    print(f"DEBUG fulfill_order: Starter behandling for Stripe session {stripe_session_id}")

    # 1. Tjek betalingsstatus
    if checkout_session.payment_status != "paid":
        print(f"WARN fulfill_order: Session {stripe_session_id} er ikke 'paid', status er '{checkout_session.payment_status}'. Ignorerer.")
        return False, "Betaling ikke gennemført."

    # 2. Hent metadata
    metadata = checkout_session.metadata
    if not metadata:
        print(f"ERROR fulfill_order: Ingen metadata fundet for session {stripe_session_id}!")
        # Notificer admin - dette bør ikke ske!
        return False, "Kritisk fejl: Manglende metadata fra Stripe."

    try:
        user_id = int(metadata.get('user_id'))
        username = metadata.get('username') # booking_id
        meter_sensor_id = metadata.get('meter_sensor_id')
        meter_config_id = int(metadata.get('meter_config_id'))
        meter_start_value = float(metadata.get('meter_start_value'))
        meter_display_name = metadata.get('meter_display_name', meter_sensor_id) # Til kvittering
        package_id = int(metadata.get('package_id'))
        package_name = metadata.get('package_name', f'Pakke {package_id}') # Til kvittering
        package_units = float(metadata.get('package_units'))
        price_paid_ore = int(metadata.get('package_price_paid_ore'))
    except (TypeError, ValueError, KeyError) as e:
        print(f"ERROR fulfill_order: Ugyldig eller manglende metadata for session {stripe_session_id}: {e}")
        print(f"Metadata modtaget: {metadata}")
        return False, "Fejl i data modtaget fra Stripe."

    print(f"DEBUG fulfill_order: Metadata OK for {stripe_session_id}. Bruger: {username}, Måler: {meter_sensor_id}, Pakke: {package_id}")

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn: raise Error("DB connection failed")
        conn.start_transaction()
        cursor = conn.cursor(dictionary=True) # Brug dict cursor til SELECT

        # 3. IDEMPOTENS CHECK: Er denne Stripe session allerede behandlet?
        #    Antager 'stripe_checkout_session_id' er UNIQUE i 'stroem_koeb'
        cursor.execute("SELECT id FROM stroem_koeb WHERE stripe_checkout_session_id = %s", (stripe_session_id,))
        existing_purchase = cursor.fetchone()
        if existing_purchase:
            print(f"INFO fulfill_order: Stripe session {stripe_session_id} er allerede behandlet (stroem_koeb ID: {existing_purchase['id']}). Ignorerer.")
            # Vigtigt at returnere True her, så webhook ikke fejler og prøver igen.
            return True, "Køb allerede behandlet."

        # 4. Tjek om måleren blev taget af en anden i mellemtiden
        cursor.execute("SELECT booking_id FROM active_meters WHERE meter_id = %s AND booking_id != %s", (meter_sensor_id, username))
        meter_taken = cursor.fetchone()
        if meter_taken:
             print(f"ERROR fulfill_order: Måler {meter_sensor_id} blev taget af booking {meter_taken['booking_id']} mens bruger {username} betalte (Session: {stripe_session_id}).")
             # Hvad skal ske her? Refundering? Notificer admin!
             conn.rollback() # Annuller alt
             # Send mail til admin?
             # Send mail til brugeren?
             return False, f"Måleren ({meter_display_name}) blev desværre optaget af en anden bruger under betalingen. Købet er annulleret. Kontakt venligst support."

        # 5. Aktiver måler/pakke (INSERT eller UPDATE active_meters)
        std_cursor = conn.cursor() # Standard cursor til INSERT/UPDATE
        std_cursor.execute("SELECT id, package_size FROM active_meters WHERE booking_id=%s", (username,))
        existing_active_meter = std_cursor.fetchone() # Bruger standard cursor, får tuple

        if existing_active_meter:
            # Bruger har allerede en aktiv måler (måske en anden? Eller køber tillæg?)
            # For nu antager vi, at det er et tillæg til den eksisterende forbindelse.
            # Vi opdaterer KUN package_size.
            # OBS: Hvis brugeren valgte en *anden* måler end den aktive, har vi et problem!
            # Denne logik bør raffineres baseret på forretningsregler.
            # For nu: Læg enheder til eksisterende.
            existing_active_id = existing_active_meter[0]
            current_package_size = float(existing_active_meter[1] if existing_active_meter[1] else 0.0)
            new_package_size = current_package_size + package_units
            print(f"DEBUG fulfill_order: Opdaterer eksisterende active_meter ID {existing_active_id} for {username}. Gammel size={current_package_size}, Ny size={new_package_size}")
            # VI OPPDATERER IKKE meter_id eller start_value her, kun size
            std_cursor.execute("UPDATE active_meters SET package_size=%s WHERE id=%s", (new_package_size, existing_active_id))
        else:
            # Ny aktiv måler for brugeren
            print(f"DEBUG fulfill_order: Indsætter ny active_meter for {username}. Måler={meter_sensor_id}, Start={meter_start_value}, Size={package_units}")
            sql_insert_active = """
                INSERT INTO active_meters (booking_id, meter_id, start_value, package_size, created_at)
                VALUES (%s, %s, %s, %s, NOW())
            """
            std_cursor.execute(sql_insert_active, (username, meter_sensor_id, meter_start_value, package_units))

        # 6. Log købet i stroem_koeb (eller payments tabel)
        #    Antager tabel har: booking_id, pakke_id, maaler_id (config_id), enheder_tilbage, pris_betalt_ore, koebs_tidspunkt, stripe_checkout_session_id
        sql_insert_log = """
            INSERT INTO stroem_koeb (booking_id, pakke_id, maaler_id, enheder_tilbage, pris_betalt_ore, koebs_tidspunkt, stripe_checkout_session_id)
            VALUES (%s, %s, %s, %s, %s, NOW(), %s)
        """
        std_cursor.execute(sql_insert_log, (username, package_id, meter_config_id, package_units, price_paid_ore, stripe_session_id))
        purchase_log_id = std_cursor.lastrowid
        print(f"DEBUG fulfill_order: Køb logget i stroem_koeb ID: {purchase_log_id} for Stripe session {stripe_session_id}")
        std_cursor.close()

        # 7. Hent brugerens email til kvittering
        cursor.execute("SELECT email, fornavn, efternavn FROM users WHERE id=%s", (user_id,))
        user_info = cursor.fetchone()
        user_email = user_info.get('email') if user_info else None
        user_name = f"{user_info.get('fornavn','')} {user_info.get('efternavn','')}".strip() if user_info else username

        # 8. Tænd for strømmen (hvis måleren har en switch)
        cursor.execute("SELECT power_switch_id FROM meter_config WHERE id=%s", (meter_config_id,))
        meter_cfg = cursor.fetchone()
        power_switch_id = meter_cfg.get('power_switch_id') if meter_cfg else None
        if not power_switch_id and meter_sensor_id.startswith('sensor.'): # Gæt hvis ikke sat
            base = meter_sensor_id.split('.')[1].split('_')[0]; power_switch_id = f"switch.{base}_0"

        if power_switch_id and HASS_URL and HASS_TOKEN:
             try:
                 print(f"DEBUG fulfill_order: Forsøger at tænde switch {power_switch_id} for {meter_sensor_id} (Session: {stripe_session_id})")
                 # Tjek først om den allerede er tændt?
                 current_switch_state = get_switch_state(power_switch_id)
                 if current_switch_state == 'off':
                     resp = requests.post(
                         f"{HASS_URL}/api/services/switch/turn_on",
                         headers={"Authorization": f"Bearer {HASS_TOKEN}"},
                         json={"entity_id": power_switch_id},
                         timeout=10
                     )
                     if resp.status_code == 200:
                         print(f"INFO fulfill_order: Tændte switch {power_switch_id}.")
                     else:
                         print(f"WARN fulfill_order: Kunne ikke tænde switch {power_switch_id} (status {resp.status_code}).")
                         # Skal købet rulles tilbage? Nok ikke, men log det tydeligt.
                 elif current_switch_state == 'on':
                      print(f"DEBUG fulfill_order: Switch {power_switch_id} var allerede tændt.")
                 else:
                      print(f"WARN fulfill_order: Kunne ikke bestemme status for switch {power_switch_id} ({current_switch_state}). Kan ikke tænde automatisk.")

             except Exception as swe:
                 print(f"ERROR fulfill_order: Fejl ved tænding af switch {power_switch_id}: {swe}")
                 # Log, men fortsæt - måske HASS er nede.

        # 9. Commit DB transaktion
        conn.commit()
        print(f"INFO fulfill_order: DB transaktion committet for session {stripe_session_id}.")

        # 10. Send kvittering (efter commit)
        if user_email:
            try:
                price_dkk = price_paid_ore / 100.0
                # Brug Decimal for præcis prisvisning hvis nødvendigt
                # price_dkk_decimal = Decimal(price_paid_ore) / 100
                send_purchase_receipt(
                    user_email=user_email,
                    user_name=user_name,
                    package_name=package_name,
                    package_units=package_units,
                    price_dkk=price_dkk, # Send som float
                    purchase_time=datetime.now(), # Brug ca. nuværende tidspunkt
                    meter_display_name=meter_display_name
                )
            except Exception as mail_e:
                # Log mail fejl, men ordren er stadig fuldført
                print(f"ERROR fulfill_order: Kunne ikke sende kvittering til {user_email} for session {stripe_session_id}: {mail_e}")
        else:
            print(f"WARN fulfill_order: Ingen email fundet for bruger {username} (ID: {user_id}). Kan ikke sende kvittering for session {stripe_session_id}.")

        return True, "Betaling gennemført og pakke aktiveret."

    except Error as dbe:
        print(f"FATAL fulfill_order DB Error for session {stripe_session_id}: {dbe}")
        if conn: conn.rollback()
        traceback.print_exc()
        return False, "Databasefejl under behandling af køb."
    except Exception as e:
        print(f"FATAL fulfill_order General Error for session {stripe_session_id}: {e}")
        if conn: conn.rollback()
        traceback.print_exc()
        return False, "Generel fejl under behandling af køb."
    finally:
        if 'std_cursor' in locals() and std_cursor: std_cursor.close()
        if cursor: cursor.close()
        if conn: safe_close_connection(conn)


# --- EMAIL FUNKTIONER ---

def send_purchase_receipt(user_email, user_name, package_name, package_units, price_dkk, purchase_time, meter_display_name):
    """Sender en købskvittering til brugeren."""
    lang = session.get('language', 'da') # Prøv at få sprog fra session hvis muligt
    trans = translations.get(lang, translations['da'])
    settings = get_system_settings()
    sender_email = settings.get('receipt_sender_email') # Hentes fra DB/env

    if not sender_email:
        print("ERROR send_purchase_receipt: Afsender email (receipt_sender_email) er ikke konfigureret.")
        return # Kan ikke sende uden afsender

    if not user_email:
        print(f"WARN send_purchase_receipt: Modtager email mangler for bruger '{user_name}'. Kan ikke sende kvittering.")
        return

    subject = trans.get('receipt_subject', "Kvittering for dit strømkøb") + f": {package_name}"
    # Brug render_template for HTML email hvis du laver en template
    # html_body = render_template('emails/receipt.html', ...)
    text_body = f"""
{trans.get('hello', 'Hej')} {user_name},

{trans.get('receipt_intro', 'Tak for dit køb!')}

{trans.get('package', 'Pakke')}: {package_name}
{trans.get('units', 'Enheder')}: {package_units:.1f}
{trans.get('meter', 'Måler')}: {meter_display_name}
{trans.get('price', 'Pris')}: {price_dkk:.2f} DKK
{trans.get('time', 'Købstidspunkt')}: {purchase_time.strftime(settings.get('timestamp_format', '%Y-%m-%d %H:%M:%S'))}

{trans.get('receipt_outro', 'Du kan nu se dit forbrug på dit dashboard.')}

{trans.get('regards', 'Med venlig hilsen')},
{settings.get('company_name', '[Dit Firmanavn]')}
"""
    msg = Message(subject=subject,
                  recipients=[user_email],
                  body=text_body,
                  # html=html_body, # Aktiver hvis du bruger HTML template
                  sender=(settings.get('company_name', 'Strømsystem'), sender_email)) # Vis navn + email

    try:
        # Sikrer at mail konfigurationen er opdateret før afsendelse
        # update_mail_config() # Måske ikke nødvendigt hvis den kun ændres sjældent
        mail.send(msg)
        print(f"INFO: Kvittering sendt til {user_email} for pakke {package_name}")
    except Exception as e:
        print(f"ERROR: Kunne ikke sende kvittering til {user_email}: {e}")
        traceback.print_exc()
        # Log fejlen, men processen fortsætter

def send_daily_sales_report():
    """Sender en daglig rapport med omsætning til admin."""
    print(f"BG JOB: Daily Sales Report Start - {datetime.now()}")
    settings = get_system_settings()
    admin_email = settings.get('admin_report_email')
    sender_email = settings.get('receipt_sender_email')
    company_name = settings.get('company_name', '[Dit Firmanavn]')
    lang = 'da' # Rapport er typisk på dansk?
    trans = translations.get(lang, translations['da'])

    if not admin_email:
        print("WARN: Daily Sales - Admin report email ikke konfigureret.")
        return
    if not sender_email:
        print("WARN: Daily Sales - Afsender email (receipt_sender_email) ikke konfigureret.")
        return # Kan ikke sende uden afsender

    conn = None; cursor = None
    try:
        conn = get_db_connection()
        if not conn: raise Error("DB connection failed for daily report")
        cursor = conn.cursor(dictionary=True)

        # Find køb siden midnat i går (hele gårsdagens salg)
        # Eller de sidste 24 timer? For nu: Sidste 24 timer.
        start_time = datetime.now() - timedelta(hours=24)
        # For gårsdagen:
        # end_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        # start_time = end_time - timedelta(days=1)

        # **VIGTIGT:** Antager 'stroem_koeb' har 'pris_betalt_ore' og 'koebs_tidspunkt'
        # og at 'maaler_id' peger på 'meter_config.id' (for at få navn)
        query = """
            SELECT sk.booking_id, sk.pris_betalt_ore, sk.koebs_tidspunkt,
                   sp.navn as package_name,
                   mc.display_name as meter_name
            FROM stroem_koeb sk
            LEFT JOIN stroem_pakker sp ON sk.pakke_id = sp.id
            LEFT JOIN meter_config mc ON sk.maaler_id = mc.id
            WHERE sk.koebs_tidspunkt >= %s
              AND sk.pris_betalt_ore > 0  -- Inkluder kun faktiske salg
            ORDER BY sk.koebs_tidspunkt DESC
        """
        cursor.execute(query, (start_time,))
        sales = cursor.fetchall()

        if not sales:
            print("INFO: Daily Sales - Ingen salg fundet i perioden.")
            # Send mail selvom der ikke er salg? For nu: Nej.
            return

        total_revenue_ore = sum(s['pris_betalt_ore'] for s in sales if s.get('pris_betalt_ore'))
        total_revenue_dkk = total_revenue_ore / 100.0

        if total_revenue_dkk <= 0:
             print("INFO: Daily Sales - Ingen omsætning i perioden.")
             return

        # Formater rapport
        subject = f"{trans.get('daily_sales_report', 'Daglig Omsætningsrapport')} - {datetime.now().strftime('%Y-%m-%d')}"
        # Brug render_template hvis du har en HTML template
        # html_body = render_template('emails/daily_report.html', ...)
        text_body = f"{trans.get('sales_report_for', 'Omsætningsrapport for perioden')} {start_time.strftime('%Y-%m-%d %H:%M')} - {datetime.now().strftime('%Y-%m-%d %H:%M')}:\n\n"
        text_body += f"{trans.get('total_revenue', 'Total Omsætning')}: {total_revenue_dkk:.2f} DKK\n"
        text_body += f"{trans.get('number_of_sales', 'Antal Salg')}: {len(sales)}\n\n"
        text_body += f"{trans.get('details', 'Detaljer')}:\n"

        for sale in sales:
             tid = sale.get('koebs_tidspunkt', datetime.min).strftime('%H:%M:%S')
             pris_dkk = (sale.get('pris_betalt_ore', 0) or 0) / 100.0
             text_body += f"- Kl {tid}: {sale.get('booking_id','Ukendt')} | {sale.get('package_name','Ukendt Pakke')} | Måler: {sale.get('meter_name','Ukendt')} | {pris_dkk:.2f} DKK\n"

        msg = Message(subject=subject,
                      recipients=[admin_email], # Send til admin
                      body=text_body,
                      # html=html_body,
                      sender=(company_name, sender_email))
        mail.send(msg)
        print(f"INFO: Daily Sales - Rapport sendt til {admin_email}. Omsætning: {total_revenue_dkk:.2f} DKK")

    except Error as dbe: print(f"FATAL: Daily Sales DB Error: {dbe}"); traceback.print_exc()
    except Exception as e: print(f"FATAL: Daily Sales General Error: {e}"); traceback.print_exc()
    finally:
        if cursor: cursor.close()
        if conn: safe_close_connection(conn)


# --- Toggle Power (Uændret i sin kerne, men tjek logning) ---
@app.route('/toggle_power', methods=['POST'])
@login_required
def toggle_power():
    # ... (samme logik som før for at finde switch og kalde HASS) ...
    lang=session.get('language','da'); trans=translations.get(lang,translations['da']); action=request.form.get('action'); switch_id=request.form.get('switch_id'); conn=None; cursor=None; meter_display_name="Ukendt"; meter_id=None
    print(f"DEBUG toggle_power: Act={action}, SwID={switch_id}, User={current_user.username}")
    if not action or action not in ['on','off']: flash('Ugyldig handling.','error'); return redirect(url_for('stroem_dashboard'))
    if not switch_id: flash('Mangler switch ID.','error'); return redirect(url_for('stroem_dashboard'))
    if not HASS_URL or not HASS_TOKEN: flash('Home Assistant er ikke konfigureret. Kan ikke styre strøm.','error'); return redirect(url_for('stroem_dashboard'))

    try:
        # Find måler og switch tilknyttet brugeren
        conn=get_db_connection()
        if not conn: raise Error("DB connection failed")
        cursor=conn.cursor(dictionary=True)
        # Find den aktive måler for brugeren og dens konfiguration
        cursor.execute("""
            SELECT am.meter_id, mc.power_switch_id, mc.display_name
            FROM active_meters am
            JOIN meter_config mc ON am.meter_id = mc.sensor_id
            WHERE am.booking_id=%s
            LIMIT 1
        """,(current_user.username,))
        active_meter_cfg = cursor.fetchone()
        safe_close_connection(conn); conn = None; cursor = None # Luk DB

        found_switch_for_user = False
        target_switch_id = None

        if active_meter_cfg:
            meter_id = active_meter_cfg['meter_id']
            meter_display_name = active_meter_cfg.get('display_name', meter_id)
            target_switch_id = active_meter_cfg.get('power_switch_id')
            # Gæt hvis ikke fundet
            if not target_switch_id and meter_id.startswith('sensor.'):
                base=meter_id.split('.')[1].split('_')[0]; target_switch_id=f"switch.{base}_0"

            if target_switch_id == switch_id: # Tjek at den switch de poster til, er den de ejer
                 found_switch_for_user = True

        if not found_switch_for_user:
            flash('Du har ikke adgang til at styre denne kontakt, eller den er ikke korrekt tilknyttet din måler.','error')
            return redirect(url_for('stroem_dashboard'))

        # Tjek nuværende state og udfør handling
        current_state = get_switch_state(target_switch_id)
        print(f"DEBUG toggle: Switch state {target_switch_id}: {current_state}")

        if current_state in ['unavailable','unknown']:
            flash(f"Kan ikke styre strøm: Kontakten ({target_switch_id}) er utilgængelig i Home Assistant.","error")
            return redirect(url_for('stroem_dashboard'))

        service = "turn_on" if action == "on" else "turn_off"
        desired_state = "on" if action == "on" else "off"

        if current_state == desired_state:
            flash(f'Strømmen for "{meter_display_name}" er allerede {action}.','info')
            return redirect(url_for('stroem_dashboard'))

        # Kald HASS API
        api_url = f"{HASS_URL}/api/services/switch/{service}"
        headers = {"Authorization": f"Bearer {HASS_TOKEN}", "Content-Type": "application/json"}
        payload = {"entity_id": target_switch_id}
        resp = requests.post(api_url, headers=headers, json=payload, timeout=10)

        if resp.status_code == 200:
            action_text = trans.get('turned_on', 'tændt') if action == 'on' else trans.get('turned_off', 'slukket')
            flash(f'Strømmen for måler "{meter_display_name}" er nu {action_text}.','success')

            # Log handlingen i power_events (Uændret logik, men sikrer den virker)
            conn_log=get_db_connection()
            if conn_log:
                lcur=conn_log.cursor(); user_id_int=None
                try: user_id_int = int(current_user.id)
                except: pass # Burde ikke ske for logget ind bruger
                try:
                    sql_log = """
                        INSERT INTO power_events (user_id, event_type, meter_id, details, event_timestamp)
                        VALUES (%s, %s, %s, %s, NOW())
                    """
                    event_type = f"manual_power_{action}"
                    details = f"Bruger {current_user.username} satte {action_text} for {target_switch_id}"
                    lcur.execute(sql_log,(user_id_int, event_type, meter_id, details))
                    conn_log.commit()
                    print(f"INFO toggle: Logget event '{event_type}' for bruger {user_id_int}, måler {meter_id}")
                except Error as loge: print(f"ERR toggle log DB: {loge}"); conn_log.rollback()
                except Exception as logge: print(f"ERR toggle log Gen: {logge}"); conn_log.rollback()
                finally:
                    if lcur: lcur.close()
                    safe_close_connection(conn_log)
            else: print("ERR toggle log: DB connection failed.")

        else: # HASS API kald fejlede
            flash(f'Fejl ({resp.status_code}) ved kommunikation med Home Assistant. Kunne ikke ændre strømstatus.','error');
            print(f"ERR toggle HA API Call: {resp.status_code} - {resp.text}")

    except Error as dbe: print(f"ERR toggle DB: {dbe}"); flash('Database fejl under strømstyring.','error')
    except requests.exceptions.RequestException as reqe: print(f"ERR toggle HA Request: {reqe}"); flash(f'Netværksfejl til Home Assistant: {reqe}','error')
    except Exception as e: print(f"ERR toggle Gen: {e}"); flash(f'Generel Fejl: {str(e)}','error'); traceback.print_exc()
    finally:
        if cursor: cursor.close()
        if conn: safe_close_connection(conn)

    return redirect(url_for('stroem_dashboard'))


# --- API endpoints til admin dashboard (uændret) ---
@app.route('/systemkontrolcenter23/get-meter', methods=['GET'])
@admin_required
def get_meter():
    # ... (uændret) ...
    booking_id = request.args.get('booking_id')
    if not booking_id: return jsonify({"success": False, "message": "Booking ID mangler"}), 400
    conn = None; cursor = None
    try:
        conn = get_db_connection()
        if not conn: return jsonify({"success": False, "message": "Databaseforbindelsesfejl"}), 500
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT am.meter_id, mc.display_name as name
            FROM active_meters am
            LEFT JOIN meter_config mc ON am.meter_id = mc.sensor_id
            WHERE am.booking_id = %s LIMIT 1
        """, (booking_id,))
        meter = cursor.fetchone()
        if meter: return jsonify({"success": True, "meter": meter})
        else: return jsonify({"success": False, "message": "Ingen måler fundet for denne booking"}), 404
    except Error as e: print(f"ERR get_meter DB: {e}"); return jsonify({"success": False, "message": f"Databasefejl: {str(e)}"}), 500
    except Exception as e: print(f"ERR get_meter Gen: {e}"); return jsonify({"success": False, "message": f"Fejl: {str(e)}"}), 500
    finally:
        if cursor: cursor.close()
        if conn: safe_close_connection(conn)

@app.route('/systemkontrolcenter23/get-map', methods=['GET'])
@admin_required
def get_map():
    # ... (uændret - returnerer stadig tom data) ...
    return jsonify({"success": True, "data": {}}), 200

@app.route('/systemkontrolcenter23/get-user-meters', methods=['GET'])
@admin_required
def get_user_meters():
    # ... (uændret) ...
    booking_id = request.args.get('booking_id')
    if not booking_id: return jsonify({"success": False, "message": "Booking ID mangler"}), 400
    conn = None; cursor = None
    try:
        conn = get_db_connection()
        if not conn: return jsonify({"success": False, "message": "Databaseforbindelsesfejl"}), 500
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT am.meter_id, mc.display_name as name, mc.location
            FROM active_meters am
            LEFT JOIN meter_config mc ON am.meter_id = mc.sensor_id
            WHERE am.booking_id = %s
        """, (booking_id,))
        meters = cursor.fetchall()
        return jsonify({"success": True, "meters": meters})
    except Error as e: print(f"ERR get_user_meters DB: {e}"); return jsonify({"success": False, "message": f"Databasefejl: {str(e)}"}), 500
    except Exception as e: print(f"ERR get_user_meters Gen: {e}"); return jsonify({"success": False, "message": f"Fejl: {str(e)}"}), 500
    finally:
        if cursor: cursor.close()
        if conn: safe_close_connection(conn)

@app.route('/systemkontrolcenter23/get-available-meters', methods=['GET'])
@admin_required
def get_available_meters():
    # ... (uændret) ...
    # Note: Denne overlapper med '/systemkontrolcenter23/get-available-meters' defineret tidligere.
    # Flask vil bruge den sidst definerede. Sørg for at navngive dem unikt hvis de skal noget forskelligt.
    conn = None; cursor = None
    try:
        conn = get_db_connection()
        if not conn: return jsonify({"success": False, "message": "Databaseforbindelsesfejl"}), 500
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT mc.sensor_id as meter_id, mc.display_name as name, mc.location
            FROM meter_config mc
            WHERE mc.is_active = 1
            AND mc.sensor_id NOT IN (SELECT DISTINCT meter_id FROM active_meters WHERE meter_id IS NOT NULL)
            ORDER BY mc.display_name
        """)
        available_meters = cursor.fetchall()
        # Tilføj online status?
        meters_with_status = []
        for meter in available_meters:
             sensor_to_read = meter['meter_id'] # Antag vi læser hovedsensor for status her
             # Måske hente energy_sensor_id hvis vi vil være mere præcise?
             # cursor.execute("SELECT energy_sensor_id FROM meter_config WHERE sensor_id=%s", (meter['meter_id'],))
             # cfg = cursor.fetchone()
             # if cfg and cfg.get('energy_sensor_id'): sensor_to_read = cfg['energy_sensor_id']
             value = get_meter_value(sensor_to_read)
             meter['is_online'] = value is not None and isinstance(value, (int, float))
             meters_with_status.append(meter)

        return jsonify({"success": True, "meters": meters_with_status}) # Returner med status
    except Error as e: print(f"ERR get_available_meters API DB: {e}"); return jsonify({"success": False, "message": f"Databasefejl: {str(e)}"}), 500
    except Exception as e: print(f"ERR get_available_meters API Gen: {e}"); return jsonify({"success": False, "message": f"Fejl: {str(e)}"}), 500
    finally:
        if cursor: cursor.close()
        if conn: safe_close_connection(conn)

# --- Baggrundsjobs ---
# ... (check_package_status og check_and_remove_inactive_users - uændret i kerne, men tjek logs) ...
def check_package_status():
    # Denne funktion slukker for strømmen hvis pakken er tom.
    # Den bør stadig virke som før. Tjek om logning til power_events er korrekt.
    print(f"BG JOB: Check Package Status Start - {datetime.now()}"); conn=None; cursor=None
    if not HASS_URL or not HASS_TOKEN: print("ERR check_pkg: No HASS config."); return
    try:
        conn=get_db_connection();
        if not conn: print("ERR check_pkg: DB fail."); return
        cursor=conn.cursor(dictionary=True);
        # Hent aktive målere, deres config (for switch), og bruger ID (for logning)
        cursor.execute("""
            SELECT am.id as active_meter_id, am.meter_id, am.start_value, am.package_size, am.booking_id,
                   u.id as user_id,
                   mc.power_switch_id, mc.energy_sensor_id
            FROM active_meters am
            JOIN users u ON am.booking_id = u.username
            LEFT JOIN meter_config mc ON am.meter_id = mc.sensor_id
            WHERE am.meter_id IS NOT NULL AND am.package_size > 0
        """)
        active_meters=cursor.fetchall();

        if not active_meters:
            # print("DEBUG check_pkg: Ingen aktive målere fundet.") # Mindre støj
            return

        for m in active_meters:
             meter_id=m['meter_id']; booking_id=m['booking_id']; user_id=m['user_id']
             sensor_to_read = m.get('energy_sensor_id') or meter_id # Læs fra korrekt sensor

             try:
                 current_value=get_meter_value(sensor_to_read);
                 if current_value is None:
                      print(f"WARN check_pkg: Kunne ikke læse værdi fra {sensor_to_read} for {booking_id}. Skipper tjek."); continue

                 start_val = float(m.get('start_value', 0.0))
                 package_sz = float(m.get('package_size', 0.0))
                 usage = current_value - start_val

                 # Håndter måler reset
                 if usage < -0.01: # Tillad lille afvigelse
                     print(f"WARN check_pkg: Negativt forbrug ({usage:.3f}) for {meter_id} ({booking_id}). Behandler som 0.")
                     usage = 0

                 remaining = package_sz - usage

                 # Tjek om pakken er tom (med lille buffer for float unøjagtighed)
                 if remaining <= 0.01:
                      print(f"INFO check_pkg: Pakke tom for {meter_id} ({booking_id}). Forbrug: {usage:.3f}, Pakke: {package_sz:.3f}. Resterende: {remaining:.3f}. Forsøger at slukke.")

                      psid=m.get('power_switch_id');
                      if not psid and meter_id.startswith('sensor.'): # Gæt switch
                          base=meter_id.split('.')[1].split('_')[0]; psid=f"switch.{base}_0"

                      if not psid:
                           print(f"WARN check_pkg: Ingen switch ID fundet/gættet for {meter_id}. Kan ikke slukke automatisk."); continue

                      try: # Forsøg at slukke
                           current_switch_state = get_switch_state(psid)
                           if current_switch_state == 'on':
                               print(f"DEBUG check_pkg: Switch {psid} er 'on', sender turn_off...")
                               pr=requests.post(f"{HASS_URL}/api/services/switch/turn_off", headers={"Authorization":f"Bearer {HASS_TOKEN}"}, json={"entity_id":psid}, timeout=10)
                               if pr.status_code==200:
                                    print(f"SUCCESS check_pkg: Slukkede switch {psid} for tom pakke ({booking_id}).")
                                    try: # Log handlingen
                                        lcur = conn.cursor()
                                        sql_log = """
                                            INSERT INTO power_events (user_id, event_type, meter_id, details, event_timestamp)
                                            VALUES (%s, %s, %s, %s, NOW())
                                        """
                                        details = f"Auto Power Off: Pakke tom. Forbrug: {usage:.3f}, Pakke: {package_sz:.3f}"
                                        lcur.execute(sql_log, (user_id, 'auto_power_off_empty', meter_id, details));
                                        conn.commit() # Commit kun loggen her
                                        lcur.close()
                                    except Error as loge: print(f"WARN check_pkg log DB: {loge}"); conn.rollback() # Rul log tilbage ved fejl
                                    except Exception as logge: print(f"WARN check_pkg log Gen: {logge}"); conn.rollback()
                                else: # HASS kald fejlede
                                     print(f"ERR check_pkg: Kunne ikke slukke switch {psid} via HASS (status {pr.status_code}).")
                           elif current_switch_state == 'off':
                               print(f"DEBUG check_pkg: Switch {psid} var allerede slukket for {booking_id}.")
                           else: # unavailable/unknown
                                print(f"WARN check_pkg: Switch {psid} status er '{current_switch_state}'. Kan ikke slukke automatisk.")

                      except Exception as swe: print(f"ERR check_pkg: Fejl ved håndtering af switch {psid}: {swe}")
                 # else: print(f"DEBUG check_pkg: OK for {meter_id} ({booking_id}). Resterende: {remaining:.3f}") # For meget støj

             except (ValueError, TypeError) as ve:
                 print(f"ERR check_pkg: Ugyldig start/pakke værdi for {meter_id} ({booking_id}): {ve}")
             except Exception as me:
                 print(f"ERR check_pkg: Generel fejl ved behandling af måler {meter_id} ({booking_id}): {me}")

    except Error as dbe: print(f"FATAL check_pkg DB: {dbe}")
    except Exception as e: print(f"FATAL check_pkg Gen: {e}"); traceback.print_exc()
    finally:
        # Sikrer at lcur lukkes hvis den blev oprettet
        if 'lcur' in locals() and lcur:
             try: lcur.close()
             except: pass
        if cursor: cursor.close()
        if conn: safe_close_connection(conn)

def check_and_remove_inactive_users():
    # Denne funktion fjerner forbindelser for brugere der ikke længere er i 'aktive_bookinger'.
    # Den bør virke som før. Tjek om logning til power_events er korrekt.
    print(f"BG JOB: Check Inactive Users Start - {datetime.now()}"); conn=None; cursor=None
    if not HASS_URL or not HASS_TOKEN: print("ERR inactive: No HASS config."); return
    try:
        conn=get_db_connection();
        if not conn: print("ERR inactive: DB fail."); return
        cursor=conn.cursor(dictionary=True);
        # Find aktive måler-forbindelser hvor brugerens booking_id IKKE findes i aktive_bookinger
        # Ekskluder admin brugeren
        cursor.execute("""
            SELECT am.id as active_meter_id, am.meter_id, am.booking_id,
                   u.id as user_id,
                   mc.power_switch_id, mc.id as meter_config_id
            FROM active_meters am
            JOIN users u ON am.booking_id = u.username
            LEFT JOIN aktive_bookinger ab ON am.booking_id = ab.booking_id
            LEFT JOIN meter_config mc ON am.meter_id = mc.sensor_id
            WHERE ab.booking_id IS NULL -- Nøglen: Findes IKKE i aktive bookinger
              AND u.username != %s
        """,(ADMIN_USERNAME,))
        inactive_connections=cursor.fetchall();

        if not inactive_connections:
            # print("DEBUG inactive: Ingen inaktive forbindelser fundet.") # Mindre støj
            return

        print(f"INFO inactive: Fundet {len(inactive_connections)} inaktive forbindelser der skal fjernes.")

        for conn_info in inactive_connections:
             active_meter_id=conn_info['active_meter_id']; meter_id=conn_info['meter_id']
             booking_id=conn_info['booking_id']; user_id=conn_info['user_id']
             psid=conn_info.get('power_switch_id')
             meter_config_id = conn_info.get('meter_config_id') # Til logning

             print(f"INFO inactive: Fjerner forbindelse ID {active_meter_id} for bruger {booking_id}, måler {meter_id}")

             try:
                 conn.start_transaction() # Start transaktion for hver fjernelse

                 # 1. Forsøg at slukke switch
                 if not psid and meter_id and meter_id.startswith('sensor.'): # Gæt switch
                      base=meter_id.split('.')[1].split('_')[0]; psid=f"switch.{base}_0"
                 if psid:
                    try:
                        # Tjek state før vi slukker? Ikke nødvendigvis, bare prøv at slukke.
                        print(f"DEBUG inactive: Forsøger at slukke switch {psid} for inaktiv forbindelse {active_meter_id}")
                        requests.post(f"{HASS_URL}/api/services/switch/turn_off", headers={"Authorization":f"Bearer {HASS_TOKEN}"}, json={"entity_id":psid}, timeout=10)
                    except Exception as swe:
                        print(f"WARN inactive: Fejl ved slukning af switch {psid} for {booking_id}: {swe}")
                        # Fortsæt alligevel med at fjerne forbindelsen

                 # 2. Log handlingen
                 log_cursor=conn.cursor()
                 try:
                      sql_log_event = """
                          INSERT INTO power_events (user_id, event_type, meter_id, details, event_timestamp)
                          VALUES (%s, %s, %s, %s, NOW())
                      """
                      details = f"Auto Release: Bruger '{booking_id}' ikke længere aktiv. Måler frigivet."
                      log_cursor.execute(sql_log_event, (user_id, 'auto_release_inactive', meter_id, details));

                      # Log også i stroem_koeb (som en "fjernet" post?) - Pakke ID 3?
                      sql_log_purchase = """
                          INSERT INTO stroem_koeb (booking_id, pakke_id, maaler_id, enheder_tilbage, pris_betalt_ore, koebs_tidspunkt, stripe_checkout_session_id)
                          VALUES (%s, %s, %s, %s, %s, NOW(), %s)
                      """
                      log_note = f"AutoReleaseInactive:{user_id}"
                      log_cursor.execute(sql_log_purchase, (booking_id, 3, meter_config_id, 0, 0, log_note)) # Pakke 3, 0 enheder, 0 pris
                      log_cursor.close()
                 except Error as loge: print(f"WARN inactive log DB: {loge}"); log_cursor.close(); conn.rollback(); continue # Stop for denne bruger ved log fejl
                 except Exception as logge: print(f"WARN inactive log Gen: {logge}"); log_cursor.close(); conn.rollback(); continue

                 # 3. Slet forbindelsen fra active_meters
                 del_cursor=conn.cursor()
                 del_cursor.execute("DELETE FROM active_meters WHERE id=%s",(active_meter_id,))
                 deleted=del_cursor.rowcount;
                 del_cursor.close()

                 if deleted>0:
                      conn.commit(); # Commit alt for denne bruger
                      # Ryd cache
                      cache.delete(f"meter_value_{meter_id}")
                      cache.delete(f"meter_value_{normalize_meter_id(meter_id, True)}")
                      cache.delete(f"meter_value_{normalize_meter_id(meter_id, False)}")
                      cache.delete(f"meter_config_switch_{meter_id}")
                      print(f"SUCCESS inactive: Fjernede forbindelse {active_meter_id} for {booking_id}, måler {meter_id}")
                 else:
                      conn.rollback(); # Sletning fejlede?
                      print(f"WARN inactive: Kunne ikke slette active_meters ID {active_meter_id} for {booking_id}. Rollback.")

             except Exception as ue:
                 print(f"ERROR inactive: Fejl ved behandling af inaktiv forbindelse {active_meter_id} ({booking_id}): {ue}");
                 if conn: conn.rollback() # Rul tilbage ved fejl

    except Error as dbe: print(f"FATAL inactive DB: {dbe}")
    except Exception as e: print(f"FATAL inactive Gen: {e}"); traceback.print_exc()
    finally:
        # Sikre lukning af cursors hvis de blev oprettet lokalt i loopet
        if 'log_cursor' in locals() and log_cursor:
            try: log_cursor.close()
            except: pass
        if 'del_cursor' in locals() and del_cursor:
            try: del_cursor.close()
            except: pass
        if cursor: cursor.close()
        if conn: safe_close_connection(conn)


# Start scheduler
scheduler = None
if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    print("Attempting scheduler start...")
    try:
        scheduler = BackgroundScheduler(daemon=True)
        # Check package status (f.eks. hvert 5. minut)
        scheduler.add_job(func=check_package_status, trigger="interval", minutes=5, id='check_pkg_job', replace_existing=True)
        # Check inactive users (f.eks. hver time)
        scheduler.add_job(func=check_and_remove_inactive_users, trigger="interval", hours=1, id='inactive_user_job', replace_existing=True)
        # Send daily sales report (f.eks. kl 00:05 hver nat for gårsdagens salg)
        scheduler.add_job(func=send_daily_sales_report, trigger='cron', hour=0, minute=5, id='daily_sales_report_job', replace_existing=True)
        scheduler.start()
        print("Scheduler started with jobs: check_pkg_job, inactive_user_job, daily_sales_report_job.")
        import atexit
        atexit.register(lambda: scheduler.shutdown() if scheduler and scheduler.running else None)
    except Exception as se:
        print(f"ERROR Scheduler start: {se}")
else:
    print("Scheduler not started (Flask debug mode or reloader process).")


# --- App Execution ---
if __name__ == '__main__':
    print("Starter Flask app...")
    # Overvej at sætte debug=False når du går i produktion
    # Brug en rigtig WSGI server som Gunicorn eller uWSGI i produktion
    app.run(host='0.0.0.0', port=5000, debug=True)