from src.utils.serialization import merkle_root
from src.core.primitives.transaction import Tx
from src.core.kmain.pow import check_pow

class Validator:
    def __init__(self, utxos, mempool):
        self.utxos = utxos
        self.mempool = mempool

    def validate_transaction(self, tx: Tx, is_in_block=False):
        tx_id = tx.id()

        input_sum = 0
        for tx_in in tx.tx_ins:
            prev_tx_hex = tx_in.prev_tx.hex()
            
            if prev_tx_hex not in self.utxos:
                print(f"Validation Error (tx: {tx_id[:10]}...): Previous tx {prev_tx_hex} not in UTXO set.")
                return False
            
            if not is_in_block:
                for mempool_tx in self.mempool.values():
                    for mempool_tx_in in mempool_tx.tx_ins:
                        if mempool_tx_in.prev_tx == tx_in.prev_tx and mempool_tx_in.prev_index == tx_in.prev_index:
                            print(f"Validation Error (tx: {tx_id[:10]}...): Double spend attempt in mempool.")
                            return False
            
            prev_tx_obj = self.utxos.get(prev_tx_hex)
            if tx_in.prev_index >= len(prev_tx_obj.tx_outs):
                print(f"Validation Error (tx: {tx_id[:10]}...): Invalid output index for tx {prev_tx_hex}.")
                return False
            
            input_sum += prev_tx_obj.tx_outs[tx_in.prev_index].amount

        output_sum = sum(tx_out.amount for tx_out in tx.tx_outs)
        if output_sum > input_sum:
            print(f"Validation Error (tx: {tx_id[:10]}...): Output amount ({output_sum}) exceeds input amount ({input_sum}).")
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
        """Valide un bloc de manière exhaustive."""
        last_block = db.lastBlock()
        
        # --- AMÉLIORATION APPORTÉE ICI ---
        # 1. Vérifier si le bloc n'est pas ancien ou déjà connu
        if last_block and block.Height <= last_block['Height']:
            # print(f"Block validation skipped (Block {block.Height}): Already have this or a newer block.")
            return False

        # 2. Valider le header (PoW et lien avec la chaîne)
        if not check_pow(block.BlockHeader):
            print(f"Block validation failed (Block {block.Height}): Invalid Proof of Work.")
            return False
            
        if block.BlockHeader.prevBlockHash.hex() != last_block['BlockHeader']['blockHash']:
            print(f"Block validation failed (Block {block.Height}): Previous hash does not match.")
            return False

        # 3. Valider la Merkle Root
        tx_ids = [bytes.fromhex(tx.id()) for tx in block.Txs]
        calculated_merkle_root = merkle_root(tx_ids)[::-1]
        
        if calculated_merkle_root != block.BlockHeader.merkleRoot:
            print(f"Block validation failed (Block {block.Height}): Merkle root mismatch.")
            return False

        # 4. Valider toutes les transactions dans le bloc (sauf la coinbase)
        for tx in block.Txs[1:]:
            if not self.validate_transaction(tx, is_in_block=True):
                print(f"Block validation failed (Block {block.Height}): Invalid transaction {tx.id()}.")
                return False
        
        return True