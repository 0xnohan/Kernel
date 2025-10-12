import socket
import time
from src.core.primitives.block import Block
from src.core.net.connection import Node
from src.database.db_manager import BlockchainDB
from src.core.primitives.transaction import Tx
from src.core.net.protocol import NetworkEnvelope
from src.core.kmain.validator import Validator
from src.core.kmain.utxo_manager import UTXOManager
from src.core.kmain.mempool import MempoolManager
from src.core.kmain.pow import check_pow
from src.core.kmain.constants import MAX_HEADERS_TO_SEND, PING_INTERVAL
from threading import Thread, Lock, RLock
from src.core.net.messages import (
    Version, VerAck, GetAddr, Addr,
    GetHeaders, Headers, Inv, GetData, 
    Tx, Block, Ping, Pong,
    INV_TYPE_TX, INV_TYPE_BLOCK
)

class SyncManager:
    def __init__(self, host, port, newBlockAvailable=None, secondaryChain=None, mempool=None, utxos=None):
        self.host = host
        self.port = port
        self.newBlockAvailable = newBlockAvailable
        self.secondaryChain = secondaryChain
        self.mempool = mempool
        self.utxos = utxos

        self.validator = Validator(self.utxos, self.mempool)
        self.db = BlockchainDB()
        
        self.utxo_manager = UTXOManager(self.utxos)
        self.mempool_manager = MempoolManager(self.mempool, self.utxos)

        self.peer_handshake_status = {}
        self.peers = {} 
        self.peers_lock = RLock()
        
        self.last_ping_sent = {}
        self.sync_lock = Lock()
        self.is_syncing = False


    def send_message(self, sock, message):
        envelope = NetworkEnvelope(message.command, message.serialize())
        sock.sendall(envelope.serialize()) 
        print(f"-> Sent {message.command.decode()} to {sock.getpeername()}")


    def connect_to_peer(self, host, port):
        peer_id = f"{host}:{port}"
        with self.peers_lock:
            if peer_id in self.peers or (self.host == host and self.port == port):
                return
        try:
            peer_node = Node(host, port)
            client_socket = peer_node.connect(self.port)

            last_block = self.db.lastBlock()
            start_height = last_block['Height'] if last_block else 0
            version_msg = Version(start_height=start_height)
            self.send_message(client_socket, version_msg)

            handler_thread = Thread(target=self.handle_connection, args=(client_socket, (host, port)))
            handler_thread.daemon = True
            handler_thread.start()

        except Exception as e:
            print(f"Failed to connect to peer {peer_id}. Error: {e}")

    def start_ping_thread(self):
        def ping_peers():
            while True:
                with self.peers_lock:
                    for peer_id, conn in list(self.peers.items()):
                        if time.time() - self.last_ping_sent.get(peer_id, 0) > 60:
                            try:
                                ping_msg = Ping()
                                self.send_message(conn, ping_msg)
                                self.last_ping_sent[peer_id] = time.time()
                            except Exception as e:
                                print(f"Failed to send ping to {peer_id}: {e}")
                time.sleep(PING_INTERVAL)

        ping_thread = Thread(target=ping_peers)
        ping_thread.daemon = True
        ping_thread.start()

    def spin_up_the_server(self):
        self.server = Node(self.host, self.port)
        self.server.startServer()
        print(f"[LISTENING] at {self.host}:{self.port}")

        self.start_ping_thread()

        while True:
            conn, addr = self.server.acceptConnection()
            handler_thread = Thread(target=self.handle_connection, args=(conn, addr))
            handler_thread.daemon = True
            handler_thread.start()


    def handle_connection(self, conn, addr):
        peer_id_str = f"{addr[0]}:{addr[1]}"
        print(f"Handling new connection from {peer_id_str}")
        
        with self.peers_lock:
            self.peers[peer_id_str] = conn
            
        try:
            stream = conn.makefile('rb', None)
            
            while True:
                try:
                    envelope = NetworkEnvelope.parse(stream)
                    command = envelope.command.decode()
                    
                    if command == Version.command.decode():
                        peer_version = Version.parse(envelope.stream())
                        print(f"Peer {peer_id_str} version: {peer_version.version}, height: {peer_version.start_height}")
                        if self.peer_handshake_status.get(peer_id_str) is None:
                            last_block = self.db.lastBlock()
                            start_height = last_block['Height'] if last_block else 0
                            version_msg = Version(start_height=start_height)
                            self.send_message(conn, version_msg)
                        verack_msg = VerAck()
                        self.send_message(conn, verack_msg)
                        self.peer_handshake_status[peer_id_str] = {'version_received': True, 'verack_received': False}

                    elif command == VerAck.command.decode():
                        if peer_id_str in self.peer_handshake_status and self.peer_handshake_status[peer_id_str]['version_received']:
                            self.peer_handshake_status[peer_id_str]['verack_received'] = True
                            print(f"Handshake complete with {peer_id_str}. Connection established.")
                            self.start_sync(conn)

                    elif command == GetHeaders.command.decode():
                        getheaders_msg = GetHeaders.parse(envelope.stream())
                        self.handle_getheaders(conn, getheaders_msg)

                    elif command == Headers.command.decode():
                        headers_msg = Headers.parse(envelope.stream())
                        self.handle_headers(conn, headers_msg)

                    elif command == Block.command.decode():
                        block_obj = Block.parse(envelope.stream())
                        self.handle_block(block_obj, origin_peer_socket=conn)
                    
                    elif command == Inv.command.decode():
                        inv_msg = Inv.parse(envelope.stream())
                        self.handle_inv(conn, inv_msg)
                    
                    elif command == GetData.command.decode():
                        getdata_msg = GetData.parse(envelope.stream())
                        self.handle_getdata(conn, getdata_msg)

                    elif command == Tx.command.decode():
                        tx_obj = Tx.parse(envelope.stream())
                        self.handle_tx(tx_obj, origin_peer_socket=conn)
                    
                    elif command == GetAddr.command.decode():
                        known_peers = []
                        with self.peers_lock:
                            for peer_id in self.peers:
                                host, port_str = peer_id.rsplit(':', 1)
                                known_peers.append((host, int(port_str)))
                        addr_msg = Addr(known_peers)
                        self.send_message(conn, addr_msg)

                    elif command == Addr.command.decode():
                        addr_message = Addr.parse(envelope.stream())
                        for new_host, new_port in addr_message.addresses:
                            self.connect_to_peer(new_host, new_port)
                    
                    elif command == Ping.command.decode():
                        ping_msg = Ping.parse(envelope.stream())
                        pong_msg = Pong(ping_msg.nonce)
                        self.send_message(conn, pong_msg)
                    
                    elif command == Pong.command.decode():
                        pong_msg = Pong.parse(envelope.stream())
                        #print(f"Received pong from {peer_id_str} with nonce {pong_msg.nonce}")

                except (RuntimeError, ValueError, IndexError) as e:
                    print(f"Error message from {peer_id_str}: {e}. Discarding message and continuing")
                    continue

        except (IOError, ConnectionResetError, socket.timeout) as e:
            print(f"Connection lost with peer {peer_id_str}. Reason: {e}")
        except Exception as e:
            print(f"An error occurred with peer {peer_id_str}. Error: {e}")
        finally:
            self.cleanup_peer_connection(peer_id_str, conn)


    def start_sync(self, conn):
        with self.sync_lock:
            if self.is_syncing:
                return
            self.is_syncing = True
        
        print("Starting blockchain synchronization...")
        last_block = self.db.lastBlock()
        
        if not last_block:
            from src.core.kmain.genesis import GENESIS_BLOCK_HASH
            start_block_hash = bytes.fromhex(GENESIS_BLOCK_HASH)
        else:
            start_block_hash = bytes.fromhex(last_block['BlockHeader']['blockHash'])
        
        getheaders_msg = GetHeaders(start_block=start_block_hash)
        self.send_message(conn, getheaders_msg)


    def handle_getheaders(self, conn, getheaders_msg):
        print(f"Received getheaders request starting from {getheaders_msg.start_block.hex()}")
        all_blocks = self.db.read()
        headers_to_send = []
        found_start = False
        
        if not all_blocks and getheaders_msg.start_block.hex() == '00'*32:
            found_start = True

        for block_data in all_blocks:
            if not found_start and block_data['BlockHeader']['blockHash'] == getheaders_msg.start_block.hex():
                found_start = True
                continue
            
            if found_start:
                header = Block.to_obj(block_data).BlockHeader
                headers_to_send.append(header)
                if len(headers_to_send) >= MAX_HEADERS_TO_SEND:
                    break
        
        if headers_to_send:
            print(f"Sending {len(headers_to_send)} headers to peer")
            headers_msg = Headers(headers_to_send)
            self.send_message(conn, headers_msg)


    
    def handle_headers(self, conn, headers_msg):
        if not headers_msg.headers:
            print("Finished headers synchronization")
            with self.sync_lock:
                self.is_syncing = False
            return

        last_known_block = self.db.lastBlock()
        prev_block_hash = last_known_block['BlockHeader']['blockHash']
        
        headers_to_request = []
        for header in headers_msg.headers:
            if header.prevBlockHash.hex() != prev_block_hash:
                print("Header validation failed: Discontinuity in chain")
                return
            if not check_pow(header):
                print("Header validation failed: Invalid Proof of Work")
                return
            
            headers_to_request.append(header)
            prev_block_hash = header.generateBlockHash()

        if headers_to_request:
            items_to_get = [(INV_TYPE_BLOCK, bytes.fromhex(h.generateBlockHash())) for h in headers_to_request]
            getdata_msg = GetData(items_to_get)
            self.send_message(conn, getdata_msg)


    def handle_inv(self, conn, inv_msg):
        items_to_get = []
        for item_type, item_hash in inv_msg.items:
            if item_type == INV_TYPE_TX:
                if item_hash.hex() not in self.mempool:
                    items_to_get.append((INV_TYPE_TX, item_hash))
            elif item_type == INV_TYPE_BLOCK:
                block_exists = False
                all_blocks = self.db.read()
                for block_data in all_blocks:
                    if block_data['BlockHeader']['blockHash'] == item_hash.hex():
                        block_exists = True
                        break
                if not block_exists:
                    items_to_get.append((INV_TYPE_BLOCK, item_hash))
        
        if items_to_get:
            getdata_msg = GetData(items_to_get)
            self.send_message(conn, getdata_msg)


    def handle_getdata(self, conn, getdata_msg):
        for item_type, item_hash in getdata_msg.items:
            if item_type == INV_TYPE_TX:
                tx_id = item_hash.hex()
                if tx_id in self.mempool:
                    tx_obj = self.mempool[tx_id]
                    tx_msg = Tx(tx_obj.version, tx_obj.tx_ins, tx_obj.tx_outs, tx_obj.locktime)
                    self.send_message(conn, tx_msg)
            elif item_type == INV_TYPE_BLOCK:
                block_hash_hex = item_hash.hex()
                all_blocks = self.db.read()
                for block_data in all_blocks:
                    if block_data['BlockHeader']['blockHash'] == block_hash_hex:
                        block_obj = Block.to_obj(block_data)
                        block_msg = Block(block_obj.Height, block_obj.Blocksize, block_obj.BlockHeader, block_obj.Txcount, block_obj.Txs)
                        self.send_message(conn, block_msg)
                        break

    def handle_tx(self, tx_obj, origin_peer_socket=None):
        tx_id = tx_obj.id()
        if tx_id in self.mempool:
            return

        if self.validator.validate_transaction(tx_obj):
            print(f"Transaction {tx_id[:10]}... is valid. Adding to mempool")
            self.mempool[tx_id] = tx_obj
            self.broadcast_tx(tx_obj, origin_peer_socket)
        else:
            print(f"Transaction {tx_id[:10]}... is invalid. Discarding")

    def handle_block(self, block_obj, origin_peer_socket=None):
        block_hash = block_obj.BlockHeader.generateBlockHash()
        print(f"Received block {block_obj.Height} ({block_hash[:10]}...). Validating...")
        
        if self.validator.validate_block(block_obj, self.db):
            block_obj.BlockHeader.to_hex()
            tx_json_list = [tx.to_dict() for tx in block_obj.Txs]
            block_to_save = {
                "Height": block_obj.Height,
                "Blocksize": block_obj.Blocksize,
                "BlockHeader": block_obj.BlockHeader.__dict__,
                "TxCount": block_obj.Txcount,
                "Txs": tx_json_list
            }
            self.db.write([block_to_save])
            print(f"Block {block_obj.Height} successfully added to the blockchain")
            
            spent_outputs = []
            for tx in block_obj.Txs[1:]:
                for tx_in in tx.tx_ins:
                    spent_outputs.append([tx_in.prev_tx, tx_in.prev_index])
            
            self.utxo_manager.remove_spent_utxos(spent_outputs)
            self.utxo_manager.add_new_utxos(block_obj.Txs)
            print(f"UTXO set updated after processing block {block_obj.Height}")

            tx_ids_in_block = [bytes.fromhex(tx.id()) for tx in block_obj.Txs]
            self.mempool_manager.remove_transactions(tx_ids_in_block)
            print(f"Mempool cleaned after processing block {block_obj.Height}")
            
            self.broadcast_block(block_obj, origin_peer_socket)
            
            if self.newBlockAvailable is not None:
                self.newBlockAvailable.clear() 
                self.newBlockAvailable[block_hash] = block_obj
        else:
            print(f"Block {block_obj.Height} is invalid. Discarding")

    def cleanup_peer_connection(self, peer_id, conn):
        if conn:
            conn.close()
        with self.peers_lock:
            if peer_id in self.peers:
                del self.peers[peer_id]
        if peer_id in self.peer_handshake_status:
            del self.peer_handshake_status[peer_id]
        print(f"Connection with {peer_id} closed and cleaned up")

    def broadcast_inv(self, inv_msg, origin_peer_socket=None):
        with self.peers_lock:
            peers_sockets = list(self.peers.values())
        for peer_socket in peers_sockets:
            if peer_socket != origin_peer_socket:
                try:
                    self.send_message(peer_socket, inv_msg)
                except Exception:
                    pass

    def broadcast_tx(self, tx_obj, origin_peer_socket=None):
        tx_hash = bytes.fromhex(tx_obj.id())
        inv_msg = Inv(items=[(INV_TYPE_TX, tx_hash)])
        print(f"Broadcasting transaction {tx_obj.id()[:10]}...")
        self.broadcast_inv(inv_msg, origin_peer_socket)

    def broadcast_block(self, block_obj, origin_peer_socket=None):
        block_hash = bytes.fromhex(block_obj.BlockHeader.generateBlockHash())
        inv_msg = Inv(items=[(INV_TYPE_BLOCK, block_hash)])
        print(f"Broadcasting block {block_obj.Height}...")
        self.broadcast_inv(inv_msg, origin_peer_socket)