import os
import mysql.connector
from flask import Flask, session
from flask_login import LoginManager, current_user, UserMixin
from dotenv import load_dotenv

# Indlæs miljøvariabler
load_dotenv()

# Hent database konfiguration
DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')

# Opret en lille Flask app for at teste
app = Flask(__name__)
app.secret_key = "test_key"  # Dette er kun til test

# User klasse for at kunne bruge current_user
class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

# Initialisér login manager
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user_data = cursor.fetchone()
        
        if user_data:
            return User(id=user_data['id'], username=user_data['username'])
        
        return None
    except Exception as e:
        print(f"Fejl ved hentning af bruger: {e}")
        return None

def check_session():
    try:
        # Hent alle brugere for at se, hvem der er aktive
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users")
        all_users = cursor.fetchall()
        
        print("Alle brugere i systemet:")
        for user in all_users:
            print(f"ID: {user['id']}, Brugernavn: {user['username']}")
        
        print("\n--- Flask session info (hvis tilgængelig) ---")
        if session:
            print(f"Session data: {session}")
            if 'user_id' in session:
                print(f"Indlogget bruger ID: {session['user_id']}")
        else:
            print("Ingen session data tilgængelig")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Fejl ved tjek af session: {e}")

if __name__ == "__main__":
    with app.app_context():
        check_session()
