import requests
import time
import random
# Assurez-vous que le chemin d'importation est correct pour votre structure de projet
from Blockchain.Backend.core.database.database import AccountDB
import logging # Ajout du logging pour mieux suivre

# Configuration du logging (optionnel mais recommandé)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# L'adresse depuis laquelle les transactions seront envoyées
# Assurez-vous que cette adresse a suffisamment de fonds (UTXOs)
fromAccount = "kqig3avssEyyDPripQCs2m7S5VKy2WFdW3"

# L'URL de votre endpoint de portefeuille Flask
wallet_url = "http://localhost:5900/wallet" # Assurez-vous que le port est correct (5900 dans votre code original)

def autoBroadcast():
    """
    Envoie une transaction avec un montant aléatoire depuis fromAccount
    vers une autre adresse aléatoire de la base de données toutes les 20 à 30 secondes.
    """
    account_db = AccountDB()

    while True:
        try:
            all_accounts = account_db.read()

            if not all_accounts:
                logging.warning("Aucun compte trouvé dans la base de données. Attente...")
                time.sleep(30) # Attendre avant de réessayer
                continue

            potential_recipients = [
                acc for acc in all_accounts
                if isinstance(acc, dict) and acc.get("PublicAddress") and acc.get("PublicAddress") != fromAccount
            ]

            if not potential_recipients:
                logging.warning(f"Aucune adresse de destination valide trouvée (autre que {fromAccount}). Attente...")
                time.sleep(30) # Attendre avant de réessayer
                continue

            recipient_account = random.choice(potential_recipients)
            to_address = recipient_account.get("PublicAddress")
            min_amount_int = 1
            max_amount_int = 40
            random_amount_int = random.randint(min_amount_int, max_amount_int)
            amount_str = str(random_amount_int) 


            params = {
                "fromAddress": fromAccount,
                "toAddress": to_address,
                "Amount": amount_str 
            }

            try:
                response = requests.post(url=wallet_url, data=params, timeout=10) 
                response.raise_for_status() 

            except requests.exceptions.RequestException as e:
                logging.error(f"Erreur lors de l'envoi de la transaction via l'API: {e}")
            except Exception as e:
                 logging.error(f"Erreur inattendue lors de la requête POST: {e}")


        except Exception as e:
            time.sleep(random.randint(5, 15)) 

        sleep_time = random.uniform(20, 30)
        time.sleep(sleep_time)

