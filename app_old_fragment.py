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
                    if cursor: cursor.close()
                    if conn: safe_close_connection(conn)
                    return redirect(url_for('select_meter'))
        except Error as dbe:
            print(f"ERR check active meter DB: {dbe}")
            flash(f"DB Fejl: {dbe}", 'error')
            if not sel:  # Kun redirect hvis vi ikke fandt en måler
                if cursor: cursor.close()
                if conn: safe_close_connection(conn)
                return redirect(url_for('select_meter'))
        except Exception as e:
            print(f"ERR check active meter Gen: {e}")
            flash(f"Fejl: {str(e)}", 'error')
            if not sel:  # Kun redirect hvis vi ikke fandt en måler
                if cursor: cursor.close()
                if conn: safe_close_connection(conn)
                return redirect(url_for('select_meter'))
        finally:
            if cursor: cursor.close()
            if conn: safe_close_connection(conn)
    
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
            cursor.execute("SELECT booking_id FROM active_meters WHERE meter_id=%s AND booking_id!=%s",(sid,current_user.username))
            if cursor.fetchone(): flash(trans['meter_already_active'],'error'); session.pop('selected_meter',None); raise Exception("Meter taken")
            
            # Hent eksisterende pakke med størrelse
            mod_cursor = conn.cursor(dictionary=True)
            mod_cursor.execute("SELECT id, package_size FROM active_meters WHERE booking_id=%s",(current_user.username,))
            existing = mod_cursor.fetchone()
            
            # Tjek om det er en tillægspakke
            is_addon = pkg.get('is_addon', 0) == 1 or pkg.get('type') == 'TILLAEG'
            
            if existing:
                if is_addon:
                    # Hvis det er en tillægspakke, læg enheder til eksisterende pakke
                    new_package_size = float(existing['package_size']) + psize
                    print(f"INFO: Tillægspakke købt - lægger {psize} enheder til eksisterende {existing['package_size']} = {new_package_size}")
                    mod_cursor.execute("UPDATE active_meters SET meter_id=%s, start_value=%s, package_size=%s, created_at=NOW() WHERE id=%s",
                                     (sid, start, new_package_size, existing['id']))
                else:
                    # Hvis det er en normal pakke, erstat pakken
                    mod_cursor.execute("UPDATE active_meters SET meter_id=%s, start_value=%s, package_size=%s, created_at=NOW() WHERE id=%s",
                                     (sid, start, psize, existing['id']))
            else:
                # Ny pakke (ingen eksisterende)
                mod_cursor.execute("INSERT INTO active_meters (booking_id, meter_id, start_value, package_size, created_at) VALUES (%s,%s,%s,%s,NOW())",
                                (current_user.username, sid, start, psize))
            
            rows_affected = mod_cursor.rowcount; mod_cursor.close()
            if rows_affected > 0:
                 try: # Log
                     log_cursor = conn.cursor()
                     
                     if is_addon:
                         # For tillægspakker skal vi opdatere den eksisterende enheder_tilbage værdi
                         log_cursor.execute("""
                             INSERT INTO stroem_koeb (booking_id, pakke_id, maaler_id, enheder_tilbage) 
                             VALUES (%s, %s, %s, (
                                 SELECT COALESCE(MAX(enheder_tilbage), 0) + %s 
                                 FROM (SELECT enheder_tilbage FROM stroem_koeb WHERE booking_id = %s ORDER BY id DESC LIMIT 1) as last_purchase
                             ))
                         """, (current_user.username, pid, cfg_id, psize, current_user.username))
                         print(f"INFO: Tillægspakke registreret - opdateret enheder_tilbage med +{psize}")
                     else:
                         # For normale pakker, indsæt som normalt
                         log_cursor.execute('INSERT INTO stroem_koeb (booking_id, pakke_id, maaler_id, enheder_tilbage) VALUES (%s,%s,%s,%s)', 
                                           (current_user.username, pid, cfg_id, psize))
                     
                     log_cursor.close()
                 except Error as loge: 
                     print(f"WARN select_pkg log: {loge}") 
                     print(f"Log fejl detaljer: {traceback.format_exc()}")  # Mere detaljeret fejllog
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