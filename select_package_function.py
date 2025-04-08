@app.route('/select_package', methods=['POST'])
@login_required
def select_package():
    # Tjek om en måler er valgt
    sel = session.get('selected_meter', None)
    if not sel:
        flash(translations.get(session.get('lang', 'da'), {}).get('error_no_meter', 'Ingen måler valgt.'), 'warning')
        return redirect(url_for('select_meter'))
    
    # Hent valgte pakke ID fra formen
    package_id = request.form.get('package_id')
    if not package_id:
        flash(translations.get(session.get('lang', 'da'), {}).get('error_no_package', 'Ingen pakke valgt.'), 'warning')
        return redirect(url_for('dashboard'))
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            flash(translations.get(session.get('lang', 'da'), {}).get('error_db_connection', 'Kunne ikke forbinde til databasen.'), 'danger')
            return redirect(url_for('dashboard'))
        
        cursor = conn.cursor(dictionary=True)
        
        # Hent pakke information
        cursor.execute('SELECT * FROM power_packages WHERE id = %s', (package_id,))
        package = cursor.fetchone()
        if not package:
            flash(translations.get(session.get('lang', 'da'), {}).get('error_invalid_package', 'Ugyldig pakke.'), 'danger')
            return redirect(url_for('dashboard'))
        
        # Hent aktive måler detaljer
        cursor.execute('SELECT * FROM active_meters WHERE id = %s AND user_id = %s', (sel, current_user.id))
        meter = cursor.fetchone()
        if not meter:
            flash(translations.get(session.get('lang', 'da'), {}).get('error_invalid_meter', 'Ugyldig måler.'), 'danger')
            return redirect(url_for('select_meter'))
        
        # For tillægspakker: Tjek om brugeren har en pakke i forvejen
        if package['is_addon']:
            if meter['package_id'] is None:
                flash(translations.get(session.get('lang', 'da'), {}).get('error_no_active_package', 'Du skal have en aktiv pakke før du kan købe tillægspakker.'), 'warning')
                return redirect(url_for('dashboard'))
            
            # Opdater eksisterende pakke ved at tilføje (ikke erstatte) enheder
            cursor.execute('''
                UPDATE active_meters 
                SET purchased_kWh = purchased_kWh + %s,
                    purchase_date = NOW()
                WHERE id = %s
            ''', (package['kWh'], sel))
        else:
            # For almindelige pakker: Erstat eksisterende pakke
            # Opdater måleren med den nye pakke
            cursor.execute('''
                UPDATE active_meters 
                SET package_id = %s,
                    purchased_kWh = %s,
                    purchase_date = NOW()
                WHERE id = %s
            ''', (package['id'], package['kWh'], sel))
        
        # Gem ændringerne
        conn.commit()
        
        # Bekræft købet til brugeren
        if package['is_addon']:
            flash(f"Du har købt tillægspakken '{package['name']}' for {package['price']} kr. Der er blevet tilføjet {package['kWh']} kWh til din eksisterende pakke.", 'success')
        else:
            flash(f"Du har købt pakken '{package['name']}' for {package['price']} kr.", 'success')
        
    except Error as e:
        if conn: conn.rollback()
        flash(f'{translations.get(session.get("lang", "da"), {}).get("error_general", "Generel fejl")}: {e}', 'danger')
    finally:
        if cursor: cursor.close()
        if conn: safe_close_connection(conn)
    
    return redirect(url_for('dashboard'))
