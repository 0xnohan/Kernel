import sys
import os
import configparser
import argparse
from multiprocessing import Process, Manager
import time

sys.path.append(os.getcwd())

from src.core.kmain.chain import Blockchain
from src.core.net.sync_manager import syncManager
from src.api.server import main as web_main 
from src.core.daemon.rpc_server import rpcServer
from src.core.kmain.utxo_manager import UTXOManager 


def main():
    parser = argparse.ArgumentParser(description="Kernel Daemon")
    parser.add_argument("--mine", action="store_true", help="Start mining on launch")
    args = parser.parse_args()

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

        # P2P
        sync = syncManager(host, p2p_port, newBlockAvailable, secondaryChain, mempool)
        processServeur = Process(target=sync.spinUpTheServer)
        processServeur.start()
        print(f"P2P server started on port {p2p_port}")

        # API
        processAPI = Process(target=web_main, args=(utxos, mempool, api_port, p2p_port))
        processAPI.start()
        print(f"API server started on port {api_port}")
        
        # RPC
        processRPC = Process(target=rpcServer, args=(host, rpc_port, utxos, mempool, miningProcessManager))
        processRPC.start()

        # Init
        utxo_manager = UTXOManager(utxos)
        print("Initializing UTXO set...")
        utxo_manager.build_utxos_from_db()
        
        mainBlockchain = Blockchain(utxos, mempool, newBlockAvailable, secondaryChain, host, p2p_port)
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
    main()