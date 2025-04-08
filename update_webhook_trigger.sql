DELIMITER //

DROP TRIGGER IF EXISTS after_webhook_insert //

CREATE TRIGGER after_webhook_insert
AFTER INSERT ON webhooks
FOR EACH ROW
BEGIN
    -- Variabler til at holde værdier fra JSON
    DECLARE current_booking_id INT;
    DECLARE is_checked_in BOOLEAN;
    DECLARE is_checked_out BOOLEAN;
    DECLARE first_name VARCHAR(50);
    DECLARE last_name VARCHAR(50);
    DECLARE email VARCHAR(255);  -- Ny variabel til email
    DECLARE total_adults INT;
    DECLARE arrival_date DATE;
    DECLARE departure_date DATE;
    DECLARE booking_status VARCHAR(50);
    DECLARE plads_type VARCHAR(10);

    -- Udtræk værdier fra JSON payload
    SET current_booking_id = JSON_UNQUOTE(JSON_EXTRACT(NEW.json_payload, '$.bookingId'));
    SET is_checked_in = JSON_UNQUOTE(JSON_EXTRACT(NEW.json_payload, '$.bookingIsCheckedIn')) = 'true';
    SET is_checked_out = JSON_UNQUOTE(JSON_EXTRACT(NEW.json_payload, '$.bookingIsCheckedOut')) = 'true';
    SET first_name = JSON_UNQUOTE(JSON_EXTRACT(NEW.json_payload, '$.guest.firstName'));
    SET last_name = JSON_UNQUOTE(JSON_EXTRACT(NEW.json_payload, '$.guest.lastName'));
    SET email = JSON_UNQUOTE(JSON_EXTRACT(NEW.json_payload, '$.guest.email'));  -- Udtræk email fra JSON
    SET total_adults = COALESCE(JSON_EXTRACT(NEW.json_payload, '$.totalAdults'), 0);
    SET arrival_date = STR_TO_DATE(JSON_UNQUOTE(JSON_EXTRACT(NEW.json_payload, '$.arrivalDate')), '%Y-%m-%d');
    SET departure_date = STR_TO_DATE(JSON_UNQUOTE(JSON_EXTRACT(NEW.json_payload, '$.departureDate')), '%Y-%m-%d');
    SET booking_status = IF(JSON_UNQUOTE(JSON_EXTRACT(NEW.json_payload, '$.bookingIsConfirmed')) = 'true', 'CONFIRMED', 'PENDING');
    
    -- Sæt plads_type baseret på antal voksne
    SET plads_type = IF(total_adults = 0, 'SÆSON', 'NORMAL');

    -- Hvis booking_id er gyldig
    IF current_booking_id IS NOT NULL THEN
        -- Hvis tjekket ind og ikke tjekket ud
        IF is_checked_in = TRUE AND is_checked_out = FALSE THEN
            -- Indsæt eller opdater i aktive_bookinger
            INSERT INTO camping_aktiv.aktive_bookinger (
                booking_id, 
                fornavn, 
                efternavn, 
                email,  -- Tilføj email felt her
                plads_type, 
                antal_gaester, 
                ankomst_dato, 
                afrejse_dato, 
                status
            ) 
            VALUES (
                current_booking_id,
                first_name,
                last_name,
                email,  -- Tilføj email værdi her
                plads_type,
                total_adults,
                arrival_date,
                departure_date,
                booking_status
            )
            ON DUPLICATE KEY UPDATE
                fornavn = VALUES(fornavn),
                efternavn = VALUES(efternavn),
                email = VALUES(email),  -- Tilføj email opdatering her
                plads_type = VALUES(plads_type),
                antal_gaester = VALUES(antal_gaester),
                ankomst_dato = VALUES(ankomst_dato),
                afrejse_dato = VALUES(afrejse_dato),
                status = VALUES(status),
                sidst_opdateret = CURRENT_TIMESTAMP;
                
        -- Hvis tjekket ud
        ELSEIF is_checked_out = TRUE THEN
            -- Slet fra aktive bookinger
            DELETE FROM camping_aktiv.aktive_bookinger 
            WHERE booking_id = current_booking_id;
        END IF;
    END IF;
END //

DELIMITER ;
