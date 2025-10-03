import socket
import json
import os
import configparser
import subprocess
import time
import sys

def clearScreen():
    os.system('cls' if os.name == 'nt' else 'clear')

def printLogo():
    print("""
██╗  ██╗███████╗██████╗ ███╗   ██╗███████╗██╗
██║ ██╔╝██╔════╝██╔══██╗████╗  ██║██╔════╝██║
█████╔╝ █████╗  ██████╔╝██╔██╗ ██║█████╗  ██║
██╔═██╗ ██╔══╝  ██╔══██╗██║╚██╗██║██╔══╝  ██║
██║  ██╗███████╗██║  ██║██║ ╚████║███████╗███████╗
╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝╚══════╝╚══════╝
    """)
    print("\nWelcome to Kernel CLI")

# Start the deamon in another terminal
def start_daemon(host, rpc_port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.connect((host, rpc_port))
        print("Kernel Daemon is already running.")
        return
    except (ConnectionRefusedError, socket.timeout):
        print("Starting Kernel Daemon in a new terminal...")
        daemon_script_path = os.path.join('src', 'core', 'daemon', 'daemon.py')
        current_dir = os.getcwd()

        if sys.platform == "win32":
            subprocess.Popen(f'start cmd /k "{sys.executable}" "{daemon_script_path}"', shell=True, cwd=current_dir)

        elif sys.platform == "darwin":
            script = f'tell app "Terminal" to do script "cd \\"{current_dir}\\" && \\"{sys.executable}\\" \\"{daemon_script_path}\\""'
            subprocess.Popen(['osascript', '-e', script])

        elif sys.platform.startswith('linux'):
            subprocess.Popen(['gnome-terminal', '--', sys.executable, daemon_script_path], cwd=current_dir)

        else:
            print(f"Unsupported OS: {sys.platform}, please start the daemon manually in another terminal")
            print("run 'python {daemon_script_path}' in another terminal")

        time.sleep(5)

# Loading screen to wait for the deamon to setup
def loading_screen():
    print("\nConnecting to the network...")
    animation = "|/-\\"
    for i in range(50):
        time.sleep(0.1)
        sys.stdout.write("\r" + animation[i % len(animation)] + " ")
        sys.stdout.flush()
    print("\nConnected !")
    time.sleep(1)

# Send command to the Daemon
def SendRpcCommand(host, rpc_port, command):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((host, rpc_port))
            s.sendall(json.dumps(command).encode('utf-8'))
            response_data = s.recv(4096)
            return json.loads(response_data.decode('utf-8'))
    except ConnectionRefusedError:
        return {"status": "error", "message": "No connection. Please check if the daemon is running"}
    except Exception as e:
        return {"status": "error", "message": f"Error: {e}"}

def settings(host, rpc_port):
    while True:
        config_response = SendRpcCommand(host, rpc_port, {"command": "get_config"})
        if config_response.get('status') != 'success':
            print("Could not load current configuration.")
            input("\nPress Enter to continue...")
            return
        
        current_config = config_response.get('config', {})
        
        clearScreen()
        printLogo()

        c_host = current_config.get('NETWORK', {}).get('host', 'N/A')
        c_p2p_port = current_config.get('P2P', {}).get('port', 'N/A')
        c_api_port = current_config.get('API', {}).get('port', 'N/A')
        c_wallet = current_config.get('MINING', {}).get('wallet', 'N/A')

        print("\n" + "="*40)
        print("Settings Menu (Current Configuration)")
        print("="*40)
        print(f"1 - Change Host IP        (current: {c_host})")
        print(f"2 - Change P2P Port       (current: {c_p2p_port})")
        print(f"3 - Change API Port       (current: {c_api_port})")
        print(f"4 - Set Miner Wallet      (current: {c_wallet})")
        print("5 - Back to Main Menu")
        choice = input(">> ")

        response = {}
        if choice == '1':
            new_host = input(f"Enter new host IP (current: {c_host}): ") or c_host
            command = {"command": "update_config", "params": {"section": "NETWORK", "key": "host", "value": new_host}}
            response = SendRpcCommand(host, rpc_port, command)
        elif choice == '2':
            new_port = input(f"Enter new P2P port (current: {c_p2p_port}): ") or c_p2p_port
            command = {"command": "update_config", "params": {"section": "P2P", "key": "port", "value": new_port}}
            response = SendRpcCommand(host, rpc_port, command)
        elif choice == '3':
            new_port = input(f"Enter new API port (current: {c_api_port}): ") or c_api_port
            command = {"command": "update_config", "params": {"section": "API", "key": "port", "value": new_port}}
            response = SendRpcCommand(host, rpc_port, command)
        elif choice == '4':
            wallets_response = SendRpcCommand(host, rpc_port, {"command": "get_wallets"})
            if wallets_response.get('status') == 'success' and wallets_response.get('wallets'):
                wallets = wallets_response.get('wallets', [])
                print("\nAvailable wallets:")
                for i, wallet in enumerate(wallets):
                    print(f"  {i + 1} - {wallet.get('WalletName')}")
                try:
                    wallet_choice_str = input(f"Select a wallet (current: {c_wallet}): ")
                    if not wallet_choice_str:
                        response = {"message": "Miner wallet not changed"}
                    else:
                        wallet_choice = int(wallet_choice_str) - 1
                        if 0 <= wallet_choice < len(wallets):
                            selected_wallet_name = wallets[wallet_choice]['WalletName']
                            command = {"command": "update_config", "params": {"section": "MINING", "key": "wallet", "value": selected_wallet_name}}
                            response = SendRpcCommand(host, rpc_port, command)
                        else:
                            response = {"message": "Invalid selection."}
                except ValueError:
                    response = {"message": "Invalid input, please enter a number"}
            else:
                response = {"message": "No wallets found, please create one first"}
        elif choice == '5':
            return
        else:
            response = {"message": "Invalid choice."}
        
        print(f"\n[DAEMON] -> {response.get('message', 'No message')}")
        input("\nPress Enter to continue...")

# Main CLI loop
def main():
    config = configparser.ConfigParser()
    config_path = os.path.join('data', 'config.ini')
    config.read(config_path)
    host = config['NETWORK']['host']
    rpc_port = int(config['API']['port']) + 1

    start_daemon(host, rpc_port)
    loading_screen()
    
    while True:
        clearScreen()
        printLogo()
        print("\n" + "="*40)
        print("Menu CLI")
        print("="*40)
        print("1 - Start Mining")
        print("2 - Stop Mining")
        print("3 - Send Transaction")
        print("4 - Create Wallet")
        print("5 - Settings") 
        print("6 - Quit")
        choice = input(">> ")

        response = {}
        if choice == '1':
            response = SendRpcCommand(host, rpc_port, {"command": "start_miner"})
        elif choice == '2':
            response = SendRpcCommand(host, rpc_port, {"command": "stop_miner"})
        elif choice == '3':
            wallets_response = SendRpcCommand(host, rpc_port, {"command": "get_wallets"})
            if wallets_response.get('status') == 'success' and wallets_response.get('wallets'):
                wallets = wallets_response['wallets']
                print("\nSelect a sender wallet:")
                for i, wallet in enumerate(wallets):
                    balance = wallet.get('balance', 0.0)
                    print(f"  {i + 1} - {wallet.get('WalletName')} ({wallet.get('PublicAddress')}) - Balance: {balance:.8f} KNL")
                
                try:
                    wallet_choice = int(input(">> ")) - 1
                    if 0 <= wallet_choice < len(wallets):
                        from_addr = wallets[wallet_choice]['PublicAddress']
                        print(f"\nSender: {from_addr}")
                        to_addr = input("Recipient address: ")
                        amount = input("Amount in KNL: ")
                        command = {"command": "send_tx", "params": {"from": from_addr, "to": to_addr, "amount": amount}}
                        response = SendRpcCommand(host, rpc_port, command)
                    else:
                        response = {"message": "Invalid selection."}
                except ValueError:
                    response = {"message": "Invalid input, please enter a number"}
            else:
                response = {"message": "No wallets found please create a wallet first"}
        elif choice == '4':
            wallet_name = input("Enter a name for the new wallet: ")
            if wallet_name:
                command = {"command": "create_wallet", "params": {"name": wallet_name}}
                response = SendRpcCommand(host, rpc_port, command)
                if response.get("status") == 'success':
                    wallet = response.get('wallet', {})
                    print("\n--- Wallet created ---")
                    print(f"  Name: {wallet.get('WalletName')}")
                    print(f"  Public Address: {wallet.get('PublicAddress')}")
                    print(f"  Private Key: {wallet.get('privateKey')}")
            else:
                response = {"message": "Wallet name cannot be empty"}
        elif choice == '5':
            settings(host, rpc_port)
            config.read(config_path)
            host = config['NETWORK']['host']
            rpc_port = int(config['API']['port']) + 1
            continue
        elif choice == '6':
            print("Exiting... Please close the Daemon terminal manually")
            break
        else:
            response = {"message": "Invalid choice. Please try again..."}

        if response:
            print(f"\n[DAEMON] -> {response.get('message', 'No message')}")

        input("\nPress Enter to continue...")

if __name__ == "__main__":
    main()