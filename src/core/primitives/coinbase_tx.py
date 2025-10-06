import json
import os

from src.core.primitives.transaction import Tx, TxIn, TxOut
from src.core.primitives.script import Script
from src.utils.serialization import int_to_little_endian, bytes_needed, decode_base58
from src.utils.config_loader import get_miner_wallet

from src.core.kmain.constants import INITIAL_REWARD_KERNELS, HALVING_INTERVAL, REDUCTION_FACTOR


def load_miner_info():
    try:
        wallet_name = get_miner_wallet()
        if not wallet_name:
            raise KeyError
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
        reduction_periods = self.BlockHeight // HALVING_INTERVAL
        reward_float = INITIAL_REWARD_KERNELS * (REDUCTION_FACTOR ** reduction_periods)
        return max(0, int(reward_float))

    def CoinbaseTransaction(self):
        tx_ins = [TxIn(prev_tx=b"\0" * 32, prev_index=0xFFFFFFFF)]
        tx_ins[0].script_sig.cmds.append(self.BlockHeightInLittleEndian)

        target_amount = self.calculate_reward() 
        target_h160 = decode_base58(self.minerAddress)
        target_script = Script.p2pkh_script(target_h160)
        tx_outs = [TxOut(amount=target_amount, script_pubkey=target_script)]
        
        coinBaseTx = Tx(1, tx_ins, tx_outs, 0)
        coinBaseTx.TxId = coinBaseTx.id()
        return coinBaseTx
