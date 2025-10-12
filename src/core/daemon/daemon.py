import sys
import os
import argparse
from multiprocessing import Process, Manager, Queue
import time

sys.path.append(os.getcwd())

from src.core.kmain.miner import Miner
from src.core.net.sync_manager import SyncManager
from src.api.server import main as web_main
from src.core.daemon.rpc_server import rpcServer
from src.core.kmain.utxo_manager import UTXOManager
from src.core.kmain.mempool import MempoolManager
from src.utils.config_loader import load_config
from threading import Thread
from src.core.kmain.genesis import create_genesis_block
from src.database.db_manager import BlockchainDB
from src.core.kmain.validator import Validator


def handle_mined_blocks(mined_block_queue, sync_manager, utxo_manager, mempool_manager):
    while True:
        mined_block = mined_block_queue.get()
        #print(f"Daemon received mined block {mined_block.Height} from Miner process")
        spent_outputs = []
        for tx in mined_block.Txs[1:]: #Ignore coinbase
            for tx_in in tx.tx_ins:
                spent_outputs.append([tx_in.prev_tx, tx_in.prev_index])
        
        utxo_manager.remove_spent_utxos(spent_outputs)
        utxo_manager.add_new_utxos(mined_block.Txs)
        mempool_manager.remove_transactions([bytes.fromhex(tx.id()) for tx in mined_block.Txs])
        #print("Daemon updated UTXO set and mempool")
        sync_manager.broadcast_block(mined_block)


def handle_new_transactions(new_tx_queue, sync_manager, validator, mempool):
    while True:
        tx = new_tx_queue.get()
        tx_id = tx.id()
        if tx_id in mempool: 
            continue

        #print(f"Daemon received new transaction {tx_id} from RPC")

        if validator.validate_transaction(tx):
            mempool[tx_id] = tx
            print(f"Transaction {tx_id} added to mempool")
            sync_manager.broadcast_tx(tx)
        else:
            print(f"Daemon discarded invalid transaction {tx_id} from RPC")


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
        new_block_available = manager.dict() 
        mining_process_manager = manager.dict({'is_mining': False, 'shutdown_requested': False})
        
        #Miner-Deamon
        mined_block_queue = Queue()
        new_tx_queue = Queue()

        utxo_manager = UTXOManager(utxos)
        mempool_manager = MempoolManager(mempool, utxos)
        sync_manager = SyncManager(host, p2p_port, new_block_available, None, mempool, utxos)
        validator = Validator(utxos, mempool)
        
        # Thread P2P
        p2p_server_thread = Thread(target=sync_manager.spin_up_the_server)
        p2p_server_thread.daemon = True 
        p2p_server_thread.start()
        print(f"P2P server started on port {p2p_port}")
        
        # API
        processAPI = Process(target=web_main, args=(utxos, mempool, api_port, p2p_port))
        processAPI.start()
        print(f"API server started on port {api_port}")
        
        # RPC
        processRPC = Process(target=rpcServer, args=(host, rpc_port, utxos, mempool, mining_process_manager, new_tx_queue))
        processRPC.start()

        # Init
        db = BlockchainDB()
        if not db.lastBlock():
            print("No blockchain found, creating genesis block")
            genesis = create_genesis_block()
            genesis.BlockHeader.to_hex()
            tx_json_list = [tx.to_dict() for tx in genesis.Txs]
            block_to_save = {
                "Height": genesis.Height, "Blocksize": genesis.Blocksize,
                "BlockHeader": genesis.BlockHeader.__dict__, "TxCount": len(tx_json_list),
                "Txs": tx_json_list
            }
            db.write([block_to_save])
            print("Genesis block written to database")

        print("Initializing UTXO set...")
        utxo_manager.build_utxos_from_db()
        
        # Listen to mined block
        block_handler_thread = Thread(target=handle_mined_blocks, args=(mined_block_queue, sync_manager, utxo_manager, mempool_manager))
        block_handler_thread.daemon = True
        block_handler_thread.start()
        
        # Listen to new transactions
        tx_handler_thread = Thread(target=handle_new_transactions, args=(new_tx_queue, sync_manager, validator, mempool))
        tx_handler_thread.daemon = True
        tx_handler_thread.start()
        
        time.sleep(2) 
        
        config = load_config()
        if 'SEED_NODES' in config:
            print("Connecting to seed nodes...")
            for key, address in config['SEED_NODES'].items():
                try:
                    peer_host, peer_port_str = address.split(':')
                    peer_port = int(peer_port_str)
                    sync_manager.connect_to_peer(peer_host, peer_port)
                except Exception as e:
                    print(f"Invalid seed node address format or connection failed: {address} ({e})")
        
        mining_process = None
        if args.mine:
            mining_process_manager['is_mining'] = True

        try:
            while not mining_process_manager.get('shutdown_requested', False):
                is_mining = mining_process_manager.get('is_mining', False)
                if is_mining and (mining_process is None or not mining_process.is_alive()):
                    print("Daemon is starting the Miner process...")
                    miner = Miner(mempool, utxos, new_block_available, mined_block_queue)
                    mining_process = Process(target=miner.run)
                    mining_process.start()
                elif not is_mining and (mining_process and mining_process.is_alive()):
                    print("Daemon is stopping the Miner process...")
                    mining_process.terminate()
                    mining_process.join()
                    mining_process = None
                time.sleep(2)

        except KeyboardInterrupt:
            print("\nShutting down daemon...")
            
        finally:
            if processAPI.is_alive():
                processAPI.terminate()
            if processRPC.is_alive():
                processRPC.terminate()
            if mining_process and mining_process.is_alive():
                mining_process.terminate()

if __name__ == "__main__":
    main()