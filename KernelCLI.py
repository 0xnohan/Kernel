import socket
import json
import os
import configparser

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

    clearScreen()
    printLogo()

    response = SendRpcCommand(host, rpc_port, {"command": "ping"})
    if response.get("status") == "error" and "Connexion refused" in response.get("message", ""):
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
            response = SendRpcCommand(host, rpc_port, {"command": "create_wallet"})
            if response.get("status") == 'success':
                wallet = response.get('wallet', {})
                print("\n--- Wallet created ---")
                print(f"  Public Address: {wallet.get('PublicAddress')}")
                print(f"  Private Key: {wallet.get('privateKey')}")
        elif choice == '5':
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please try again...")
        
        if response and response != {}:
             print(f"\n[DAEMON LOG] -> {response.get('message', 'No message')}")

        input("\nPress Enter to continue...")
        clearScreen()
        printLogo()

if __name__ == "__main__":
    main()