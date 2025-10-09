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
from src.utils.config_loader import load_config
from threading import Thread

def main():
    parser = argparse.ArgumentParser(description="Kernel Daemon")
    parser.add_argument("--mine", action="store_true", help="Start mining on launch")
    args = parser.parse_args()

    config = load_config()
    
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

        # P2P Sync Manager
        sync = syncManager(host, p2p_port, newBlockAvailable, secondaryChain, mempool)
        
        # P2P Server Thread
        P2PserverThread = Thread(target=sync.spinUpTheServer)
        P2PserverThread.daemon = True 
        P2PserverThread.start()
        print(f"P2P server started on port {p2p_port}")

        # API Process
        processAPI = Process(target=web_main, args=(utxos, mempool, api_port, p2p_port))
        processAPI.start()
        print(f"API server started on port {api_port}")
        
        # RPC Process
        processRPC = Process(target=rpcServer, args=(host, rpc_port, utxos, mempool, miningProcessManager))
        processRPC.start()

        # Init UTXO set
        utxo_manager = UTXOManager(utxos)
        print("Initializing UTXO set...")
        utxo_manager.build_utxos_from_db()
        
        # Init Blockchain
        mainBlockchain = Blockchain(utxos, mempool, newBlockAvailable, secondaryChain, host, p2p_port)
        if not mainBlockchain.fetch_last_block():
            mainBlockchain.GenesisBlock()
            
        mainBlockchain.settargetWhileBooting()
        time.sleep(2) 
        config = load_config()
        if 'SEED_NODES' in config:
            print("Connecting to seed nodes...")
            for key, address in config['SEED_NODES'].items():
                try:
                    peer_host, peer_port_str = address.split(':')
                    peer_port = int(peer_port_str)
                    # Use the main sync manager instance to connect
                    conn_thread = Thread(target=sync.connect_to_peer, args=(peer_host, peer_port))
                    conn_thread.start()
                except Exception as e:
                    print(f"Invalid seed node address format or connection failed: {address} ({e})")
        
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
            processAPI.terminate()
            processRPC.terminate()
            if mining_process and mining_process.is_alive():
                mining_process.terminate()

if __name__ == "__main__":
    main()