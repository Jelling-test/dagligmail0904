@app.route('/select_package', methods=['GET', 'POST'])
@login_required
def select_package():
    lang=session.get('language','da'); trans=translations.get(lang,translations['da']); sel=session.get('selected_meter')
    
    # Hvis der ikke er valgt en måler i session, tjek om brugeren allerede har en aktiv måler
    if not sel:
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor(dictionary=True)
                # Find brugerens aktive måler
                cursor.execute('SELECT am.meter_id, am.start_value, mc.id as meter_config_id, mc.display_name FROM active_meters am JOIN meter_config mc ON am.meter_id = mc.sensor_id WHERE am.booking_id = %s', (current_user.username,))
                active_meter = cursor.fetchone()
                
                if active_meter:
                    # Bruger har en aktiv måler - opret select_meter data
                    meter_id = active_meter['meter_id']
                    sel = {
                        'meter_config_id': active_meter['meter_config_id'],
                        'sensor_id': meter_id,
                        'display_name': active_meter['display_name'],
                        'start_value': active_meter['start_value'],
                        'sensor_read_for_start': meter_id
                    }
                    print(f"INFO: Genbruger aktiv måler {meter_id} for bruger {current_user.username} til tillægspakke")
                else:
                    # Ingen aktiv måler fundet
                    flash('Ingen måler valgt.','warning')
                    return redirect(url_for('select_meter'))
        except Error as dbe:
            print(f"ERR check active meter DB: {dbe}")
            flash(f"DB Fejl: {dbe}", 'error')
            if not sel:  # Kun redirect hvis vi ikke fandt en måler
                return redirect(url_for('select_meter'))
        except Exception as e:
            print(f"ERR check active meter Gen: {e}")
            flash(f"Fejl: {str(e)}", 'error')
            if not sel:  # Kun redirect hvis vi ikke fandt en måler
                return redirect(url_for('select_meter'))
        finally:
            if cursor: 
                cursor.close()
            if conn: 
                safe_close_connection(conn)