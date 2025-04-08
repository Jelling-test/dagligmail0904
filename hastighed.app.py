import os
import requests
from datetime import datetime, timedelta
from functools import wraps

import mysql.connector
from mysql.connector import Error, pooling # Importer pooling
from mysql.connector.cursor import MySQLCursorDict

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_caching import Cache # Importer Cache
from apscheduler.schedulers.background import BackgroundScheduler
from werkzeug.security import generate_password_hash, check_password_hash # Tilføj check_password_hash
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_key')

# --- Cache Konfiguration ---
# Brug SimpleCache som default (in-memory).
# Kan overskrives med f.eks. 'redis' via miljøvariabler i produktion.
cache_config = {
    "CACHE_TYPE": os.getenv('CACHE_TYPE', 'SimpleCache'),
    "CACHE_DEFAULT_TIMEOUT": int(os.getenv('CACHE_DEFAULT_TIMEOUT', 300)) # Default timeout hvis ikke sat på decorator
}
if cache_config['CACHE_TYPE'].lower() == 'redis':
     cache_config["CACHE_REDIS_URL"] = os.getenv('CACHE_REDIS_URL', 'redis://localhost:6379/0')

app.config.from_mapping(cache_config)
cache = Cache(app)
print(f"Cache konfigureret med type: {app.config['CACHE_TYPE']}")


# --- Database Connection Pooling ---
db_pool = None

def init_db_pool():
    global db_pool
    try:
        pool_config = {
            "host": os.getenv('DB_HOST'),
            "user": os.getenv('DB_USER'),
            "password": os.getenv('DB_PASSWORD'),
            "database": os.getenv('DB_NAME'),
            "pool_name": os.getenv('DB_POOL_NAME', "flask_pool"),
            "pool_size": int(os.getenv('DB_POOL_SIZE', 5)), # Antal forbindelser i poolen
            "pool_reset_session": True, # Nulstil session ved frigivelse
            # "connection_timeout": 10 # Timeout for at få forbindelse fra pool
        }
        # Fjern None værdier fra config, da connectoren ikke kan lide dem
        pool_config = {k: v for k, v in pool_config.items() if v is not None}

        print(f"Initialiserer database pool '{pool_config.get('pool_name')}' med størrelse {pool_config.get('pool_size')}...")
        db_pool = pooling.MySQLConnectionPool(**pool_config)
        # Test at hente en forbindelse for at fange fejl tidligt
        print("Tester pool ved at hente en forbindelse...")
        test_conn = db_pool.get_connection()
        print(f"Forbindelse hentet succesfuldt (ID: {test_conn.connection_id}). Frigiver...")
        test_conn.close() # Vigtigt at frigive test forbindelsen!
        print("Database pool initialiseret succesfuldt.")
    except Error as e:
        print(f"FATAL: Fejl ved initialisering af database pool: {e}")
        db_pool = None # Sæt til None hvis initialisering fejler
    except Exception as e:
        print(f"FATAL: Uventet fejl ved initialisering af database pool: {e}")
        db_pool = None

def get_db_connection():
    """Henter en forbindelse fra den globale pool."""
    global db_pool
    if db_pool is None:
        print("ERROR: Database pool er ikke initialiseret.")
        try:
            # Forsøg at initialisere poolen igen
            print("Forsøger at initialisere database pool igen...")
            init_db_pool()
            if db_pool is None:
                print("Geninitialisering af database pool fejlede.")
                return None
            else:
                print("Database pool blev geninitialiseret succesfuldt.")
        except Exception as e:
            print(f"Fejl ved geninitialisering af database pool: {e}")
            return None
    try:
        # Tilføj mere detaljeret logging
        print(f"DEBUG: Forsøger at hente forbindelse fra pool med config: Host={os.getenv('DB_HOST')}, User={os.getenv('DB_USER')}, DB={os.getenv('DB_NAME')}")
        conn = db_pool.get_connection()
        conn.cursor_class = MySQLCursorDict # Sæt cursor class her (alternativt ved pool creation)
        print(f"DEBUG: Hentet DB forbindelse {conn.connection_id} fra pool.")
        
        # Test forbindelsen ved at udføre en simpel forespørgsel
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            print(f"DEBUG: Forbindelse {conn.connection_id} testet og er aktiv.")
        except Error as test_err:
            print(f"ADVARSEL: Forbindelse {conn.connection_id} kunne ikke udføre test-query: {test_err}")
            # Luk forbindelsen og prøv igen
            try:
                conn.close()
                print(f"DEBUG: Lukket fejlende forbindelse {conn.connection_id}. Prøver at hente en ny.")
                conn = db_pool.get_connection()
                conn.cursor_class = MySQLCursorDict
                print(f"DEBUG: Hentet ny DB forbindelse {conn.connection_id} fra pool efter fejl.")
            except Error as retry_err:
                print(f"FEJL: Kunne ikke hente ny forbindelse efter test-fejl: {retry_err}")
                return None
        
        return conn
    except Error as e:
        print(f"FEJL ved hentning af forbindelse fra database pool: {e}")
        # Mere detaljeret fejlinfo
        if hasattr(e, 'errno'):
            if e.errno == 2003:
                print(f"FEJL: Kunne ikke forbinde til MySQL server på '{os.getenv('DB_HOST')}' - kontroller at serveren kører og er tilgængelig.")
            elif e.errno == 1045:
                print(f"FEJL: Adgang nægtet for bruger '{os.getenv('DB_USER')}' - kontroller brugernavn og adgangskode.")
            elif e.errno == 1049:
                print(f"FEJL: Databasen '{os.getenv('DB_NAME')}' eksisterer ikke - kontroller databasenavnet.")
            else:
                print(f"FEJL: MySQL fejlkode {e.errno}: {e}")
        
        # Forsøg at initialisere poolen igen ved fejl
        try:
            print("Fejl ved hentning af forbindelse. Forsøger at initialisere database pool igen...")
            init_db_pool()
            if db_pool is not None:
                try:
                    conn = db_pool.get_connection()
                    conn.cursor_class = MySQLCursorDict
                    print(f"DEBUG: Hentet DB forbindelse {conn.connection_id} fra geninitialiseret pool.")
                    return conn
                except Error as e2:
                    print(f"Fejl ved hentning af forbindelse efter geninitialisering: {e2}")
                    return None
        except Exception as e3:
            print(f"Fejl ved geninitialisering efter forbindelsesfejl: {e3}")
            return None
        return None

# Rest of the code remains the same
