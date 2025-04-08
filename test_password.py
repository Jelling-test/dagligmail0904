from werkzeug.security import generate_password_hash, check_password_hash

def validate_password_case_insensitive(stored_hash, input_password):
    """
    Validerer et password mod et gemt hash på en case-insensitive måde.
    Prøver forskellige varianter af input_password med forskellige store/små bogstaver.
    """
    print(f"DEBUG validate_password: Validerer '{input_password}' mod hash")
    
    # Tjek først med det originale password
    original_match = check_password_hash(stored_hash, input_password)
    print(f"DEBUG validate_password: Original match: {original_match}")
    if original_match:
        return True
        
    # Prøv med første bogstav stort, resten små
    capitalized = input_password.capitalize()
    cap_match = check_password_hash(stored_hash, capitalized)
    print(f"DEBUG validate_password: Capitalize match ('{capitalized}'): {cap_match}")
    if cap_match:
        return True
    
    # Prøv med alle bogstaver store
    upper = input_password.upper()
    upper_match = check_password_hash(stored_hash, upper)
    print(f"DEBUG validate_password: Upper match ('{upper}'): {upper_match}")
    if upper_match:
        return True
        
    # Prøv med alle bogstaver små
    lower = input_password.lower()
    lower_match = check_password_hash(stored_hash, lower)
    print(f"DEBUG validate_password: Lower match ('{lower}'): {lower_match}")
    if lower_match:
        return True
    
    return False

# Test funktionen
if __name__ == "__main__":
    # Opret et hash af "Halse"
    original_password = "Halse"
    hashed_password = generate_password_hash(original_password)
    
    print(f"Original password: {original_password}")
    print(f"Hashed password: {hashed_password}")
    
    # Test med forskellige varianter
    test_passwords = ["Halse", "halse", "HALSE", "HaLsE"]
    
    for test_pw in test_passwords:
        result = validate_password_case_insensitive(hashed_password, test_pw)
        print(f"Test med '{test_pw}': {result}")
