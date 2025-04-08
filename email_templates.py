"""
Sprogskabeloner til email-meddelelser.
Dette modul indeholder HTML og tekst-versioner af alle email-skabeloner,
der bruges i strømstyringssystemet, tilgængelige på alle understøttede sprog.
"""

# Email-skabeloner for påmindelser om lav strøm
LOW_POWER_TEMPLATES = {
    'da': {
        'subject': 'Jelling Camping - Advarsel: Din strømpakke er ved at løbe ud',
        'html': """
        <html>
          <body>
            <h2>Jelling Camping - Advarsel om strømforbrug</h2>
            <p>Hej {fornavn} {efternavn},</p>
            <p>Dette er en service mail.</p>
            <p>Du har nu <strong>{remaining:.2f} enheder</strong> tilbage inden din elmåler slukker.</p>
            <p>Gå på <a href="https://welcome.jellingcamping.dk">welcome.jellingcamping.dk</a> for at indsætte en strømpakke.</p>
            <p>Med venlig hilsen,<br>Jelling Camping</p>
          </body>
        </html>
        """,
        'text': """
        Jelling Camping - Advarsel om strømforbrug
        
        Hej {fornavn} {efternavn},
        
        Dette er en service mail.
        Du har nu {remaining:.2f} enheder tilbage inden din elmåler slukker.
        
        Gå på welcome.jellingcamping.dk for at indsætte en strømpakke.
        
        Med venlig hilsen,
        Jelling Camping
        """
    },
    'en': {
        'subject': 'Jelling Camping - Warning: Your power package is running low',
        'html': """
        <html>
          <body>
            <h2>Jelling Camping - Power Consumption Warning</h2>
            <p>Hello {fornavn} {efternavn},</p>
            <p>This is a service email.</p>
            <p>You now have <strong>{remaining:.2f} units</strong> left before your power meter turns off.</p>
            <p>Go to <a href="https://welcome.jellingcamping.dk">welcome.jellingcamping.dk</a> to add a power package.</p>
            <p>Kind regards,<br>Jelling Camping</p>
          </body>
        </html>
        """,
        'text': """
        Jelling Camping - Power Consumption Warning
        
        Hello {fornavn} {efternavn},
        
        This is a service email.
        You now have {remaining:.2f} units left before your power meter turns off.
        
        Go to welcome.jellingcamping.dk to add a power package.
        
        Kind regards,
        Jelling Camping
        """
    },
    'de': {
        'subject': 'Jelling Camping - Warnung: Ihr Strompaket geht zur Neige',
        'html': """
        <html>
          <body>
            <h2>Jelling Camping - Warnung zum Stromverbrauch</h2>
            <p>Hallo {fornavn} {efternavn},</p>
            <p>Dies ist eine Service-E-Mail.</p>
            <p>Sie haben jetzt <strong>{remaining:.2f} Einheiten</strong> übrig, bevor Ihr Stromzähler abschaltet.</p>
            <p>Gehen Sie auf <a href="https://welcome.jellingcamping.dk">welcome.jellingcamping.dk</a>, um ein Strompaket hinzuzufügen.</p>
            <p>Mit freundlichen Grüßen,<br>Jelling Camping</p>
          </body>
        </html>
        """,
        'text': """
        Jelling Camping - Warnung zum Stromverbrauch
        
        Hallo {fornavn} {efternavn},
        
        Dies ist eine Service-E-Mail.
        Sie haben jetzt {remaining:.2f} Einheiten übrig, bevor Ihr Stromzähler abschaltet.
        
        Gehen Sie auf welcome.jellingcamping.dk, um ein Strompaket hinzuzufügen.
        
        Mit freundlichen Grüßen,
        Jelling Camping
        """
    },
    'nl': {
        'subject': 'Jelling Camping - Waarschuwing: Uw stroompakket raakt op',
        'html': """
        <html>
          <body>
            <h2>Jelling Camping - Waarschuwing stroomverbruik</h2>
            <p>Hallo {fornavn} {efternavn},</p>
            <p>Dit is een service e-mail.</p>
            <p>U heeft nu <strong>{remaining:.2f} eenheden</strong> over voordat uw stroommeter uitschakelt.</p>
            <p>Ga naar <a href="https://welcome.jellingcamping.dk">welcome.jellingcamping.dk</a> om een stroompakket toe te voegen.</p>
            <p>Met vriendelijke groet,<br>Jelling Camping</p>
          </body>
        </html>
        """,
        'text': """
        Jelling Camping - Waarschuwing stroomverbruik
        
        Hallo {fornavn} {efternavn},
        
        Dit is een service e-mail.
        U heeft nu {remaining:.2f} eenheden over voordat uw stroommeter uitschakelt.
        
        Ga naar welcome.jellingcamping.dk om een stroompakket toe te voegen.
        
        Met vriendelijke groet,
        Jelling Camping
        """
    },
    'pl': {
        'subject': 'Jelling Camping - Ostrzeżenie: Twój pakiet energii kończy się',
        'html': """
        <html>
          <body>
            <h2>Jelling Camping - Ostrzeżenie o zużyciu energii</h2>
            <p>Witaj {fornavn} {efternavn},</p>
            <p>To jest wiadomość serwisowa.</p>
            <p>Masz teraz <strong>{remaining:.2f} jednostek</strong> zanim Twój licznik energii się wyłączy.</p>
            <p>Przejdź do <a href="https://welcome.jellingcamping.dk">welcome.jellingcamping.dk</a>, aby dodać pakiet energii.</p>
            <p>Z poważaniem,<br>Jelling Camping</p>
          </body>
        </html>
        """,
        'text': """
        Jelling Camping - Ostrzeżenie o zużyciu energii
        
        Witaj {fornavn} {efternavn},
        
        To jest wiadomość serwisowa.
        Masz teraz {remaining:.2f} jednostek zanim Twój licznik energii się wyłączy.
        
        Przejdź do welcome.jellingcamping.dk, aby dodać pakiet energii.
        
        Z poważaniem,
        Jelling Camping
        """
    },
    'fi': {
        'subject': 'Jelling Camping - Varoitus: Virtapakettisi on käymässä vähiin',
        'html': """
        <html>
          <body>
            <h2>Jelling Camping - Virrankulutusvaroitus</h2>
            <p>Hei {fornavn} {efternavn},</p>
            <p>Tämä on palveluviesti.</p>
            <p>Sinulla on nyt <strong>{remaining:.2f} yksikköä</strong> jäljellä ennen kuin sähkömittarisi sammuu.</p>
            <p>Siirry osoitteeseen <a href="https://welcome.jellingcamping.dk">welcome.jellingcamping.dk</a> lisätäksesi virtapaketin.</p>
            <p>Ystävällisin terveisin,<br>Jelling Camping</p>
          </body>
        </html>
        """,
        'text': """
        Jelling Camping - Virrankulutusvaroitus
        
        Hei {fornavn} {efternavn},
        
        Tämä on palveluviesti.
        Sinulla on nyt {remaining:.2f} yksikköä jäljellä ennen kuin sähkömittarisi sammuu.
        
        Siirry osoitteeseen welcome.jellingcamping.dk lisätäksesi virtapaketin.
        
        Ystävällisin terveisin,
        Jelling Camping
        """
    },
    'fr': {
        'subject': 'Jelling Camping - Avertissement : Votre forfait électrique est presque épuisé',
        'html': """
        <html>
          <body>
            <h2>Jelling Camping - Avertissement de consommation électrique</h2>
            <p>Bonjour {fornavn} {efternavn},</p>
            <p>Ceci est un e-mail de service.</p>
            <p>Il vous reste maintenant <strong>{remaining:.2f} unités</strong> avant que votre compteur électrique ne s'éteigne.</p>
            <p>Rendez-vous sur <a href="https://welcome.jellingcamping.dk">welcome.jellingcamping.dk</a> pour ajouter un forfait électrique.</p>
            <p>Cordialement,<br>Jelling Camping</p>
          </body>
        </html>
        """,
        'text': """
        Jelling Camping - Avertissement de consommation électrique
        
        Bonjour {fornavn} {efternavn},
        
        Ceci est un e-mail de service.
        Il vous reste maintenant {remaining:.2f} unités avant que votre compteur électrique ne s'éteigne.
        
        Rendez-vous sur welcome.jellingcamping.dk pour ajouter un forfait électrique.
        
        Cordialement,
        Jelling Camping
        """
    }
}

def get_low_power_template(language='da'):
    """
    Returnerer skabelon til varsling om lav strøm på det angivne sprog.
    
    Args:
        language (str): Sprogkode ('da', 'en', 'de', osv.)
        
    Returns:
        dict: Skabelon med emne, HTML og tekst-version
    """
    # Hvis sproget ikke findes, brug dansk som standard
    if language not in LOW_POWER_TEMPLATES:
        language = 'da'
        
    return LOW_POWER_TEMPLATES[language]
