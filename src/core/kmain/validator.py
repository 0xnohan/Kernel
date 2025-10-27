from src.utils.serialization import merkle_root
from src.core.primitives.transaction import Tx
from src.utils.crypto_hash import hash256
from src.utils.serialization import little_endian_to_int, bits_to_target

def check_pow(block_header):
    sha = hash256(block_header.serialize())
    proof = little_endian_to_int(sha)
    return proof < bits_to_target(block_header.bits)

class Validator:
    def __init__(self, utxos, mempool):
        self.utxos = utxos
        self.mempool = mempool


    def validate_transaction(self, tx: Tx, is_in_block=False):
        tx_id = tx.id()
        if tx.is_coinbase():
            return True

        input_sum = 0
        for tx_in in tx.tx_ins:
            prev_tx_hex = tx_in.prev_tx.hex()
            
            if not is_in_block:
                if tx_id in self.mempool:
                    print(f"Validation Error (tx: {tx_id}): Transaction already in mempool")
                    return False
                
                for mempool_tx in self.mempool.values():
                    for mempool_tx_in in mempool_tx.tx_ins:
                        if mempool_tx_in.prev_tx == tx_in.prev_tx and mempool_tx_in.prev_index == tx_in.prev_index:
                            print(f"Validation Error (tx: {tx_id}): Double spend attempt in mempool")
                            return False
                        
            if prev_tx_hex not in self.utxos:
                print(f"Validation Error (tx: {tx_id}): Previous tx {prev_tx_hex} not in UTXO set")
                return False
            
            prev_tx_obj = self.utxos.get(prev_tx_hex)
            if tx_in.prev_index >= len(prev_tx_obj.tx_outs):
                print(f"Validation Error (tx: {tx_id}): Invalid output index for tx {prev_tx_hex}")
                return False
            
            input_sum += prev_tx_obj.tx_outs[tx_in.prev_index].amount

        output_sum = sum(tx_out.amount for tx_out in tx.tx_outs)
        if output_sum > input_sum:
            print(f"Validation Error (tx: {tx_id}): Output amount ({output_sum}) exceeds input amount ({input_sum})")
            return False

        for i, tx_in in enumerate(tx.tx_ins):
            prev_tx_obj = self.utxos[tx_in.prev_tx.hex()]
            output_to_spend = prev_tx_obj.tx_outs[tx_in.prev_index]
            script_pubkey = output_to_spend.script_pubkey
            
            if not tx.verify_input(i, script_pubkey):
                print(f"Validation Error (tx: {tx_id[:10]}...): Signature verification failed for input {i}.")
                return False
        return True


    def validate_block_header(self, block_header, db):
        if not check_pow(block_header):
            print(f"Header validation failed: Invalid Proof of Work")
            return False
        
        prev_hash = block_header.prevBlockHash.hex()
        if prev_hash != '00' * 32 and not db.get_index(prev_hash):
            print(f"Header validation failed: Previous hash {prev_hash[:10]}... is unknown.")
            return False
            
        # TODO: Add timestamp check (e.g., not after 2 hours in future)
        return True

    def validate_block_body(self, block, db):
        tx_ids = [bytes.fromhex(tx.id()) for tx in block.Txs]
        calculated_merkle_root = merkle_root(tx_ids)[::-1]
        
        if calculated_merkle_root != block.BlockHeader.merkleRoot:
            print(f"Block validation failed (Block {block.Height}): Merkle root mismatch")
            return False

        spent_utxos_in_block = set()
        for tx in block.Txs[1:]: 
            for tx_in in tx.tx_ins:
                utxo_id = f"{tx_in.prev_tx.hex()}_{tx_in.prev_index}"
                if utxo_id in spent_utxos_in_block:
                    print(f"Block validation failed (Block {block.Height}): Double spend inside the same block for UTXO {utxo_id}")
                    return False
                spent_utxos_in_block.add(utxo_id)
        
        # TODO: Check coinbase transaction rules (e.g., correct reward, script format)
        # TODO: Check block size against MAX_BLOCK_SIZE constant
        
        return True

    def validate_block_transactions(self, Txs, is_in_block=True):
        for tx in Txs[1:]: 
            if not self.validate_transaction(tx, is_in_block=True):
                print(f"Block connection failed: Invalid transaction {tx.id()}")
                return False
        return True