from src.core.primitives.block import Block
from src.core.primitives.blockheader import BlockHeader
from src.core.primitives.transaction import Tx, TxIn, TxOut
from src.core.primitives.script import Script


GENESIS_TIMESTAMP = 1759863403
GENESIS_BITS = bytes.fromhex("b22d121e")
GENESIS_NONCE = 18453
GENESIS_MERKLE_ROOT = bytes.fromhex("a0e3b9e806c95cf243bd03c881966ac1d518b1b44e220bf373ee4bf348a2e765")
GENESIS_BLOCK_HASH = "0000ad2e767a7d6ad6297d6b867f680ab61c942b9b605c118f12f84eea6f30ed"
GENESIS_TX_ID = "a0e3b9e806c95cf243bd03c881966ac1d518b1b44e220bf373ee4bf348a2e765"
HASH160 = "3284b16e8cddbe53479ddab1c2a6010ca9923d88"

def create_genesis_block():
    tx_in = TxIn(
        prev_tx=b'\0' * 32, 
        prev_index=0xFFFFFFFF,
        script_sig=Script([b'Genesis Block']) 
    )
    
    script_pubkey = Script([
        0x76,
        0xA9,  
        bytes.fromhex(HASH160), 
        0x88,  
        0xAC   
    ])
    
    tx_out = TxOut(amount=5000000000, script_pubkey=script_pubkey)

    coinbase_tx = Tx(version=1, tx_ins=[tx_in], tx_outs=[tx_out], locktime=0)
    coinbase_tx.TxId = GENESIS_TX_ID 

    block_header = BlockHeader(
        version=1,
        prevBlockHash=b'\0' * 32,
        merkleRoot=GENESIS_MERKLE_ROOT,
        timestamp=GENESIS_TIMESTAMP,
        bits=GENESIS_BITS,
        nonce=GENESIS_NONCE
    )
    block_header.blockHash = GENESIS_BLOCK_HASH
    
    genesis_block = Block(
        Height=0,
        Blocksize=167, 
        BlockHeader=block_header,
        TxCount=1,
        Txs=[coinbase_tx]
    )

    return genesis_block