import copy
import time
import json
import os

from multiprocessing import Process
from src.core.primitives.block import Block
from src.core.primitives.blockheader import BlockHeader
from src.core.primitives.transaction import Tx, TxIn, TxOut
from src.core.primitives.script import Script
from src.database.db_manager import BlockchainDB, NodeDB
from src.core.net.sync_manager import syncManager
from src.core.kmain.mempool import MempoolManager
from src.core.kmain.utxo_manager import UTXOManager

from src.utils.config_loader import get_miner_wallet
from src.core.kmain.genesis import create_genesis_block
from src.core.kmain.pow import mine
from src.utils.serialization import (
    merkle_root,
    target_to_bits,
    bits_to_target,
    int_to_little_endian,
    bytes_needed,
    decode_base58
)

from src.core.kmain.genesis import GENESIS_BITS, GENESIS_TIMESTAMP
from src.core.kmain.constants import (
    VERSION, 
    ZERO_HASH, 
    INITIAL_TARGET, 
    MAX_TARGET, 
    AVERAGE_BLOCK_MINE_TIME, 
    RESET_DIFFICULTY_AFTER_BLOCKS, 
    AVERAGE_MINE_TIME, 
    INITIAL_REWARD_KERNELS, 
    HALVING_INTERVAL, 
    REDUCTION_FACTOR
)


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

