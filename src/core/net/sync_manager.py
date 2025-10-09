from src.core.primitives.block import Block
from src.core.primitives.blockheader import BlockHeader
from src.core.net.connection import Node
from src.database.db_manager import BlockchainDB, NodeDB
from src.core.primitives.transaction import Tx
from src.core.net.protocol import NetworkEnvelope, requestBlock, FinishedSending, portlist
from src.utils.serialization import little_endian_to_int
from threading import Thread

class syncManager:
    def __init__(self, host, port, newBlockAvailable = None, secondryChain = None, Mempool = None):
        self.host = host
        self.port = port 
        self.newBlockAvailable = newBlockAvailable
        self.secondryChain = secondryChain
        self.Mempool = Mempool
        self.peers = set()

    def connect_to_peer(self, host, port):
        peer_id = f"{host}:{port}"
        if peer_id in self.peers or (self.host == host and self.port == port):
            return

        try:
            print(f"Attempting to connect to {peer_id}...")
            peer_node = Node(host, port)
            client_socket = peer_node.connect(self.port) 
            self.peers.add(peer_id)

            print(f"Successfully connected to {peer_id}")
            handler_thread = Thread(target=self.handleConnection, args=(client_socket, (host, port)))
            handler_thread.start()

        except Exception as e:
            print(f"Failed to connect to peer {peer_id}. Error: {e}")


    def spinUpTheServer(self):
        self.server = Node(self.host, self.port)
        self.server.startServer()
        print("SERVER STARTED")
        print(f"[LISTENING] at {self.host}:{self.port}")

        while True:
            conn, addr = self.server.acceptConnection()
            handleConn = Thread(target=self.handleConnection, args=(conn, addr))
            handleConn.start()

    def handleConnection(self, conn, addr):
        print(f"Handling new connection from {addr}")
        stream = None
        try:
            self.addNode(addr)
            stream = conn.makefile('rb', None)
            
            while True:
                envelope = NetworkEnvelope.parse(stream)
                
                print(f"Received command '{envelope.command.decode()}' from {addr}")

                if envelope.command == b'Tx':
                    Transaction = Tx.parse(envelope.stream())
                    Transaction.TxId = Transaction.id()
                    if Transaction.TxId not in self.Mempool:
                        self.Mempool[Transaction.TxId] = Transaction
                        print(f"Added new transaction {Transaction.TxId[:10]}... to mempool")
                    
                elif envelope.command == b'block':
                    blockObj = Block.parse(envelope.stream())
                    BlockHeaderObj = BlockHeader(blockObj.BlockHeader.version,
                                blockObj.BlockHeader.prevBlockHash, 
                                blockObj.BlockHeader.merkleRoot, 
                                blockObj.BlockHeader.timestamp,
                                blockObj.BlockHeader.bits,
                                blockObj.BlockHeader.nonce)
                    
                    block_hash = BlockHeaderObj.generateBlockHash()
                    print(f"Received new block {blockObj.Height} ({block_hash[:10]}...) from {addr}")
                    self.newBlockAvailable[block_hash] = blockObj

                elif envelope.command == requestBlock.command:
                    start_block, end_block = requestBlock.parse(envelope.stream())
                    print(f"Peer {addr} requested blocks from {start_block.hex()[:10]}...")
                    # Modify logic to use "conn"
                    # self.sendBlockToRequestor(start_block) 

                # Add 'getaddr', 'addr', 'inv', etc for future msg

        except (IOError, ConnectionResetError) as e:
            print(f"Connection with {addr} was closed by the peer")
        except Exception as e:
            print(f"💥 An error occurred with peer {addr}. Closing connection. Error: {e}")
        finally:
            if conn:
                conn.close()
            
            peer_id = f"{addr[0]}:{addr[1]}"
            if peer_id in self.peers:
                self.peers.remove(peer_id)
            print(f"Connection with {addr} closed")

    def addNode(self, addr):
        try:
            peer_port = addr[1]
            if not isinstance(peer_port, int) or peer_port <= 0:
                return

            nodeDb = NodeDB()
            portList = nodeDb.read()

            if peer_port not in portList:
                nodeDb.write([peer_port])
                print(f"Added new peer port {peer_port} to database")
        except Exception as e:
            print(f"Could not add node {addr} to DB. Error: {e}")


    def sendBlockToRequestor(self, start_block):
        blocksToSend = self.fetchBlocksFromBlockchain(start_block)

        try:
            self.sendBlock(blocksToSend)
            self.sendSecondryChain()
            self.sendPortlist()
            self.sendFinishedMessage()
        except Exception as e:
            print(f"Unable to send the blocks \n {e}")

    def sendPortlist(self):
        nodeDB = NodeDB()
        portLists = nodeDB.read()

        portLst = portlist(portLists)
        envelope = NetworkEnvelope(portLst.command, portLst.serialize())
        self.conn.sendall(envelope.serialize())

    def sendSecondryChain(self):
        TempSecChain = dict(self.secondryChain)
        
        for blockHash in TempSecChain:
            envelope = NetworkEnvelope(TempSecChain[blockHash].command, TempSecChain[blockHash].serialize())
            self.conn.sendall(envelope.serialize())


    def sendFinishedMessage(self):
        MessageFinish = FinishedSending()
        envelope = NetworkEnvelope(MessageFinish.command, MessageFinish.serialize())
        self.conn.sendall(envelope.serialize())

    def sendBlock(self, blockstoSend):
        for block in blockstoSend:
            cblock = Block.to_obj(block)
            envelope = NetworkEnvelope(cblock.command, cblock.serialize())
            self.conn.sendall(envelope.serialize())
            print(f"Block Sent {cblock.Height}")

    def fetchBlocksFromBlockchain(self, start_Block):
        fromBlocksOnwards = start_Block.hex()

        blocksToSend = []
        blockchain = BlockchainDB()
        blocks = blockchain.read()

        foundBlock = False 
        for block in blocks:
            if block['BlockHeader']['blockHash'] == fromBlocksOnwards:
                foundBlock = True
                continue
        
            if foundBlock:
                blocksToSend.append(block)
        
        return blocksToSend

    def connectToHost(self, localport, port, bindPort = None):
        self.connect = Node(self.host, port)

        if bindPort:
            self.socket = self.connect.connect(localport, bindPort)
        else:
            self.socket = self.connect.connect(localport)

        self.stream = self.socket.makefile('rb', None)
    
    def publishBlock(self, localport, port, block):
        self.connectToHost(localport, port)
        self.connect.send(block)

    def publishTx(self, Tx):
        self.connect.send(Tx)
     
    def startDownload(self, localport,  port, bindPort):
        lastBlock = BlockchainDB().lastBlock()

        if not lastBlock:
            lastBlockHeader = "0000a889a4f86b9207c092684b5ecfe250a78c12bbd36c30a1665744a12bfed6"
        else:
            lastBlockHeader = lastBlock['BlockHeader']['blockHash']
        
        startBlock = bytes.fromhex(lastBlockHeader)

        getHeaders = requestBlock(startBlock=startBlock)
        self.connectToHost(localport, port, bindPort)
        self.connect.send(getHeaders)

        while True:    
            envelope = NetworkEnvelope.parse(self.stream)
            if envelope.command == b"Finished":
                blockObj = FinishedSending.parse(envelope.stream())
                print(f"All Blocks Received")
                self.socket.close()
                break

            if envelope.command == b'portlist':
                ports = portlist.parse(envelope.stream())
                nodeDb = NodeDB()
                portlists = nodeDb.read()

                for port in ports:
                    if port not in portlists:
                        nodeDb.write([port])

            if envelope.command == b'block':
                blockObj = Block.parse(envelope.stream())
                BlockHeaderObj = BlockHeader(blockObj.BlockHeader.version,
                            blockObj.BlockHeader.prevBlockHash, 
                            blockObj.BlockHeader.merkleRoot, 
                            blockObj.BlockHeader.timestamp,
                            blockObj.BlockHeader.bits,
                            blockObj.BlockHeader.nonce)
                
                if BlockHeaderObj.validateBlock():
                    for idx, tx in enumerate(blockObj.Txs):
                        tx.TxId = tx.id()
                        blockObj.Txs[idx] = tx.to_dict()
                
                    BlockHeaderObj.blockHash = BlockHeaderObj.generateBlockHash()
                    BlockHeaderObj.prevBlockHash = BlockHeaderObj.prevBlockHash.hex()
                    BlockHeaderObj.merkleRoot = BlockHeaderObj.merkleRoot.hex()
                    BlockHeaderObj.nonce =  little_endian_to_int(BlockHeaderObj.nonce)
                    BlockHeaderObj.bits = BlockHeaderObj.bits.hex()
                    blockObj.BlockHeader = BlockHeaderObj
                    BlockchainDB().write([blockObj.to_dict()])
                    print(f"Block Received - {blockObj.Height}")
                else:
                    self.secondryChain[BlockHeaderObj.generateBlockHash()] = blockObj
                