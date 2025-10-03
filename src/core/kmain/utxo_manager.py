from src.database.db_manager import BlockchainDB
from src.core.primitives.transaction import Tx

class UTXOManager:
    def __init__(self, utxos):
        self.utxos = utxos

    def build_utxos_from_db(self):
        all_txs = {}
        blocks = BlockchainDB().read()

        for block in blocks:
            for tx in block['Txs']:
                all_txs[tx['TxId']] = tx

        spent_outputs = set()
        for block in blocks:
            for tx in block['Txs']:
                for txin in tx['tx_ins']:
                    if txin['prev_tx'] != "00" * 32:
                        spent_key = f"{txin['prev_tx']}_{txin['prev_index']}"
                        spent_outputs.add(spent_key)

        self.utxos.clear()

        for tx_id, tx_data in all_txs.items():
            for index, tx_out in enumerate(tx_data['tx_outs']):
                spend_key = f"{tx_id}_{index}"
                if spend_key not in spent_outputs:
                    if tx_id not in self.utxos:
                        self.utxos[tx_id] = Tx.to_obj(tx_data)
                    # Si la Tx est déjà dans les utxos mais avec un autre output, on la garde
                    # (Ce cas est rare mais possible si une Tx a plusieurs outputs non dépensés)

        print(f"UTXO set rebuilt. Found {len(self.utxos)} unspent transactions.")


    def add_new_utxos(self, transactions):
        for tx in transactions:
            self.utxos[tx.TxId] = tx

    def remove_spent_utxos(self, spent_outputs):
        if not spent_outputs:
            return

        for tx_id_bytes, output_index in spent_outputs:
            tx_id_hex = tx_id_bytes.hex()

            if tx_id_hex in self.utxos:
                tx_obj = self.utxos[tx_id_hex]

                if 0 <= output_index < len(tx_obj.tx_outs):
                    # En pratique, on ne supprime pas un output spécifique mais
                    # toute la transaction car ses outputs sont maintenant dépensés.
                    # Une gestion plus fine consisterait à recréer un objet Tx avec
                    # les outputs restants. Pour l'instant, on supprime la clé.
                    del self.utxos[tx_id_hex]
                else:
                    print(f"Warning: Output index {output_index} out of range for Tx {tx_id_hex}.")