from src.utils.serialization import merkle_root
from src.core.primitives.transaction import Tx
from src.core.kmain.pow import check_pow

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


    def validate_block(self, block, db):
        last_block = db.lastBlock()
    
        if last_block and block.Height != last_block['Height'] + 1:
            print(f"Block validation failed (Block {block.Height}): Invalid height, expected {last_block['Height'] + 1}")
            return False
        
        if not check_pow(block.BlockHeader):
            print(f"Block validation failed (Block {block.Height}): Invalid Proof of Work")
            return False
            
        if block.BlockHeader.prevBlockHash.hex() != last_block['BlockHeader']['blockHash']:
            print(f"Block validation failed (Block {block.Height}): Previous hash does not match")
            return False

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

            if not self.validate_transaction(tx, is_in_block=True):
                print(f"Block validation failed (Block {block.Height}): Invalid transaction {tx.id()}")
                return False
        
        return True