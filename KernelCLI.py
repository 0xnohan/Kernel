import socket
import json
import os
import configparser

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_logo():
    print("""
██╗  ██╗███████╗██████╗ ███╗   ██╗███████╗██╗     
██║ ██╔╝██╔════╝██╔══██╗████╗  ██║██╔════╝██║     
█████╔╝ █████╗  ██████╔╝██╔██╗ ██║█████╗  ██║     
██╔═██╗ ██╔══╝  ██╔══██╗██║╚██╗██║██╔══╝  ██║     
██║  ██╗███████╗██║  ██║██║ ╚████║███████╗███████╗
╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝╚══════╝╚══════╝
    """)
    print("\nBienvenue dans le Client Kernel")

def SendRpcCommand(host, rpc_port, command):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((host, rpc_port))
            s.sendall(json.dumps(command).encode('utf-8'))
            response_data = s.recv(4096)
            return json.loads(response_data.decode('utf-8'))
    except ConnectionRefusedError:
        return {"status": "error", "message": "Connexion refusée. Le daemon KernelD.py n'est pas en cours d'exécution"}
    except Exception as e:
        return {"status": "error", "message": f"Erreur: {e}"}

def main():
    config = configparser.ConfigParser()
    config.read('config.ini')
    host = config['DEFAULT']['host']
    rpc_port = int(config['Webhost']['port']) + 1

    clear_screen()
    print_logo()

    response = SendRpcCommand(host, rpc_port, {"command": "ping"})
    if response.get("status") == "error" and "Connexion refusée" in response.get("message", ""):
        print(f"\nERREUR: {response['message']}")
        return

    while True:
        print("\n" + "="*40)
        print("Menu CLI")
        print("="*40)
        print("1 - Démarrer le Minage")
        print("2 - Arrêter le Minage")
        print("3 - Envoyer des KNL")
        print("4 - Créer un portefeuille")
        print("5 - Quitter")
        choice = input(">> ")

        response = {}
        if choice == '1':
            response = SendRpcCommand(host, rpc_port, {"command": "start_miner"})
        elif choice == '2':
            response = SendRpcCommand(host, rpc_port, {"command": "stop_miner"})
        elif choice == '3':
            from_addr = input("Votre adresse d'envoi: ")
            to_addr = input("Adresse du destinataire: ")
            amount = input("Montant en KNL: ")
            command = {"command": "send_tx", "params": {"from": from_addr, "to": to_addr, "amount": amount}}
            response = SendRpcCommand(host, rpc_port, command)
        elif choice == '4':
            response = SendRpcCommand(host, rpc_port, {"command": "create_wallet"})
            if response.get("status") == 'success':
                wallet = response.get('wallet', {})
                print("\n--- Portefeuille créé avec succès ---")
                print(f"  Adresse: {wallet.get('PublicAddress')}")
                print(f"  Clé Privée: {wallet.get('privateKey')}")
        elif choice == '5':
            print("À bientôt !")
            break
        else:
            print("Choix invalide. Veuillez réessayer...")
        
        if response and response != {}:
             print(f"\n[DAEMON] -> {response.get('message', 'Aucun message')}")

        input("\nAppuyez sur Entrée pour continuer...")
        clear_screen()
        print_logo()

if __name__ == "__main__":
    main()