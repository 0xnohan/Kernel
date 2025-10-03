from src.database.db_manager import BlockchainDB
from src.utils.crypto_hash import hash256
from src.utils.serialization import (int_to_little_endian, little_endian_to_int, bits_to_target)


def check_pow(block_header):
    sha = hash256(block_header.serialize())
    proof = little_endian_to_int(sha)
    return proof < bits_to_target(block_header.bits)

def validate_block_header(block_header):
    lastBlock = BlockchainDB().lastBlock()
    if block_header.prevBlockHash.hex() == lastBlock['BlockHeader']['blockHash']:
        if check_pow(block_header):
            return True
    return False

def mine(block_header, target, newBlockAvailable):
    current_hash_int = target + 1
    competitionOver = False

    while current_hash_int > target:
        if newBlockAvailable:
            competitionOver = True
            return competitionOver, None 

        block_header.nonce += 1
        serialized_header = block_header.serialize()
        current_hash_bytes = hash256(serialized_header)
        current_hash_int = little_endian_to_int(current_hash_bytes)

        print(f"Mining Started {block_header.nonce}", end="\r")

    block_header.blockHash = current_hash_bytes[::-1].hex()

    return competitionOver, block_header