import logging
logger = logging.getLogger(__name__)

import os
import json
import time
from sqlitedict import SqliteDict
from src.utils.serialization import bits_to_target
from src.core.transaction import Tx


class BaseDB:
    def __init__(self):
        self.basepath = "data"
        self.filepath = os.path.join(self.basepath, self.filename)

class BlockchainDB(BaseDB):
    def __init__(self):
        self.basepath = "data"
        self.blocks_db_file = os.path.join(self.basepath, "blockchain.sqlite")
        self.index_db_file = os.path.join(self.basepath, "block_index.sqlite") 
        self.db = SqliteDict(self.blocks_db_file, autocommit=False)
        self.index_db = SqliteDict(self.index_db_file, autocommit=True)
        self.MAIN_TIP_KEY = '_MAIN_CHAIN_TIP'

    def read(self):
        blocks = []
        current_hash = self.get_main_chain_tip_hash()
        
        while current_hash:
            block = self.get_block(current_hash)
            if not block:
                break 
            blocks.append(block)
            current_hash = block['BlockHeader']['prevBlockHash']

            if current_hash == '00' * 32:
                break
                
        return list(reversed(blocks)) 

    def write(self, items):
        try:
            for block_dict in items:
                block_hash = block_dict['BlockHeader']['blockHash']
                self.db[block_hash] = block_dict
                self.write_index(block_hash, block_dict)
                
            self.db.commit() 
        except Exception as e:
            logging.error(f"Error when writing to db: {e}")
            self.db.rollback()
    
    def write_block(self, block_dict):
        try:
            block_hash = block_dict['BlockHeader']['blockHash']
            self.db[block_hash] = block_dict
            self.db.commit()
            self.write_index(block_hash, block_dict)
            return True

        except Exception as e:
            logging.error(f"Error when writing block {block_hash} to db: {e}")
            self.db.rollback()
            return False

    def write_index(self, block_hash, block_dict):
        prev_hash = block_dict['BlockHeader']['prevBlockHash']
        prev_index = self.get_index(prev_hash)
        if prev_index:
            total_work = prev_index['total_work'] + self.calculate_work(block_dict)
        else:
            total_work = self.calculate_work(block_dict) 
        
        index_entry = {
            'hash': block_hash,
            'height': block_dict['Height'],
            'prev_hash': prev_hash,
            'total_work': total_work,
            'status': 'valid-header' 
        }
        self.index_db[block_hash] = index_entry

    def calculate_work(self, block_dict):
        try:
            bits_hex = block_dict['BlockHeader']['bits']
            target = bits_to_target(bytes.fromhex(bits_hex))
            return (2**256) // (target + 1)
        except Exception as e:
            logging.error(f"Error calculating work: {e}. Defaulting to 0")
            return 0
    
    def get_block(self, block_hash):
        return self.db.get(block_hash)

    def get_index(self, block_hash):
        if block_hash == '00' * 32: 
            return None
        return self.index_db.get(block_hash)

    def set_main_chain_tip(self, block_hash):
        self.index_db[self.MAIN_TIP_KEY] = block_hash
        logging.debug(f"New main chain tip set to: {block_hash}")

    def get_main_chain_tip_hash(self):
        return self.index_db.get(self.MAIN_TIP_KEY)

    def update(self, data):
        try:
            self.db.clear() 
            self.db.commit()
            self.index_db.clear()
            self.index_db[self.MAIN_TIP_KEY] = None 
            self.write(data) 

            if data:
                last_block_dict = data[-1]
                last_hash = last_block_dict['BlockHeader']['blockHash']
                self.set_main_chain_tip(last_hash)
            return True
        except Exception as e:
            logging.error(f"Error when updating db: {e}")
            self.db.rollback()
            return False

    def lastBlock(self):
        tip_hash = self.get_main_chain_tip_hash()
        if not tip_hash:
            return None
        return self.get_block(tip_hash)


