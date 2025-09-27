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
#from Blockchain.Frontend.run import main as web_main
from Blockchain.Frontend.api import main as web_main
from Blockchain.client.account import account
from Blockchain.Backend.core.database.database import AccountDB
from Blockchain.client.send import Send
from Blockchain.client.autoBroadcastTX import autoBroadcast

# Create and manage the RPC server for CLI-DAEMON communication
def rpcServer(host, rpcPort, utxos, mempool, miningProcessManager):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, rpcPort))
        s.listen()
        print(f"RPC server start, listening on port {rpcPort}") 
        while True:
            conn, addr = s.accept()
            with conn:
                data = conn.recv(1024)
                if not data:
                    continue
                
                try:
                    command = json.loads(data.decode('utf-8'))
                    response = handleRpcCommand(command, utxos, mempool, miningProcessManager)
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    response = {"status": "error", "message": f"Invalid command format: {e}"}
                except Exception as e:
                    response = {"status": "error", "message": f"An unexpected error occurred: {e}"}

                conn.sendall(json.dumps(response).encode('utf-8'))

 # Handle incoming RPC commands
def handleRpcCommand(command, utxos, mempool, miningProcessManager):
    cmd = command.get('command')
    params = command.get('params', {})
    
    if cmd == 'start_miner':
        miningProcessManager['is_mining'] = True
        return {"status": "success", "message": "Start mining process..."}
    
    elif cmd == 'stop_miner':
        miningProcessManager['is_mining'] = False
        return {"status": "success", "message": "End mining process..."}
        
    elif cmd == 'create_wallet':
        acc = account()
        wallet_data = acc.createKeys()
        AccountDB().write([wallet_data])
        return {"status": "success", "wallet": wallet_data}
        
    elif cmd == 'send_tx':
        send_handler = Send(params['from'], params['to'], float(params['amount']), utxos, mempool)
        tx = send_handler.prepareTransaction()
        if tx:
            mempool[tx.id()] = tx
            # add broadcast tx to peers later
            return {"status": "success", "message": "Transaction added to mempool", "txid": tx.id()} 
        else:
            return {"status": "error", "message": "Failed to create transaction"} 
    else:
        return {"status": "error", "message": "Command not recognized"} 

# Start all the processes: P2P, Web, RPC, Mining 
def mainDaemon(args):
    config = configparser.ConfigParser()
    config.read('config.ini')
    host = config['DEFAULT']['host']
    minerPort = int(config['MINER']['port'])
    webServerPort = int(config['Webhost']['port'])
    rpcPort = webServerPort + 1 
    simulateTX = bool(config['MINER']['simulateTX']) 

    with Manager() as manager:
        utxos = manager.dict()
        mempool = manager.dict()
        newBlockAvailable = manager.dict()
        secondaryChain = manager.dict()
        miningProcessManager = manager.dict({'is_mining': False})

        # Process 1 P2P
        sync = syncManager(host, minerPort, newBlockAvailable, secondaryChain, mempool)
        processServeur = Process(target=sync.spinUpTheServer)
        processServeur.start()
        print(f"P2P server started on port {minerPort}") 

        # Process 2 Web 
        processAPI = Process(target=web_main, args=(utxos, mempool, webServerPort, minerPort))
        processAPI.start()
        print(f"API Web server started on port {webServerPort}")
        
        # Process 3 RPC CLI-DAEMON
        processRPC = Process(target=rpcServer, args=(host, rpcPort, utxos, mempool, miningProcessManager))
        processRPC.start()


        mainBlockchain = Blockchain(utxos, mempool, newBlockAvailable, secondaryChain, host, minerPort)
        print("Initialisation (sync, utxos...)")
        #mainBlockchain.startSync()
        mainBlockchain.buildUTXOS()

        # Auto broadcast process for testing
        #if simulateTX: 
        #    autobroadcastTX = Process(target= autoBroadcast())
        #    autobroadcastTX.start()

        mainBlockchain.settargetWhileBooting()
        
        mining_process = None
        if args.mine:
            miningProcessManager['is_mining'] = True

        try:
            while True:
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
            print("\nShutting down...")
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