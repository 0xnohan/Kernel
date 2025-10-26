
import sys
import os
from queue import Queue
from threading import Thread, Event
import time

sys.path.append(os.getcwd())

from src.core.net.sync_manager import SyncManager
from src.api.server import main as web_main
from src.core.daemon.rpc_server import rpcServer
from src.core.kmain.utxo_manager import UTXOManager
from src.utils.config_loader import load_config
from src.core.kmain.genesis import create_genesis_block
from src.database.db_manager import BlockchainDB
from src.core.kmain.validator import Validator


def handle_broadcasts(broadcast_queue, sync_manager, new_block_event):
    while True:
        block_to_broadcast = broadcast_queue.get()
        if block_to_broadcast and sync_manager:
            sync_manager.broadcast_block(block_to_broadcast)
            new_block_event.set()


def handle_new_transactions(new_tx_queue, sync_manager, validator, mempool):
    while True:
        tx = new_tx_queue.get()
        tx_id = tx.id()
        if tx_id in mempool: 
            continue

        if validator.validate_transaction(tx):
            mempool[tx_id] = tx
            print(f"Transaction {tx_id} added to mempool")
            sync_manager.broadcast_tx(tx)
        else:
            print(f"Daemon discarded invalid transaction {tx_id} from RPC")


def main():
    config = load_config()
    
    host = config['NETWORK']['host']
    p2p_port = int(config['P2P']['port'])
    api_port = int(config['API']['port'])
    rpc_port = api_port + 1

    utxos = {}
    mempool = {}
    mining_process_manager = {'shutdown_requested': False}
    
    new_tx_queue = Queue()
    broadcast_queue = Queue()
    new_block_event = Event()

    utxo_manager = UTXOManager(utxos)
    sync_manager = SyncManager(host, p2p_port, new_block_event, None, mempool, utxos)
    validator = Validator(utxos, mempool)

    # Thread P2P
    p2p_server_thread = Thread(target=sync_manager.spin_up_the_server)
    p2p_server_thread.daemon = True 
    p2p_server_thread.start()
    print(f"P2P server started on port {p2p_port}")
    
    # API
    api_thread = Thread(target=web_main, args=(utxos, mempool, api_port, p2p_port))
    api_thread.daemon = True 
    api_thread.start()
    print(f"API server started on port {api_port}")
    
    # RPC
    rpc_thread = Thread(target=rpcServer, args=(host, rpc_port, utxos, mempool, mining_process_manager, new_tx_queue, broadcast_queue, new_block_event))
    rpc_thread.daemon = True 
    rpc_thread.start()

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
    
    # Listen to new transactions
    tx_handler_thread = Thread(target=handle_new_transactions, args=(new_tx_queue, sync_manager, validator, mempool))
    tx_handler_thread.daemon = True
    tx_handler_thread.start()

    broadcast_handler_thread = Thread(target=handle_broadcasts, args=(broadcast_queue, sync_manager, new_block_event))
    broadcast_handler_thread.daemon = True
    broadcast_handler_thread.start()
    
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
    
    try:
        while not mining_process_manager.get('shutdown_requested', False):
            time.sleep(2)

    except KeyboardInterrupt:
        print("\nShutting down daemon...")

if __name__ == "__main__":
    main()