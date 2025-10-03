class MempoolManager:
    def __init__(self, mempool, utxos):
        self.mempool = mempool
        self.utxos = utxos

    def _is_double_spend(self, tx, block_pending_txs):
        for txin in tx.tx_ins:
            if txin.prev_tx in block_pending_txs:
                return True 
            if txin.prev_tx.hex() not in self.utxos:
                return True 
        return False

    def get_transactions_for_block(self):
        block_size = 80  
        tx_ids_for_block = []
        txs_for_block = []
        spent_utxos_for_block = []
        prev_txs_in_block = [] 
        delete_txs_from_mempool = []
        temp_mempool = dict(self.mempool)

        for tx_id, tx in temp_mempool.items():
            if block_size + len(tx.serialize()) > 1000000: 
                continue

            if not self._is_double_spend(tx, prev_txs_in_block):
                tx.TxId = tx_id
                tx_ids_for_block.append(bytes.fromhex(tx_id))
                txs_for_block.append(tx)
                block_size += len(tx.serialize())
                
                for spent in tx.tx_ins:
                    prev_txs_in_block.append(spent.prev_tx)
                    spent_utxos_for_block.append([spent.prev_tx, spent.prev_index])
            else:
                delete_txs_from_mempool.append(tx_id)

        for tx_id in delete_txs_from_mempool:
            if tx_id in self.mempool:
                del self.mempool[tx_id]

        input_amount = 0
        output_amount = 0

        for tx_id_bytes, output_index in spent_utxos_for_block:
            tx_id_hex = tx_id_bytes.hex()
            if tx_id_hex in self.utxos:
                input_amount += self.utxos[tx_id_hex].tx_outs[output_index].amount

        for tx in txs_for_block:
            for tx_out in tx.tx_outs:
                output_amount += tx_out.amount

        total_fees = input_amount - output_amount

        return {
            "transactions": txs_for_block,
            "tx_ids": tx_ids_for_block,
            "block_size": block_size,
            "fees": total_fees
        }

    def remove_transactions(self, tx_ids):
        """
        Supprime une liste de transactions de la mempool (généralement après qu'elles
        aient été incluses dans un bloc miné).
        """
        for tx_id_bytes in tx_ids:
            tx_id_hex = tx_id_bytes.hex()
            if tx_id_hex in self.mempool:
                del self.mempool[tx_id_hex]