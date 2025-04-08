"""
Dette er en omskrevet version af admin_connect_meter funktionen
til at diagnosticere mulige problemer.
"""

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
        cursor.execute("SELECT * FROM bookings WHERE id = %s", (booking_id,))
        if not cursor.fetchone():
            flash('Booking ID findes ikke.', 'error')
            return redirect(url_for('admin_login_or_dashboard'))
        
        # Indsæt måleren i active_meters tabellen
        cursor.execute(
            "INSERT INTO active_meters (booking_id, meter_id, start_date) VALUES (%s, %s, NOW())", 
            (booking_id, meter_id)
        )
        
        # Log handlingen i package_logs
        log_note = f"Admin tilknyttede måler: {current_user.username}"
        cursor.execute(
            """
            INSERT INTO package_logs 
            (booking_id, meter_id, package_name, units_added, admin_action, notes, action_timestamp) 
            VALUES (%s, %s, 'Startpakke', %s, 1, %s, NOW())
            """, 
            (booking_id, meter_id, package_size, log_note)
        )
        
        # Opret en aktiv pakke til måleren
        cursor.execute(
            """
            INSERT INTO active_packages 
            (booking_id, meter_id, package_name, total_units, consumed_units, remaining_units, start_date, expiry_date) 
            VALUES (%s, %s, 'Startpakke', %s, 0, %s, NOW(), DATE_ADD(NOW(), INTERVAL 30 DAY))
            """, 
            (booking_id, meter_id, package_size, package_size)
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
