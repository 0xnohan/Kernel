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

        daemon_script_path = 'KernelD.py'
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
            return
            
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

# Main CLI loop
def main():
    config = configparser.ConfigParser()
    config.read('config.ini')
    host = config['DEFAULT']['host']
    rpc_port = int(config['Webhost']['port']) + 1

    start_daemon(host, rpc_port)
    loading_screen()
    clearScreen()
    printLogo()

    response = SendRpcCommand(host, rpc_port, {"command": "ping"})
    if response.get("status") == "error" and "No connection" in response.get("message", ""):
        print(f"\nERREUR: {response['message']}")
        return

    while True:
        print("\n" + "="*40)
        print("Menu CLI")
        print("="*40)
        print("1 - Start Mining")
        print("2 - Stop Mining")
        print("3 - Send ")
        print("4 - Create Wallet")
        print("5 - Quit")
        choice = input(">> ")

        response = {}
        if choice == '1':
            response = SendRpcCommand(host, rpc_port, {"command": "start_miner"})
        elif choice == '2':
            response = SendRpcCommand(host, rpc_port, {"command": "stop_miner"})
        elif choice == '3':
            from_addr = input("Sender address: ")
            to_addr = input("Recipient address: ")
            amount = input("Amount in KNL: ")
            command = {"command": "send_tx", "params": {"from": from_addr, "to": to_addr, "amount": amount}}
            response = SendRpcCommand(host, rpc_port, command)
        elif choice == '4':
            wallet_name = input("Enter a name for the new wallet: ")
            if wallet_name:
                response = SendRpcCommand(host, rpc_port, {"command": "create_wallet", "params": {"name": wallet_name}})
                if response.get("status") == 'success':
                    wallet = response.get('wallet', {})
                    print("\n--- Wallet created ---")
                    print(f"  Public Address: {wallet.get('PublicAddress')}")
                    print(f"  Private Key: {wallet.get('privateKey')}")
            else:
                print("Wallet name is required")
        elif choice == '5':
            print("Exiting... Please close the Daemon terminal manually")
            break
        else:
            print("Invalid choice. Please try again...")

        if response and response != {}:
             print(f"\n[DAEMON] -> {response.get('message', 'No message')}")

        input("\nPress Enter to continue...")
        clearScreen()
        printLogo()


if __name__ == "__main__":
    main()