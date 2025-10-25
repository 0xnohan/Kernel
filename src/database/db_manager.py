import os
import json
import logging
from .lmdb_manager import LMDBManager  

MAP_SIZE = 10 * 1024 * 1024 * 1024  # 10 Gb

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class BaseDB:
    def __init__(self):
        self.basepath = "data"


class BlockchainDB(BaseDB):
    HEIGHT_KEY_BYTES = 8

    def __init__(self):
        super().__init__() 
        self.db_path = os.path.join(self.basepath, "blockchain.lmdb")
        try:
            self.lmdb_manager = LMDBManager(self.db_path, map_size=MAP_SIZE)
        except Exception as e:
            logging.error(f"Error initializing LMDBManager for BlockchainDB at {self.db_path}: {e}")
            self.lmdb_manager = None 

    def _encode_height(self, height):
        return height.to_bytes(self.HEIGHT_KEY_BYTES, 'big')

    def _decode_height(self, height_bytes):
        return int.from_bytes(height_bytes, 'big')

    def read(self):
        if not self.lmdb_manager:
            return []
        
        blocks_data = self.lmdb_manager.get_all() 
        valid_blocks = []
        for key_bytes, block_dict in blocks_data:
            if isinstance(block_dict, dict) and 'Height' in block_dict:
                if block_dict['Height'] == self._decode_height(key_bytes):
                    valid_blocks.append(block_dict)
                else:
                    logging.warning(f"Non-matching height for key {key_bytes.hex()}: {block_dict['Height']} vs {self._decode_height(key_bytes)}")
                 
            else:
                 logging.warning(f"Invalid block data for key {key_bytes.hex()}: {block_dict}")

        try:
            valid_blocks.sort(key=lambda block: block['Height'])
        except KeyError as e:
             logging.error("Error sorting blocks by Height: {e}")
        
        return valid_blocks


    def write(self, items):
        if not self.lmdb_manager:
            logging.error("Blockchain not initialized, cannot write data")
            return False
            
        success = True
        try:
            for block_dict in items:
                try:
                    height = block_dict['Height']
                    key = self._encode_height(height)
                    if not self.lmdb_manager.put(key, block_dict):
                        logging.error(f"Failed to write block at height {height} to DB")
                        success = False
                except KeyError:
                    logging.error(f"Block dictionary missing 'Height' key: {block_dict}")
                    success = False
                except Exception as e:
                     logging.error(f"Unexpected error writing block {block_dict}: {e}")
                     success = False

            return success
        except Exception as e:
            logging.error(f"Error during write operation to DB: {e}")
            return False

    def update(self, data):
        if not self.lmdb_manager:
            logging.error("DB not initialized, cannot update data")
            return False
            
        if self.lmdb_manager.clear_db():
            return self.write(data)
        else:
            logging.error("Failed to clear DB before update")
            return False

    def lastBlock(self):
        if not self.lmdb_manager:
            logging.error("DB not initialized, cannot retrieve last block")
            return None
            
        key, value = self.lmdb_manager.get_last_key_value()
        
        if key and value:
            if isinstance(value, dict):
                try:
                    decoded_height = self._decode_height(key)
                    if value.get('Height') == decoded_height:
                        return value
                    else:
                        logging.error(f"Height mismatch for last block: key height {decoded_height}, value height {value.get('Height')}")
                        return None #
                except Exception as e:
                     logging.error(f"Error decoding last block height: {e}")
                     return None
            else:
                 logging.error("Last block value is not a dictionary")
                 return None
        elif key is None and value is None:
             return None 
        else:
             logging.error("Error retrieving last block from LMDB")
             return None
        
    def close(self):
        if self.lmdb_manager:
            self.lmdb_manager.close()


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
        if not wallet_name or "/" in wallet_name or "\\" in wallet_name or ".." in wallet_name:
            print(f"Invalid wallet name: '{wallet_name}'")
            return False

        filepath = os.path.join(self.wallets_dir, f"{wallet_name}.json")
        if os.path.exists(filepath):
            print(f"Wallet with name '{wallet_name}' already exists")
            return False
        with open(filepath, "w") as file:
            json.dump(wallet_data, file, indent=4)
        return True

class NodeDB(BaseDB):
    def __init__(self):
        self.filename = "nodes.json"
        super().__init__()