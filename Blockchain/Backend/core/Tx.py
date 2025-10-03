from Blockchain.Backend.core.Script import Script
from Blockchain.Backend.util.util import (
    int_to_little_endian,
    bytes_needed,
    decode_base58,
    little_endian_to_int,
    encode_varint,
    hash256,
    read_varint
)
import configparser
import json
import os

ZERO_HASH = b"\0" * 32
INITIAL_REWARD_SATOSHIS = 50 * 100000000 
HALVING_INTERVAL = 250000 
REDUCTION_FACTOR = 0.75
SIGHASH_ALL = 1

def load_miner_info():
    try:
        config = configparser.ConfigParser()
        config_path = os.path.join('data', 'config.ini')
        config.read(config_path)
        wallet_name = config['MINING']['wallet']

        wallet_path = os.path.join('data', 'wallets', f"{wallet_name}.json")
        with open(wallet_path, 'r') as f:
            wallet_data = json.load(f)
        
        return str(wallet_data['privateKey']), wallet_data['PublicAddress']
    except (FileNotFoundError, KeyError) as e:
        print(f"Could not load miner wallet '{wallet_name}', please check config.ini and wallet files")
        return None, None


class CoinbaseTx:
    def __init__(self, BlockHeight):
        self.BlockHeight = BlockHeight 
        self.BlockHeightInLittleEndian = int_to_little_endian(BlockHeight, bytes_needed(BlockHeight))
        self.privateKey, self.minerAddress = load_miner_info()



    def calculate_reward(self):
        """Calcule la récompense de bloc en fonction de la hauteur et de la réduction de 25%."""
        reduction_periods = self.BlockHeight // HALVING_INTERVAL
        reward_float = INITIAL_REWARD_SATOSHIS * (REDUCTION_FACTOR ** reduction_periods)
        reward_int = int(reward_float)

        #print(f"DEBUG Tx.py: BlockHeight={self.BlockHeight}, Reduction Periods={reduction_periods}")
        #print(f"DEBUG Tx.py: Calculated Float Reward={reward_float}")
        #print(f"DEBUG Tx.py: Calculated Int Reward (Satoshis)={reward_int}")
        return max(0, reward_int)


    def CoinbaseTransaction(self):
        prev_tx = ZERO_HASH
        prev_index = 0xFFFFFFFF
        tx_ins = []
        tx_ins.append(TxIn(prev_tx, prev_index))
        tx_ins[0].script_sig.cmds.append(self.BlockHeightInLittleEndian)

        tx_outs = []
        target_amount = self.calculate_reward()
        target_h160 = decode_base58(self.minerAddress)
        target_script = Script.p2pkh_script(target_h160)
        tx_outs.append(TxOut(amount=target_amount, script_pubkey=target_script))
        coinBaseTx = Tx(1, tx_ins, tx_outs, 0)
        coinBaseTx.TxId = coinBaseTx.id()

        return coinBaseTx