class Blockchain:
    def __init__(self, utxos, MemPool, newBlockAvailable, secondryChain, localHost, localHostPort):
        self.utxos = utxos
        self.MemPool = MemPool
        self.newBlockAvailable = newBlockAvailable
        self.secondryChain = secondryChain
        self.current_target = INITIAL_TARGET
        self.bits = target_to_bits(INITIAL_TARGET)
        self.localHost = localHost
        self.localHostPort = localHostPort
        self.mempool_manager = MempoolManager(self.MemPool, self.utxos)
        self.utxo_manager = UTXOManager(self.utxos)

    def write_on_disk(self, block):
        blockchainDB = BlockchainDB()
        blockchainDB.write(block)

    def fetch_last_block(self):
        blockchainDB = BlockchainDB()
        return blockchainDB.lastBlock()

    def GenesisBlock(self):
        print("Creating genesis block...")
        genesis_block = create_genesis_block()

        genesis_block.BlockHeader.to_hex() 
        tx_json_list = [tx.to_dict() for tx in genesis_block.Txs]
        block_to_save = {
            "Height": genesis_block.Height,
            "BlockSize": genesis_block.Blocksize,
            "BlockHeader": genesis_block.BlockHeader.__dict__,
            "TxCount": genesis_block.Txcount,
            "Txs": tx_json_list
        }
        
        blockchainDB = BlockchainDB()
        blockchainDB.write([block_to_save])
        print("Genesis block written to database")

    def startSync(self, block = None):
        try:
            node = NodeDB()
            portList = node.read()

            for port in portList:
                if self.localHostPort != port:
                    sync = syncManager(self.localHost, port, secondryChain = self.secondryChain)
                    try:
                        if block:
                            sync.publishBlock(self.localHostPort - 1, port, block) 
                        else:                    
                            sync.startDownload(self.localHostPort - 1, port, True)
                  
                    except Exception as err:
                        pass
                    
        except Exception as err:
            pass


    def settargetWhileBooting(self):
        bits, timestamp = self.getTargetDifficultyAndTimestamp()
        self.bits = bytes.fromhex(bits)
        self.current_target = bits_to_target(self.bits)

    def getTargetDifficultyAndTimestamp(self, BlockHeight = None):
        if BlockHeight:
            blocks = BlockchainDB().read()
            bits = blocks[BlockHeight]['BlockHeader']['bits']
            timestamp = blocks[BlockHeight]['BlockHeader']['timestamp']
        else:
            block = BlockchainDB().lastBlock()
            if not block:
                return GENESIS_BITS.hex(), GENESIS_TIMESTAMP
            
            bits = block['BlockHeader']['bits']
            timestamp = block['BlockHeader']['timestamp']
        return bits, timestamp


    def adjustTargetDifficulty(self, BlockHeight):
        if BlockHeight > 0 and BlockHeight % RESET_DIFFICULTY_AFTER_BLOCKS == 0:
            bits, timestamp = self.getTargetDifficultyAndTimestamp(BlockHeight - 10)
            Lastbits, lastTimestamp = self.getTargetDifficultyAndTimestamp()

            lastTarget = bits_to_target(bytes.fromhex(bits))
            AverageBlockMineTime = lastTimestamp - timestamp

            if AverageBlockMineTime < 0:
                self.bits = bytes.fromhex(Lastbits)
                self.current_target = bits_to_target(self.bits)
                return
            
            timeRatio = AverageBlockMineTime / AVERAGE_MINE_TIME
            calculated_target = float(lastTarget) * timeRatio
            
            NEW_TARGET = int(calculated_target)
            if NEW_TARGET <= 0:
                NEW_TARGET = lastTarget
                
            if NEW_TARGET > MAX_TARGET:
                NEW_TARGET = MAX_TARGET
            
            self.bits = target_to_bits(NEW_TARGET)
            self.current_target = NEW_TARGET

    def BroadcastBlock(self, block):
        self.startSync(block)

    def LostCompetition(self):
        deleteBlock = []
        tempBlocks = dict(self.newBlockAvailable)

        for newblock in tempBlocks:
            block = tempBlocks[newblock]
            deleteBlock.append(newblock)
        
            BlockHeaderObj = BlockHeader(block.BlockHeader.version,
                                block.BlockHeader.prevBlockHash, 
                                block.BlockHeader.merkleRoot, 
                                block.BlockHeader.timestamp,
                                block.BlockHeader.bits,
                                block.BlockHeader.nonce)

            if BlockHeaderObj.validateBlock():
                for idx, tx in enumerate(block.Txs):
                    self.utxos[tx.id()] = tx.serialize()
                    block.Txs[idx].TxId = tx.id()

                    """ Remove Spent Transactions """
                    for txin in tx.tx_ins:
                        if txin.prev_tx.hex() in self.utxos:
                            del self.utxos[txin.prev_tx.hex()]

                    if tx.id() in self.MemPool:
                        del self.MemPool[tx.id()]

                    block.Txs[idx] = tx.to_dict()
                    
                block.BlockHeader.to_hex()
                BlockchainDB().write([block.to_dict()])
            else:
                """ Resolve the Conflict b/w ther Miners """
                orphanTxs = {}
                validTxs = {}
                if self.secondryChain:
                    addBlocks = []
                    addBlocks.append(block)
                    prevBlockhash = block.BlockHeader.prevBlockHash.hex()
                    count = 0

                    while count != len(self.secondryChain):
                        if prevBlockhash in self.secondryChain:
                            addBlocks.append(self.secondryChain[prevBlockhash])
                            prevBlockhash = self.secondryChain[prevBlockhash].BlockHeader.prevBlockHash.hex()
                        count += 1
                    
                    blockchain = BlockchainDB().read()
                    lastValidBlock = blockchain[-len(addBlocks)]

                    if lastValidBlock['BlockHeader']['blockHash'] == prevBlockhash:
                        for i in range(len(addBlocks) - 1):
                            orphanBlock = blockchain.pop()

                            for tx in orphanBlock['Txs']:
                                if tx['TxId'] in self.utxos:
                                    del self.utxos[tx['TxId']]

                                    """ Don't Include COINBASE TX because it didn't come from MEMPOOL"""
                                    if tx['tx_ins'][0]['prev_tx'] != "0000000000000000000000000000000000000000000000000000000000000000":
                                        orphanTxs[tx['TxId']] = tx

                        BlockchainDB().update(blockchain)
                        
                        for Bobj in addBlocks[::-1]:
                            validBlock = copy.deepcopy(Bobj)
                            validBlock.BlockHeader.to_hex()

                            for index, tx in enumerate(validBlock.Txs):
                                validBlock.Txs[index].TxId = tx.id()
                                self.utxos[tx.id()] = tx

                                """ Remove Spent Transactions """
                                for txin in tx.tx_ins:
                                    if txin.prev_tx.hex() in self.utxos:
                                        del self.utxos[txin.prev_tx.hex()]
                                
                                if tx.tx_ins[0].prev_tx.hex() != "0000000000000000000000000000000000000000000000000000000000000000":
                                    validTxs[validBlock.Txs[index].TxId] = tx

                                validBlock.Txs[index] = tx.to_dict()
                            
                            BlockchainDB().write([validBlock.to_dict()])
                        
                        """ Add Transactoins Back to MemPool """
                        for TxId in orphanTxs:
                            if TxId not in validTxs:
                                self.MemPool[TxId] = Tx.to_obj(orphanTxs[TxId])

                self.secondryChain[newblock] = block

        
        for blockHash in deleteBlock:
            del self.newBlockAvailable[blockHash]

    def addBlock(self, BlockHeight, prevBlockHash):
        block_data = self.mempool_manager.get_transactions_for_block()
        self.addTransactionsInBlock = block_data["transactions"]
        self.TxIds = block_data["tx_ids"]
        self.fee = block_data["fees"]
        self.Blocksize = block_data["block_size"]

        spent_outputs = []
        for tx in self.addTransactionsInBlock:
            for tx_in in tx.tx_ins:
                spent_outputs.append([tx_in.prev_tx, tx_in.prev_index])

        timestamp = int(time.time())
        coinbaseInstance = CoinbaseTx(BlockHeight)
        coinbaseTx = coinbaseInstance.CoinbaseTransaction()
        self.Blocksize += len(coinbaseTx.serialize())

        coinbaseTx.tx_outs[0].amount = coinbaseTx.tx_outs[0].amount + self.fee

        self.TxIds.insert(0, bytes.fromhex(coinbaseTx.id()))
        self.addTransactionsInBlock.insert(0, coinbaseTx)

        merkleRoot = merkle_root(self.TxIds)[::-1].hex()
        self.adjustTargetDifficulty(BlockHeight)
        blockheader = BlockHeader(
            VERSION,
            bytes.fromhex(prevBlockHash),
            bytes.fromhex(merkleRoot),
            timestamp,
            self.bits,
            nonce=0
        )
        
        competitionOver, mined_header = mine(blockheader, self.current_target, self.newBlockAvailable)

        if competitionOver:
            self.LostCompetition()
        else:
            blockheader = mined_header
            newBlock = Block(BlockHeight, self.Blocksize, blockheader, len(self.addTransactionsInBlock), self.addTransactionsInBlock)
            block_to_broadcast = copy.deepcopy(newBlock)
            broadcastNewBlock = Process(target=self.BroadcastBlock, args=(block_to_broadcast,))
            broadcastNewBlock.start()  
            blockheader.to_hex()    

            self.utxo_manager.remove_spent_utxos(spent_outputs)
            self.utxo_manager.add_new_utxos(self.addTransactionsInBlock)
            self.mempool_manager.remove_transactions(self.TxIds)

            print(f"Block {BlockHeight} mined successfully with Nonce value of {blockheader.nonce}")
            tx_json_list = [tx.to_dict() for tx in newBlock.Txs]
            block_to_save = Block(
                BlockHeight,
                self.Blocksize,
                blockheader.__dict__,
                len(tx_json_list),
                tx_json_list
            )
            self.write_on_disk([block_to_save.__dict__])

    def main(self):
        lastBlock = self.fetch_last_block()
        if lastBlock is None:
            self.GenesisBlock()

        while True:
            lastBlock = self.fetch_last_block()
            BlockHeight = lastBlock["Height"] + 1
            print(f"Current Block Height is is {BlockHeight}")
            prevBlockHash = lastBlock["BlockHeader"]["blockHash"]
            self.addBlock(BlockHeight, prevBlockHash)