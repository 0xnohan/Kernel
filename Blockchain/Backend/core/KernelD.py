import sys
import os
import configparser
import argparse
from multiprocessing import Process, Manager
import time
import socket
import json

sys.path.append(os.getcwd())

from Blockchain.Backend.core.blockchain import Blockchain
from Blockchain.Backend.core.network.syncManager import syncManager
from Blockchain.API.serverAPI import main as web_main
from Blockchain.client.account import account
from Blockchain.Backend.core.database.database import AccountDB
from Blockchain.client.send import Send
from Blockchain.Backend.util.util import decode_base58

# --- NOUVELLE FONCTION HELPER ---
def calculate_wallet_balances(wallets, utxos):
    """Calcule le solde de chaque portefeuille en scannant les UTXOs."""
    balances = {wallet.get('PublicAddress'): 0 for wallet in wallets}
    
    for tx_obj in utxos.values():
        if hasattr(tx_obj, 'tx_outs'):
            for tx_out in tx_obj.tx_outs:
                try:
                    # Le pubKeyHash est le 3ème élément dans un script p2pkh
                    pubKeyHash = tx_out.script_pubkey.cmds[2]
                    for wallet in wallets:
                        # On décode l'adresse du portefeuille pour la comparer au hash
                        wallet_h160 = decode_base58(wallet.get('PublicAddress'))
                        if wallet_h160 == pubKeyHash:
                            balances[wallet.get('PublicAddress')] += tx_out.amount
                            break 
                except (AttributeError, IndexError, KeyError):
                    continue
    
    # Ajoute le solde calculé à chaque dictionnaire de portefeuille
    for wallet in wallets:
        balance_knl = balances.get(wallet.get('PublicAddress'), 0) / 100000000
        wallet['balance'] = balance_knl
        
    return wallets

def rpcServer(host, rpcPort, utxos, mempool, miningProcessManager):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, rpcPort))
        s.listen()
        print(f"RPC server started, listening on port {rpcPort}") 
        while True:
            conn, addr = s.accept()
            with conn:
                data = conn.recv(1024)
                if not data:
                    continue
                
                try:
                    command = json.loads(data.decode('utf-8'))
                    response = handleRpcCommand(command, utxos, mempool, miningProcessManager)
                except Exception as e:
                    response = {"status": "error", "message": f"An unexpected error occurred: {e}"}

                conn.sendall(json.dumps(response).encode('utf-8'))

