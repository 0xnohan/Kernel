from src.utils.serialization import decode_base58
from src.core.primitives.script import Script
from src.core.primitives.transaction import TxIn, TxOut, Tx
from src.database.db_manager import AccountDB
from src.utils.elleptic_curve import PrivateKey

class Send:
    def __init__(self, fromAccount, toAccount, Amount_float, UTXOS, MEMPOOL):
        self.COIN = 100000000
        self.FromPublicAddress = fromAccount
        self.toAccount = toAccount
        self.utxos = UTXOS
        self.mempool = MEMPOOL 
        self.isBalanceEnough = True

        if isinstance(Amount_float, (int, float)) and Amount_float > 0:
            self.Amount = int(Amount_float * self.COIN)
        else:
            self.Amount = 0
            self.isBalanceEnough = False
            print(f"Error: Invalid amount ({Amount_float}) passed to SendBTC.")

    def scriptPubKey(self, PublicAddress):
        h160 = decode_base58(PublicAddress)
        script_pubkey = Script().p2pkh_script(h160)
        return script_pubkey

    def getPrivateKey(self):
        AllAccounts = AccountDB().get_all_wallets()
        if not AllAccounts:
             print("Error: Could not read accounts.")
             return None
        for account in AllAccounts:
            if account.get("PublicAddress") == self.FromPublicAddress:
                return account.get("privateKey")
        print(f"Error: Private key not found for address {self.FromPublicAddress}")
        return None

    def prepareTxIn(self):
        TxIns = []
        self.Total = 0 
        amount_needed_kernel = self.Amount

        # 1. Obtenir le script pubkey de l'expéditeur
        try:
            self.From_address_script_pubkey = self.scriptPubKey(self.FromPublicAddress)
            self.fromPubKeyHash = self.From_address_script_pubkey.cmds[2]
        except Exception as e:
            print(f"Error creating scriptPubKey for sender: {e}")
            self.isBalanceEnough = False
            return []

        # 2. Créer l'ensemble des UTXOs déjà dépensés dans le MEMPOOL
        mempool_spent_utxos = set()
        try:
            current_mempool = dict(self.mempool)
            print(f"DEBUG: Checking {len(current_mempool)} transactions in mempool for spent UTXOs.")
            for txid_mem, tx_mem_obj in current_mempool.items():
                # S'assurer que tx_mem_obj a bien des tx_ins
                if hasattr(tx_mem_obj, 'tx_ins'):
                    for tx_in_mem in tx_mem_obj.tx_ins:
                        utxo_id = f"{tx_in_mem.prev_tx.hex()}_{tx_in_mem.prev_index}"
                        mempool_spent_utxos.add(utxo_id)
            print(f"DEBUG: Found {len(mempool_spent_utxos)} UTXOs spent in mempool.")
        except Exception as e:
            print(f"Error processing mempool to find spent UTXOs: {e}")

        # 3. Copier les UTXOs confirmés
        confirmed_utxos = {}
        try:
            confirmed_utxos = dict(self.utxos)
        except Exception as e:
            print(f"Error converting managed UTXOS dict to normal dict: {e}")
            self.isBalanceEnough = False
            return []

        if not confirmed_utxos:
             print("No confirmed UTXOs found.")
             self.isBalanceEnough = False
             return []

        # 4. Sélectionner les UTXOs confirmés et non dépensés dans le mempool
        selected_utxo_keys_in_tx = set() 
        for tx_hex, TxObj in confirmed_utxos.items():
            if self.Total >= amount_needed_kernel:
                break 

            if not hasattr(TxObj, 'tx_outs'): continue

            for index, txout in enumerate(TxObj.tx_outs):
                utxo_id = f"{tx_hex}_{index}"

                # Vérifier si :
                # - appartient à l'expéditeur
                # - n'est PAS dans le set des UTXOs dépensés par le mempool
                # - n'est PAS déjà sélectionné pour CETTE transaction
                if hasattr(txout, 'script_pubkey') and \
                   hasattr(txout.script_pubkey, 'cmds') and \
                   len(txout.script_pubkey.cmds) > 2 and \
                   txout.script_pubkey.cmds[2] == self.fromPubKeyHash and \
                   utxo_id not in mempool_spent_utxos and \
                   utxo_id not in selected_utxo_keys_in_tx:

                    print(f"DEBUG: Selecting UTXO {utxo_id} with amount {txout.amount}")
                    self.Total += txout.amount
                    prev_tx_bytes = bytes.fromhex(tx_hex)
                    TxIns.append(TxIn(prev_tx_bytes, index))
                    selected_utxo_keys_in_tx.add(utxo_id) 

                    if self.Total >= amount_needed_kernel:
                        break 

        # 5. Vérification finale du solde
        if self.Total < amount_needed_kernel:
            self.isBalanceEnough = False
            return []

        self.isBalanceEnough = True 
        return TxIns

    def prepareTxOut(self):
        TxOuts = []
        amount_to_send_kernel = self.Amount

        self.fee = 25000000 
        if self.Total < amount_to_send_kernel + self.fee:
             print(f"Insufficient funds for amount + fee: Required {amount_to_send_kernel + self.fee}, Available {self.Total}")
             self.isBalanceEnough = False
             return []
        
        try:
             to_scriptPubkey = self.scriptPubKey(self.toAccount)
             TxOuts.append(TxOut(amount_to_send_kernel, to_scriptPubkey))
        except Exception as e:
             print(f"Error creating scriptPubKey for receiver: {e}")
             return []

        self.changeAmount = self.Total - amount_to_send_kernel - self.fee

        if self.changeAmount > 0:
            if hasattr(self, 'From_address_script_pubkey'):
                 TxOuts.append(TxOut(self.changeAmount, self.From_address_script_pubkey))
            else:
                 print("Error: Sender scriptPubKey not available for change output.")
        elif self.changeAmount < 0:
             print("Error: Negative change amount calculated.")
             return []

        return TxOuts


    def signTx(self):
        secret = self.getPrivateKey()
        if secret is None:
             print("Error: Cannot sign transaction without private key.")
             return False

        try:
             priv = PrivateKey(secret=int(secret))
        except Exception as e:
             print(f"Error creating PrivateKey object: {e}")
             return False

        if not hasattr(self, 'From_address_script_pubkey'):
            print("Error: Sender scriptPubKey not defined, cannot sign.")
            return False

        print(f"Signing transaction {self.TxObj.id()}...")
        for index, tx_in in enumerate(self.TxIns):
             print(f"Signing input #{index} spending UTXO {tx_in.prev_tx.hex()}:{tx_in.prev_index}")
             try:
                 self.TxObj.sign_input(index, priv, self.From_address_script_pubkey)
             except Exception as e:
                  print(f"Error signing input {index}: {e}")
                  return False
        print("Transaction signing complete.")
        return True

    def prepareTransaction(self):
        self.isBalanceEnough = True
        self.TxIns = self.prepareTxIn()
        if not self.isBalanceEnough: 
            print("DEBUG: Transaction preparation failed in prepareTxIn (Insufficient funds or UTXO unavailable)")
            return False #

        # Vérifie si assez pour montant + frais
        self.TxOuts = self.prepareTxOut()
        if not self.isBalanceEnough: 
            print("DEBUG: Transaction preparation failed in prepareTxOut (Insufficient funds for fee)")
            return False 

        if not self.TxIns or not self.TxOuts: 
             print("DEBUG: Transaction preparation failed (TxIns or TxOuts missing).")
             return False

        self.TxObj = Tx(1, self.TxIns, self.TxOuts, 0)

        #Signature
        if not self.signTx():
             print("DEBUG: Transaction preparation failed due to signing error.")
             return False

        self.TxObj.TxId = self.TxObj.id()
        print(f"Transaction prepared successfully: {self.TxObj.TxId}")
        return self.TxObj