class Tx:
    command = b'Tx'
    def __init__(self, version, tx_ins, tx_outs, locktime):
        self.version = version
        self.tx_ins = tx_ins
        self.tx_outs = tx_outs
        self.locktime = locktime

    def id(self):
        return self.hash().hex()

    def hash(self):
        return hash256(self.serialize())[::-1]

    @classmethod
    def parse(cls, s):
        version = little_endian_to_int(s.read(4))
        num_inputs = read_varint(s)
        inputs = []
        for _ in range(num_inputs):
            inputs.append(TxIn.parse(s))
        num_outputs = read_varint(s)
        outputs = []
        for _ in range(num_outputs):
            outputs.append(TxOut.parse(s))
        locktime = little_endian_to_int(s.read(4))
        return cls(version, inputs, outputs, locktime)

    def serialize(self):
        result = int_to_little_endian(self.version, 4)
        result += encode_varint(len(self.tx_ins))

        for tx_in in self.tx_ins:
            result += tx_in.serialize()

        result += encode_varint(len(self.tx_outs))

        for tx_out in self.tx_outs:
            result += tx_out.serialize()

        result += int_to_little_endian(self.locktime, 4)
        return result

    def sigh_hash(self, input_index, script_pubkey):
        s = int_to_little_endian(self.version, 4)
        s += encode_varint(len(self.tx_ins))

        for i, tx_in in enumerate(self.tx_ins):
            if i == input_index:
                s += TxIn(tx_in.prev_tx, tx_in.prev_index, script_pubkey).serialize()
            else:
                s += TxIn(tx_in.prev_tx, tx_in.prev_index).serialize()

        s += encode_varint(len(self.tx_outs))

        for tx_out in self.tx_outs:
            s += tx_out.serialize()

        s += int_to_little_endian(self.locktime, 4)
        s += int_to_little_endian(SIGHASH_ALL, 4)
        h256 = hash256(s)
        return int.from_bytes(h256, "big")

    def sign_input(self, input_index, private_key, script_pubkey):
        z = self.sigh_hash(input_index, script_pubkey)
        der = private_key.sign(z).der()
        sig = der + SIGHASH_ALL.to_bytes(1, "big")
        sec = private_key.point.sec()
        self.tx_ins[input_index].script_sig = Script([sig, sec])

    def verify_input(self, input_index, script_pubkey):
        tx_in = self.tx_ins[input_index]
        z = self.sigh_hash(input_index, script_pubkey)
        combined = tx_in.script_sig + script_pubkey
        return combined.evaluate(z)

    def is_coinbase(self):
        if len(self.tx_ins) != 1:
            return False

        first_input = self.tx_ins[0]

        if first_input.prev_tx != b"\x00" * 32:
            return False

        if first_input.prev_index != 0xFFFFFFFF:
            return False

        return True

    @classmethod
    def to_obj(cls, item):
        TxInList = []
        TxOutList = []
        cmds = []
        
        for tx_in in item['tx_ins']:
            for cmd in tx_in['script_sig']['cmds']:
               
                if tx_in['prev_tx'] == "0000000000000000000000000000000000000000000000000000000000000000":
                    cmds.append(int_to_little_endian(int(cmd), bytes_needed(int(cmd))))
                else:
                    if type(cmd) == int:
                        cmds.append(cmd)
                    else:
                        cmds.append(bytes.fromhex(cmd))
            TxInList.append(TxIn(bytes.fromhex(tx_in['prev_tx']),tx_in['prev_index'],Script(cmds)))   


        cmdsout = []
        for tx_out in item['tx_outs']:
            for cmd in tx_out['script_pubkey']['cmds']:
                if type(cmd) == int:
                    cmdsout.append(cmd)
                else:
                    cmdsout.append(bytes.fromhex(cmd))
                    
            TxOutList.append(TxOut(tx_out['amount'],Script(cmdsout)))
            cmdsout= []
        
        return cls(1, TxInList, TxOutList, 0)
                


    def to_dict(self):
        for tx_index, tx_in in enumerate(self.tx_ins):
            if self.is_coinbase():
                tx_in.script_sig.cmds[0] = little_endian_to_int(
                    tx_in.script_sig.cmds[0]
                )

            tx_in.prev_tx = tx_in.prev_tx.hex()

            for index, cmd in enumerate(tx_in.script_sig.cmds):
                if isinstance(cmd, bytes):
                    tx_in.script_sig.cmds[index] = cmd.hex()

            tx_in.script_sig = tx_in.script_sig.__dict__
            self.tx_ins[tx_index] = tx_in.__dict__

        for index, tx_out in enumerate(self.tx_outs):
            tx_out.script_pubkey.cmds[2] = tx_out.script_pubkey.cmds[2].hex()
            tx_out.script_pubkey = tx_out.script_pubkey.__dict__
            self.tx_outs[index] = tx_out.__dict__

        return self.__dict__


class TxIn:
    def __init__(self, prev_tx, prev_index, script_sig=None, sequence=0xFFFFFFFF):
        self.prev_tx = prev_tx
        self.prev_index = prev_index

        if script_sig is None:
            self.script_sig = Script()
        else:
            self.script_sig = script_sig

        self.sequence = sequence

    def serialize(self):
        result = self.prev_tx[::-1]
        result += int_to_little_endian(self.prev_index, 4)
        result += self.script_sig.serialize()
        result += int_to_little_endian(self.sequence, 4)
        return result

    @classmethod
    def parse(cls, s):
        prev_tx = s.read(32)[::-1]
        prev_index = little_endian_to_int(s.read(4))
        script_sig = Script.parse(s)
        sequence = little_endian_to_int(s.read(4))
        return cls(prev_tx, prev_index, script_sig, sequence)


class TxOut:
    def __init__(self, amount, script_pubkey):
        self.amount = amount
        self.script_pubkey = script_pubkey

    def serialize(self):
        result = int_to_little_endian(self.amount, 8)
        result += self.script_pubkey.serialize()
        return result

    @classmethod
    def parse(cls,s):
        amount = little_endian_to_int(s.read(8))
        script_pubkey = Script.parse(s)
        return cls(amount, script_pubkey)