def handleRpcCommand(command, utxos, mempool, miningProcessManager):
    cmd = command.get('command')
    params = command.get('params', {})
    
    if cmd == 'ping':
        return {"status": "success", "message": "pong"}

    elif cmd == 'start_miner':
        miningProcessManager['is_mining'] = True
        return {"status": "success", "message": "Mining process started."}
    
    elif cmd == 'stop_miner':
        miningProcessManager['is_mining'] = False
        return {"status": "success", "message": "Mining process stopped."}
        
    elif cmd == 'create_wallet':
        wallet_name = params.get('name')
        if not wallet_name:
            return {"status": "error", "message": "Wallet name is required"}
        acc = account()
        wallet_data = acc.createKeys(wallet_name)
        if AccountDB().save_wallet(wallet_name, wallet_data):
            return {"status": "success", "message": f"Wallet '{wallet_name}' created.", "wallet": wallet_data}
        else:
            return {"status": "error", "message": f"Wallet '{wallet_name}' already exists."}
        
    elif cmd == 'send_tx':
        send_handler = Send(params['from'], params['to'], float(params['amount']), utxos, mempool)
        tx = send_handler.prepareTransaction()
        if tx:
            mempool[tx.id()] = tx
            return {"status": "success", "message": "Transaction added to mempool", "txid": tx.id()} 
        else:
            return {"status": "error", "message": "Failed to create transaction. Check balance and addresses."} 
    
    # --- COMMANDE MISE À JOUR ---
    elif cmd == 'get_wallets':
        try:
            all_wallets = AccountDB().get_all_wallets()
            # Calcule les soldes avant de renvoyer
            wallets_with_balances = calculate_wallet_balances(all_wallets, utxos)
            return {"status": "success", "wallets": wallets_with_balances}
        except Exception as e:
            return {"status": "error", "message": f"Could not retrieve wallets: {e}"}

    elif cmd == 'get_config':
        config = configparser.ConfigParser()
        config_path = os.path.join('data', 'config.ini')
        config.read(config_path)
        config_dict = {s: dict(config.items(s)) for s in config.sections()}
        return {"status": "success", "config": config_dict}
        
    elif cmd == 'update_config':
        config = configparser.ConfigParser()
        config_path = os.path.join('data', 'config.ini')
        config.read(config_path)
        
        section = params.get('section')
        key = params.get('key')
        value = params.get('value')
        
        if section and key and value is not None:
            if not config.has_section(section):
                config.add_section(section)
            config.set(section, key, str(value))
            with open(config_path, 'w') as configfile:
                config.write(configfile)
            return {"status": "success", "message": f"Config updated: [{section}] {key} = {value}"}
        else:
            return {"status": "error", "message": "Invalid parameters for update_config"}
        
    elif cmd == 'shutdown':
        miningProcessManager['shutdown_requested'] = True
        return {"status": "success", "message": "Daemon shutdown initiated"}
    
    else:
        return {"status": "error", "message": f"Command '{cmd}' not recognized"}

def mainDaemon(args):
    config = configparser.ConfigParser()
    config_path = os.path.join('data', 'config.ini')
    config.read(config_path)
    
    host = config['NETWORK']['host']
    p2p_port = int(config['P2P']['port'])
    api_port = int(config['API']['port'])
    rpc_port = api_port + 1 

    with Manager() as manager:
        utxos = manager.dict()
        mempool = manager.dict()
        newBlockAvailable = manager.dict()
        secondaryChain = manager.dict()
        miningProcessManager = manager.dict({'is_mining': False, 'shutdown_requested': False})

        sync = syncManager(host, p2p_port, newBlockAvailable, secondaryChain, mempool)
        processServeur = Process(target=sync.spinUpTheServer)
        processServeur.start()
        print(f"P2P server started on port {p2p_port}") 

        processAPI = Process(target=web_main, args=(utxos, mempool, api_port, p2p_port))
        processAPI.start()
        print(f"API Web server started on port {api_port}")
        
        processRPC = Process(target=rpcServer, args=(host, rpc_port, utxos, mempool, miningProcessManager))
        processRPC.start()

        mainBlockchain = Blockchain(utxos, mempool, newBlockAvailable, secondaryChain, host, p2p_port)
        print("Initializing blockchain...")
        mainBlockchain.buildUTXOS()
        mainBlockchain.settargetWhileBooting()
        
        mining_process = None
        if args.mine:
            miningProcessManager['is_mining'] = True

        try:
            while not miningProcessManager.get('shutdown_requested', False):
                is_mining = miningProcessManager.get('is_mining', False)
                if is_mining and (mining_process is None or not mining_process.is_alive()):
                    print("Starting mining process...")
                    mining_process = Process(target=mainBlockchain.main) 
                    mining_process.start()
                elif not is_mining and (mining_process and mining_process.is_alive()):
                    print("Stopping mining process...")
                    mining_process.terminate()
                    mining_process.join()
                    mining_process = None
                time.sleep(2)
        except KeyboardInterrupt:
            print("\nShutting down daemon...")
        finally:
            processServeur.terminate()
            processAPI.terminate()
            processRPC.terminate()
            if mining_process and mining_process.is_alive():
                mining_process.terminate()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kernel Daemon")
    parser.add_argument("--mine", action="store_true", help="Start mining on launch")
    args = parser.parse_args()
    mainDaemon(args)