
from src.core.primitives.transaction import Tx
import time
from src.core.kmain.utxo_manager import UTXOManager
from src.core.kmain.mempool import MempoolManager
from src.core.kmain.validator import Validator
from src.core.primitives.block import Block

class ChainManager:
    def __init__(self, blockchain_db, utxo_db, mempool_db, txindex_db, new_block_event):
        self.db = blockchain_db
        self.utxos = utxo_db
        self.mempool = mempool_db
        self.txindex = txindex_db
        self.new_block_event = new_block_event
        self.validator = Validator(self.utxos, self.mempool)
        self.utxo_manager = UTXOManager(self.utxos)
        self.mempool_manager = MempoolManager(self.mempool, self.utxos)

    def process_new_block(self, block_obj):
        block_hash = block_obj.BlockHeader.generateBlockHash()
        if self.db.get_block(block_hash):
            print(f"Block {block_hash[:10]}... already known. Discarding.")
            return False

        if not self.validator.validate_block_header(block_obj.BlockHeader, self.db):
            print(f"Block {block_hash[:10]}... failed header validation. Discarding.")
            return False

        if not self.validator.validate_block_body(block_obj, self.db):
            print(f"Block {block_hash[:10]}... failed body validation. Discarding.")
            return False
        
        block_dict = self.block_to_dict(block_obj)
        self.db.write_block(block_dict) 
        
        print(f"Received valid new block {block_obj.Height} ({block_hash[:10]}...).")
        main_tip_hash = self.db.get_main_chain_tip_hash()
        if not main_tip_hash: 
            print("Processing Genesis block.")
            self.connect_block(block_obj) 
            self.db.set_main_chain_tip(block_hash)
            return True

        main_tip_index = self.db.get_index(main_tip_hash)
        new_block_index = self.db.get_index(block_hash)

        if new_block_index['total_work'] > main_tip_index['total_work']:
            print(f"New block {block_hash[:10]}... has more work. Reorganizing chain.")
            self.reorganize_chain(block_hash)
        else:
            print(f"New block {block_hash[:10]}... is on a fork with less work. Storing.")

        return True

    def reorganize_chain(self, new_tip_hash):
        new_chain = []
        old_chain = []
        
        curr_new_hash = new_tip_hash
        curr_old_hash = self.db.get_main_chain_tip_hash()

        while curr_new_hash != curr_old_hash:
            new_idx = self.db.get_index(curr_new_hash)
            old_idx = self.db.get_index(curr_old_hash)

            if not new_idx: break 

            if not old_idx or new_idx['height'] > old_idx['height']:
                new_chain.append(curr_new_hash)
                curr_new_hash = new_idx['prev_hash']
            elif new_idx['height'] < old_idx['height']:
                old_chain.append(curr_old_hash)
                curr_old_hash = old_idx['prev_hash']
            else: 
                new_chain.append(curr_new_hash)
                old_chain.append(curr_old_hash)
                curr_new_hash = new_idx['prev_hash']
                curr_old_hash = old_idx['prev_hash']
        
        common_ancestor_hash = curr_new_hash
        print(f"Common ancestor is {common_ancestor_hash[:10]}...")

        for block_hash in old_chain:
            print(f"Disconnecting block {block_hash[:10]}...")
            block = Block.to_obj(self.db.get_block(block_hash))
            self.disconnect_block(block)

        for block_hash in reversed(new_chain):
            print(f"Connecting block {block_hash[:10]}...")
            block = Block.to_obj(self.db.get_block(block_hash))
            if not self.connect_block(block):
                print(f"FATAL: Failed to connect block {block_hash} during reorg. Chain state may be corrupt.")
                return

        self.db.set_main_chain_tip(new_tip_hash)
        self.utxos.set_meta('last_block_hash', new_tip_hash)
        self.utxos.commit()
        
        self.new_block_event.set()

    def connect_block(self, block_obj):
        if not self.validator.validate_block_transactions(block_obj, is_in_block=True):
            print(f"Block {block_obj.Height} failed context-full tx validation. Aborting connect.")
            return False
        
        block_hash = block_obj.BlockHeader.generateBlockHash()
        tx_ids_in_block = []

        for tx in block_obj.Txs:
            tx_id = tx.id()
            tx_ids_in_block.append(bytes.fromhex(tx_id))
            self.txindex[tx_id] = block_hash

        spent_outputs = [[tx_in.prev_tx, tx_in.prev_index] for tx in block_obj.Txs[1:] for tx_in in tx.tx_ins]
        
        self.utxo_manager.remove_spent_utxos(spent_outputs)
        self.utxo_manager.add_new_utxos(block_obj.Txs)
        
        self.mempool_manager.remove_transactions(tx_ids_in_block)
        
        print(f"Connected block {block_obj.Height}. UTXOs and mempool updated.")
        return True

    def disconnect_block(self, block_obj):
        for tx in block_obj.Txs:
            tx_id_hex = tx.id()
            if tx_id_hex in self.utxos:
                del self.utxos[tx_id_hex]
            
            if tx_id_hex in self.txindex:
                del self.txindex[tx_id_hex]
 
        for tx in block_obj.Txs[1:]: 
            for tx_in in tx.tx_ins:
                prev_tx_hash = tx_in.prev_tx.hex()
                
                if prev_tx_hash in self.utxos:
                    continue 

                prev_tx_block_dict = self.find_tx_block_in_chain(prev_tx_hash)
                if prev_tx_block_dict:
                    for tx_dict in prev_tx_block_dict['Txs']:
                        if tx_dict['TxId'] == prev_tx_hash:
                            self.utxos[prev_tx_hash] = Tx.to_obj(tx_dict)
                            break
                else:
                    print(f"WARN: Could not find parent tx {prev_tx_hash[:10]}... during disconnect.")

        for tx in block_obj.Txs[1:]:
            tx_id = tx.id()
            if tx_id not in self.mempool:
                if self.validator.validate_transaction(tx):
                    self.mempool[tx_id] = tx
                else:
                    print(f"Orphaned tx {tx_id[:10]}... is no longer valid. Discarding.")
                    
        print(f"Disconnected block {block_obj.Height}. UTXOs restored, txs returned to mempool.")
        return True

    def find_tx_block_in_chain(self, tx_id):
        block_hash = self.txindex.get(tx_id)
        if not block_hash:
            print(f"WARN: Transaction {tx_id[:10]}... not found in txindex")
            return self.find_tx_block_in_chain_slow(tx_id)
        
        block = self.db.get_block(block_hash)
        if not block:
            print(f"FATAL: txindex points to block {block_hash} for tx {tx_id}, but block is not in DB")
            return None
            
        return block
    
    def find_tx_block_in_chain_slow(self, tx_id):
        for block in self.db.read():
            for tx in block.get("Txs", []):
                if tx.get("TxId") == tx_id:
                    return block
        for block_hash in self.db.db.keys():
            block = self.db.get_block(block_hash)
            if not block: continue
            for tx in block.get("Txs", []):
                if tx.get("TxId") == tx_id:
                    return block
        return None

    def block_to_dict(self, block):
        block.BlockHeader.to_hex()
        tx_json_list = [tx.to_dict() for tx in block.Txs]
        return {
            "Height": block.Height, "Blocksize": block.Blocksize,
            "BlockHeader": block.BlockHeader.__dict__, "TxCount": len(tx_json_list),
            "Txs": tx_json_list
        }