import time

from src.utils.serialization import decode_base58
from src.scripts.script import Script
from src.core.transaction import TxIn, TxOut, Tx
from src.database.db_manager import AccountDB

from secp256k1 import PrivateKey

from src.chain.params import TX_BASE_SIZE, TX_INPUT_SIZE, TX_OUTPUT_SIZE,COIN

class Send:
    def __init__(self, fromAccount, toAccount, Amount_float, feeRate, UTXOS, MEMPOOL):
        self.FromPublicAddress = fromAccount
        self.toAccount = toAccount
        self.feeRate = feeRate
        self.receivedTime = time.time()
        self.utxos = UTXOS
        self.mempool = MEMPOOL 
        self.isBalanceEnough = True

        if isinstance(Amount_float, (int, float)) and Amount_float > 0:
            self.Amount = int(Amount_float * COIN)
        else:
            self.Amount = 0
            self.isBalanceEnough = False
            print(f"Error: Invalid amount ({Amount_float}) passed to send")

    def estimate_tx_size(self, num_inputs, num_outputs):
        return TX_BASE_SIZE + (num_inputs * TX_INPUT_SIZE) + (num_outputs * TX_OUTPUT_SIZE)

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

        try:
            self.From_address_script_pubkey = self.scriptPubKey(self.FromPublicAddress)
            self.fromPubKeyHash = self.From_address_script_pubkey.cmds[2]
        except Exception as e:
            print(f"Error creating scriptPubKey for sender: {e}")
            self.isBalanceEnough = False
            return []

        mempool_spent_utxos = set()
        current_mempool = dict(self.mempool)
        print(f"DEBUG: Checking {len(current_mempool)} transactions in mempool for spent UTXOs")
        for tx_mem_obj in current_mempool.values():
            if hasattr(tx_mem_obj, 'tx_ins'):
                for tx_in_mem in tx_mem_obj.tx_ins:
                    mempool_spent_utxos.add(f"{tx_in_mem.prev_tx.hex()}_{tx_in_mem.prev_index}")
        print(f"DEBUG: Found {len(mempool_spent_utxos)} UTXOs spent in mempool")

        spendable_utxos = []
        confirmed_utxos = dict(self.utxos)
        for tx_hex, TxObj in confirmed_utxos.items():
            if not hasattr(TxObj, 'tx_outs'): continue
            for index, txout in enumerate(TxObj.tx_outs):
                utxo_id = f"{tx_hex}_{index}"
                if hasattr(txout.script_pubkey, 'cmds') and len(txout.script_pubkey.cmds) > 2 and \
                   txout.script_pubkey.cmds[2] == self.fromPubKeyHash and \
                   utxo_id not in mempool_spent_utxos:
                    spendable_utxos.append({'tx_hex': tx_hex, 'index': index, 'amount': txout.amount})

        if not spendable_utxos:
            print("No spendable UTXOs found.")
            self.isBalanceEnough = False
            return []

        spendable_utxos.sort(key=lambda x: x['amount'])

        for utxo in spendable_utxos:
            TxIns.append(TxIn(bytes.fromhex(utxo['tx_hex']), utxo['index']))
            self.Total += utxo['amount']
            print(f"DEBUG: Selecting UTXO {utxo['tx_hex']}_{utxo['index']} with amount {utxo['amount']}. Total collected: {self.Total}")

            estimated_size = self.estimate_tx_size(num_inputs=len(TxIns), num_outputs=2)
            estimated_fee = int(estimated_size * self.feeRate)

            if self.Total >= self.Amount + estimated_fee:
                print("DEBUG: Collected enough to cover amount + fees")
                break

        
        final_size = self.estimate_tx_size(num_inputs=len(TxIns), num_outputs=2)
        final_fee = int(final_size * self.feeRate)
        if self.Total < self.Amount + final_fee:
            self.isBalanceEnough = False
            return []

        self.isBalanceEnough = True
        return TxIns

    def prepareTxOut(self):
        TxOuts = []
        amount_to_send_kernel = self.Amount

        num_outputs = 2 #2 for now (receiver & sender)
        estimated_size = self.estimate_tx_size(num_inputs=len(self.TxIns), num_outputs=num_outputs)
        self.fee = int(estimated_size * self.feeRate)

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

        elif self.changeAmount == 0:
            num_outputs = 1

        else:
            print("Error: Negative change amount calculated.")
            return []

        final_size = self.estimate_tx_size(num_inputs=len(self.TxIns), num_outputs=num_outputs)
        self.fee = int(final_size * self.feeRate)
        
        return TxOuts


    def signTx(self):
        secret = self.getPrivateKey()
        if secret is None:
            print("Error: Cannot sign transaction without private key.")
            return False

        try:
            secret_bytes = int(secret).to_bytes(32, 'big')
            priv = PrivateKey(privkey=secret_bytes)
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

        # Check for amount + fees
        self.TxOuts = self.prepareTxOut()
        if not self.isBalanceEnough: 
            print("DEBUG: Transaction preparation failed in prepareTxOut (Insufficient funds for fee)")
            return False 

        if not self.TxIns or not self.TxOuts: 
            print("DEBUG: Transaction preparation failed (TxIns or TxOuts missing).")
            return False

        self.TxObj = Tx(1, self.TxIns, self.TxOuts, 0)
        self.TxObj.fee = self.fee 
        self.TxObj.receivedTime = self.receivedTime

        #Signature
        if not self.signTx():
            print("DEBUG: Transaction preparation failed due to signing error.")
            return False

        self.TxObj.TxId = self.TxObj.id()
        print(f"Transaction prepared successfully: {self.TxObj.TxId}")
        return self.TxObj