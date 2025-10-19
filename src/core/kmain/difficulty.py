from src.database.db_manager import BlockchainDB
from src.utils.serialization import target_to_bits, bits_to_target
from src.core.primitives.constants import MAX_TARGET, RESET_DIFFICULTY_AFTER_BLOCKS, AVERAGE_MINE_TIME
from src.core.kmain.genesis import GENESIS_BITS

def calculate_new_bits(current_height):
    db = BlockchainDB()
    last_block = db.lastBlock()
    
    if not last_block:
        return GENESIS_BITS

    if current_height % RESET_DIFFICULTY_AFTER_BLOCKS != 0:
        return bytes.fromhex(last_block['BlockHeader']['bits'])

    all_blocks = db.read() 
    if len(all_blocks) < RESET_DIFFICULTY_AFTER_BLOCKS:
        return bytes.fromhex(last_block['BlockHeader']['bits'])
    
    first_block_in_period = all_blocks[current_height - RESET_DIFFICULTY_AFTER_BLOCKS]
    time_diff = last_block['BlockHeader']['timestamp'] - first_block_in_period['BlockHeader']['timestamp']
    
    if time_diff == 0:
        time_diff = 1 

    time_ratio = max(0.25, min(4.0, time_diff / AVERAGE_MINE_TIME))
    last_target = bits_to_target(bytes.fromhex(last_block['BlockHeader']['bits']))
    new_target = int(last_target * time_ratio)
    new_target = min(new_target, MAX_TARGET)
    new_bits = target_to_bits(new_target)
    
    print(f"Difficulty readjusted. New bits: {new_bits.hex()}")
    
    return new_bits