class UTXODB(BaseDB):
    def __init__(self):
        self.basepath = "data"
        self.db_file = os.path.join(self.basepath, "utxos.sqlite")
        self.db = SqliteDict(self.db_file, autocommit=False) 
        self.meta_key_prefix = '_meta_'

    def get_meta(self, key):
        return self.db.get(f"{self.meta_key_prefix}{key}")

    def set_meta(self, key, value):
        self.db[f"{self.meta_key_prefix}{key}"] = value

    def commit(self):
        self.db.commit()
        
    def clear(self):
        keys_to_delete = [k for k in self.db.keys() if not k.startswith(self.meta_key_prefix)]
        for k in keys_to_delete:
            del self.db[k]

    def __setitem__(self, tx_id_hex, tx_obj):
        self.db[tx_id_hex] = tx_obj.to_dict()

    def __getitem__(self, tx_id_hex):
        tx_dict = self.db.get(tx_id_hex)
        if tx_dict:
            return Tx.to_obj(tx_dict)
        raise KeyError(f"Tx {tx_id_hex} not in UTXO set")

    def __delitem__(self, tx_id_hex):
        if tx_id_hex in self.db:
            del self.db[tx_id_hex]
        else:
            pass

    def __contains__(self, tx_id_hex):
        return tx_id_hex in self.db

    def __len__(self):
        return len([k for k in self.db.keys() if not k.startswith(self.meta_key_prefix)])

    def keys(self):
        return (k for k in self.db.keys() if not k.startswith(self.meta_key_prefix))

    def values(self):
        for k in self.keys():
            yield self[k] # Use __getitem__ to deserialize

    def items(self):
        for k in self.keys():
            yield (k, self[k])

    def get(self, tx_id_hex, default=None):
        try:
            return self[tx_id_hex]
        except KeyError:
            return default

    def get_balances(self, wallet_h160_list):
        balances = {h160.hex(): 0 for h160 in wallet_h160_list}
        wallet_h160_set = set(wallet_h160_list)
        
        for tx_dict in self.db.values():
            if isinstance(tx_dict, dict) and 'tx_outs' in tx_dict:
                for tx_out in tx_dict['tx_outs']:
                    try:
                        pubKeyHash_hex = tx_out['script_pubkey']['cmds'][2]
                        pubKeyHash_bytes = bytes.fromhex(pubKeyHash_hex)
                        if pubKeyHash_bytes in wallet_h160_set:
                            balances[pubKeyHash_hex] += tx_out['amount']
                    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
                        continue
        return balances


class MempoolDB(BaseDB):
    def __init__(self):
        self.basepath = "data"
        self.db_file = os.path.join(self.basepath, "mempool.sqlite")
        self.db = SqliteDict(self.db_file, autocommit=True)

    def __setitem__(self, tx_id_hex, tx_obj):
        store_data = {
            'tx_dict': tx_obj.to_dict(),
            'fee': getattr(tx_obj, 'fee', 0),
            'received_time': getattr(tx_obj, 'receivedTime', time.time())
        }
        self.db[tx_id_hex] = store_data

    def __getitem__(self, tx_id_hex):
        stored = self.db.get(tx_id_hex)
        if not stored:
            raise KeyError(f"Tx {tx_id_hex} not in mempool")
        tx_obj = Tx.to_obj(stored['tx_dict'])
        tx_obj.fee = stored['fee']
        tx_obj.receivedTime = stored['received_time']
        return tx_obj

    def __delitem__(self, tx_id_hex):
        if tx_id_hex in self.db:
            del self.db[tx_id_hex]

    def __contains__(self, tx_id_hex):
        return tx_id_hex in self.db

    def __len__(self):
        return len(self.db)

    def keys(self):
        return self.db.keys()

    def values(self):
        for k in self.keys():
            yield self[k] # Use __getitem__ to deserialize

    def items(self):
        for k in self.keys():
            yield (k, self[k])
            
    def clear(self):
        self.db.clear()
        self.db.commit()


class AccountDB:
    def __init__(self):
        self.basepath = "data"
        self.wallets_dir = os.path.join(self.basepath, "wallets")
        os.makedirs(self.wallets_dir, exist_ok=True)
    
    def get_all_wallets(self):
        wallets = []
        if not os.path.exists(self.wallets_dir):
            return wallets
        for filename in os.listdir(self.wallets_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(self.wallets_dir, filename)
                with open(filepath, "r") as file:
                    wallets.append(json.load(file))
        return wallets
        
    def save_wallet(self, wallet_name, wallet_data):
        filepath = os.path.join(self.wallets_dir, f"{wallet_name}.json")
        if os.path.exists(filepath):
            logging.error(f"Wallet with name '{wallet_name}' already exists")
            return False
        with open(filepath, "w") as file:
            json.dump(wallet_data, file, indent=4)
        return True

class TxIndexDB(BaseDB):
    def __init__(self):
        self.basepath = "data"
        self.db_file = os.path.join(self.basepath, "tx_index.sqlite")
        self.db = SqliteDict(self.db_file, autocommit=True)

    def __setitem__(self, tx_id_hex, block_hash_hex):
        """ Stores tx_id -> block_hash mapping """
        self.db[tx_id_hex] = block_hash_hex

    def __getitem__(self, tx_id_hex):
        """ Retrieves block_hash for a given tx_id """
        return self.db[tx_id_hex]

    def __delitem__(self, tx_id_hex):
        if tx_id_hex in self.db:
            del self.db[tx_id_hex]

    def __contains__(self, tx_id_hex):
        return tx_id_hex in self.db
    
    def get(self, tx_id_hex, default=None):
        return self.db.get(tx_id_hex, default)

    def clear(self):
        self.db.clear()
        self.db.commit()


class NodeDB(BaseDB):
    def __init__(self):
        self.filename = "nodes.json"
        super().__init__()