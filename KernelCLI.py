import socket
import json
import os
import configparser
import subprocess
import time
import sys
from src.utils.config_loader import load_config, update_config, get_config_dict
from src.chain.params import FEE_RATE_FAST, FEE_RATE_NORMAL, FEE_RATE_SLOW
import logging
logger = logging.getLogger(__name__)

running_processes = {
    "daemon": None,
    "miner": None
}

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

def start_process_in_new_terminal(script_path, process_key):
    current_dir = os.getcwd()
    
    if sys.platform == "win32":
        process = subprocess.Popen(f'start cmd /k "cd /d {current_dir} && {sys.executable} {script_path}"', shell=True)
    elif sys.platform == "darwin":
        script = f'tell app "Terminal" to do script "cd \\"{current_dir}\\" && \\"{sys.executable}\\" \\"{script_path}\\""'
        process = subprocess.Popen(['osascript', '-e', script])
    elif sys.platform.startswith('linux'):
        process = subprocess.Popen(['gnome-terminal', '--', sys.executable, script_path], cwd=current_dir)
    else:
        logger.error(f"Unsupported OS: {sys.platform}, please start {script_path} manually.")
        return
        
    running_processes[process_key] = process
    logger.info(f"Started {process_key} in a new terminal")

def start_daemon(host, rpc_port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.connect((host, rpc_port))
        logger.warning("Kernel Daemon is already running")
        return
    except (ConnectionRefusedError, socket.timeout):
        logger.info("Starting Kernel Daemon...")
        daemon_script_path = os.path.join('src', 'node', 'kerneld.py')
        start_process_in_new_terminal(daemon_script_path, "deamon")
        time.sleep(5) 

def shutdown_all(host, rpc_port):
    logger.info("\nStopping all processes...")
    
    miner_process = running_processes.get("miner")
    if miner_process and miner_process.poll() is None:
        logger.debug("Stopping miner process...")
        miner_process.terminate()
        running_processes["miner"] = None

    logger.debug("Sending shutdown command to daemon...")
    SendRpcCommand(host, rpc_port, {"command": "shutdown"})
    logger.info("\nAll processes have been stopped")

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
        return {"status": "error", "message": f"RPC Error: {e}"}
    
def settings(host, rpc_port):
    while True:
        current_config = get_config_dict()
        
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
            update_config("NETWORK", "host", new_host)
            response = {"message": "Host IP updated"}
        elif choice == '2':
            new_port = input(f"Enter new P2P port (current: {c_p2p_port}): ") or c_p2p_port
            update_config("P2P", "port", new_port)
            response = {"message": "P2P port updated"}
        elif choice == '3':
            new_port = input(f"Enter new API port (current: {c_api_port}): ") or c_api_port
            update_config("API", "port", new_port)
            response = {"message": "API port updated"}
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
                            update_config("MINING", "wallet", selected_wallet_name)
                            response = {"message": "Miner wallet updated"}
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
        
        logger.info(f"\n[DAEMON] -> {response.get('message', 'No message')}")
        input("\nPress Enter to continue...")

# Main CLI loop
def main():
    config = load_config()
    host = config['NETWORK']['host']
    rpc_port = int(config['API']['port']) + 1

    start_daemon(host, rpc_port)

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
            logger.info("Starting KernelX miner process...")
            miner_script_path = os.path.join('KernelX', 'main.py')
            if os.path.exists(miner_script_path):
                start_process_in_new_terminal(miner_script_path, "miner")
                response = {"message": "Miner process launched in a new window"}
            else:
                response = {"message": "Error: KernelX/main.py not found"}

        elif choice == '2':
            miner_process = running_processes.get("miner")
            if miner_process and miner_process.poll() is None:
                logger.info("Stopping miner process...")
                miner_process.terminate()
                running_processes["miner"] = None
                response = {"message": "Miner process stopped"}
            else:
                response = {"message": "Miner process is not running"}

        elif choice == '3':
            wallets_response = SendRpcCommand(host, rpc_port, {"command": "get_wallets"})
            if wallets_response.get('status') == 'success' and wallets_response.get('wallets'):
                wallets = wallets_response['wallets']
                print("\nSelect a sender wallet:")
                for i, wallet in enumerate(wallets):
                    balance = wallet.get('balance', 0.0)
                    print(f"  {i + 1} - {wallet.get('WalletName')} ({wallet.get('PublicAddress')}) - Balance: {balance:.8f} KOR")
                    fee_fast = FEE_RATE_FAST
                    fee_normal = FEE_RATE_NORMAL
                    fee_slow = FEE_RATE_SLOW
                
                try:
                    wallet_choice = int(input(">> ")) - 1
                    if 0 <= wallet_choice < len(wallets):
                        from_addr = wallets[wallet_choice]['PublicAddress']
                        print(f"\nSender: {from_addr}")
                        to_addr = input("Recipient address: ")
                        amount = input("Amount in KOR: ") 
                        print("\nSelect transaction fee rate:")
                        print(f"  1 - Fast ({fee_fast} kores/byte)")
                        print(f"  2 - Normal ({fee_normal} kores/byte)")
                        print(f"  3 - Slow ({fee_slow} kores/byte)")
                        fee_choice = input(">> ")
                        fee_map = {'1': fee_fast, '2': fee_normal, '3': fee_slow}
                        fee_rate = fee_map.get(fee_choice, FEE_RATE_NORMAL) 
                        print(f"Fee rate selected: {fee_rate} kernels/byte")

                        command = {"command": "send_tx", "params": {"from": from_addr, "to": to_addr, "amount": amount, "fee_rate": fee_rate}}
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
            config = load_config()
            host = config['NETWORK']['host']
            rpc_port = int(config['API']['port']) + 1
            continue
        elif choice == '6':
            shutdown_all(host, rpc_port)
            break
        else:
            response = {"message": "Invalid choice. Please try again..."}

        if response:
            logger.info(f"\n[DAEMON] -> {response.get('message', 'No message')}")

        input("\nPress Enter to continue...")
    
if __name__ == "__main__":
    main()