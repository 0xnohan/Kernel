# src/core/kmain/miner.py

import copy
import time
from multiprocessing import Process

from src.core.primitives.block import Block
from src.core.primitives.blockheader import BlockHeader
from src.database.db_manager import BlockchainDB
from src.core.kmain.mempool import MempoolManager
from src.core.primitives.coinbase_tx import CoinbaseTx
from src.core.kmain.pow import mine
from src.utils.serialization import merkle_root, target_to_bits, bits_to_target

from src.core.kmain.genesis import GENESIS_BITS
from src.core.kmain.constants import (
    VERSION,
    MAX_TARGET,
    RESET_DIFFICULTY_AFTER_BLOCKS,
    AVERAGE_MINE_TIME
)

class Miner:
    def __init__(self, mempool, utxos, new_block_available_flag, mined_block_queue):
        self.mempool = mempool
        self.utxos = utxos
        self.new_block_available = new_block_available_flag
        self.mined_block_queue = mined_block_queue
        self.db = None
        self.mempool_manager = MempoolManager(self.mempool, self.utxos)
        self.bits = GENESIS_BITS
        self.current_target = bits_to_target(self.bits)

    def adjust_target_difficulty(self, block_height):
        last_block = self.db.lastBlock()
        if not last_block: return

        if block_height > 0 and block_height % RESET_DIFFICULTY_AFTER_BLOCKS == 0:
            all_blocks = self.db.read()
            if len(all_blocks) > RESET_DIFFICULTY_AFTER_BLOCKS:
                first_block_in_period = all_blocks[block_height - RESET_DIFFICULTY_AFTER_BLOCKS]
                time_diff = last_block['BlockHeader']['timestamp'] - first_block_in_period['BlockHeader']['timestamp']
                if time_diff == 0: return

                time_ratio = max(0.25, min(4.0, time_diff / AVERAGE_MINE_TIME))
                last_target = bits_to_target(bytes.fromhex(last_block['BlockHeader']['bits']))
                new_target = int(last_target * time_ratio)
                self.bits = target_to_bits(min(new_target, MAX_TARGET))
            else:
                self.bits = bytes.fromhex(last_block['BlockHeader']['bits'])
        else:
            self.bits = bytes.fromhex(last_block['BlockHeader']['bits'])
        self.current_target = bits_to_target(self.bits)

    def run(self):
        self.db = BlockchainDB()
        print("Miner process started.")

        while True:
            last_block = self.db.lastBlock()
            if not last_block:
                print("Miner waiting for genesis block...")
                time.sleep(5)
                continue

            # Interrompre si un bloc externe est arrivé
            if self.new_block_available:
                print("Mining interrupted: a new block was received from the network.")
                self.new_block_available.clear() # On acquitte le signal
                continue

            block_height = last_block["Height"] + 1
            prev_block_hash = last_block["BlockHeader"]["blockHash"]
            
            # 1. Créer le bloc candidat
            block_candidate = self.create_block_template(block_height, prev_block_hash)
            if not block_candidate:
                time.sleep(2)
                continue

            # 2. Lancer la recherche de la preuve de travail
            competition_over, mined_header = mine(block_candidate.BlockHeader, self.current_target, self.new_block_available)

            if competition_over:
                continue
            
            if mined_header:
                print(f"Block {block_height} mined successfully with nonce {mined_header.nonce}!")
                new_block = Block(
                    block_height,
                    block_candidate.Blocksize,
                    mined_header,
                    len(block_candidate.Txs),
                    block_candidate.Txs
                )

                # 3. ÉCRIRE LE BLOC EN BASE DE DONNÉES (logique restaurée)
                # C'est l'étape cruciale pour éviter la race condition.
                mined_header.to_hex()
                tx_json_list = [tx.to_dict() for tx in new_block.Txs]
                block_to_save = {
                    "Height": new_block.Height, "Blocksize": new_block.Blocksize,
                    "BlockHeader": mined_header.__dict__, "TxCount": len(tx_json_list),
                    "Txs": tx_json_list
                }
                self.db.write([block_to_save])
                
                # 4. Envoyer le bloc au daemon (qui n'aura plus qu'à diffuser)
                self.mined_block_queue.put(new_block)

    def create_block_template(self, height, prev_hash):
        block_data = self.mempool_manager.get_transactions_for_block()
        transactions = block_data["transactions"]
        tx_ids = block_data["tx_ids"]
        fees = block_data["fees"]
        block_size = block_data["block_size"]

        coinbase_tx = CoinbaseTx(height).CoinbaseTransaction(fees=fees)
        if not coinbase_tx:
            print("Miner Error: Could not create Coinbase TX. Check wallet config.")
            return None

        block_size += len(coinbase_tx.serialize())
        tx_ids.insert(0, bytes.fromhex(coinbase_tx.id()))
        transactions.insert(0, coinbase_tx)
        
        self.adjust_target_difficulty(height)

        merkle_root_bytes = merkle_root(tx_ids)[::-1]
        
        block_header = BlockHeader(
            version=VERSION,
            prevBlockHash=bytes.fromhex(prev_hash),
            merkleRoot=merkle_root_bytes,
            timestamp=int(time.time()),
            bits=self.bits,
            nonce=0
        )
        return Block(height, block_size, block_header, len(transactions), transactions)