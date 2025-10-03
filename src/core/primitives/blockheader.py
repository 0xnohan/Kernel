from src.database.db_manager import BlockchainDB
from src.utils.crypto_hash import hash256
from src.utils.serialization import (int_to_little_endian, little_endian_to_int, bits_to_target)


class BlockHeader:
    def __init__(self, version, prevBlockHash, merkleRoot, timestamp, bits, nonce = None):
        self.version = version
        self.prevBlockHash = prevBlockHash
        self.merkleRoot = merkleRoot
        self.timestamp = timestamp
        self.bits = bits
        self.nonce = nonce
        self.blockHash = ""

    @classmethod
    def parse(cls, s):
        version = little_endian_to_int(s.read(4))
        prevBlockHash = s.read(32)[::-1]
        merkleRoot = s.read(32)[::-1]
        timestamp = little_endian_to_int(s.read(4))
        bits = s.read(4)
        nonce = s.read(4)
        return cls(version, prevBlockHash, merkleRoot, timestamp, bits, nonce)

    def serialize(self):
        result = int_to_little_endian(self.version, 4)
        prev_block_hash_bytes = self.prevBlockHash
        if isinstance(prev_block_hash_bytes, str):
            prev_block_hash_bytes = bytes.fromhex(prev_block_hash_bytes)

        merkle_root_bytes = self.merkleRoot
        if isinstance(merkle_root_bytes, str):
            merkle_root_bytes = bytes.fromhex(merkle_root_bytes)

        result += prev_block_hash_bytes[::-1]
        result += merkle_root_bytes[::-1]
        result += int_to_little_endian(self.timestamp, 4)
        result += self.bits
        nonce_bytes = self.nonce
        if isinstance(nonce_bytes, int):
            nonce_bytes = int_to_little_endian(nonce_bytes, 4)
        result += nonce_bytes
        return result
    
    def to_hex(self):
        self.blockHash = self.generateBlockHash()

        if isinstance(self.nonce, bytes):
            self.nonce = little_endian_to_int(self.nonce)

        if isinstance(self.prevBlockHash, bytes):
            self.prevBlockHash = self.prevBlockHash.hex()

        if isinstance(self.merkleRoot, bytes):
            self.merkleRoot = self.merkleRoot.hex()

        if isinstance(self.bits, bytes):
            self.bits = self.bits.hex()

    def to_bytes(self):
        if isinstance(self.nonce, int):
            self.nonce = int_to_little_endian(self.nonce, 4)

        if isinstance(self.prevBlockHash, str):
            self.prevBlockHash = bytes.fromhex(self.prevBlockHash)

        if isinstance(self.merkleRoot, str):
            self.merkleRoot = bytes.fromhex(self.merkleRoot)

        if isinstance(self.blockHash, str):
            self.blockHash = bytes.fromhex(self.blockHash)

        if isinstance(self.bits, str):
            self.bits = bytes.fromhex(self.bits)

    def generateBlockHash(self):
        sha = hash256(self.serialize())
        proof = little_endian_to_int(sha)
        return int_to_little_endian(proof, 32).hex()[::-1]

    def to_dict(self):
        dt = self.__dict__
        return dt

