from base64 import encode
from io import BytesIO
from src.utils.serialization import int_to_little_endian, little_endian_to_int, encode_varint, read_varint
from src.utils.crypto_hash import hash256

NETWORK_MAGIC = b'\xf9\xbe\xb4\xd9'
FINISHED_SENDING =b'\x0a\x11\x09\x07'

class NetworkEnvelope:
    def __init__(self, command, payload):
        self.command = command
        self.payload = payload
        self.magic = NETWORK_MAGIC

    @classmethod
    def parse(cls, s):
        magic = s.read(4)

        if magic != NETWORK_MAGIC:
            raise RuntimeError(f"Magic is not right {magic.hex()} vs {NETWORK_MAGIC.hex()}")
        
        command = s.read(12)
        command = command.strip(b'\x00')
        payloadLen = little_endian_to_int(s.read(4))
        checksum = s.read(4)
        payload = s.read(payloadLen)
        calculatedChecksum = hash256(payload)[:4]

        if calculatedChecksum != checksum:
            raise IOError("Checksum does not match")
        
        return cls(command, payload)

    def serialize(self):
        result = self.magic
        result += self.command + b'\x00' * (12 - len(self.command))
        result += int_to_little_endian(len(self.payload), 4)
        result += hash256(self.payload)[:4]
        result += self.payload
        return result 
    
    def stream(self):
        return BytesIO(self.payload)

class GetAddr:
    command = b'getaddr'

    def serialize(self):
        return b''

    @classmethod
    def parse(cls, stream):
        return cls()

class Addr:
    command = b'addr'
    def __init__(self, addresses):
        self.addresses = addresses

    def serialize(self):
        result = encode_varint(len(self.addresses))
        for host, port in self.addresses:
            host_bytes = host.encode('utf-8')
            result += encode_varint(len(host_bytes))
            result += host_bytes
            result += int_to_little_endian(port, 4)
        return result

    @classmethod
    def parse(cls, s):
        num_addresses = read_varint(s)
        addresses = []
        for _ in range(num_addresses):
            host_len = read_varint(s)
            host = s.read(host_len).decode('utf-8')
            port = little_endian_to_int(s.read(4))
            addresses.append((host, port))
        return cls(addresses)

class requestBlock:
    command = b'requestBlock'

    def __init__(self, startBlock = None, endBlock = None) -> None:
        if startBlock is None:
            raise RuntimeError("Starting Block cannot be None")
        else:
            self.startBlock = startBlock
        
        if endBlock is None:
            self.endBlock = b'\x00' * 32
        else: 
            self.endBlock = endBlock
    
    @classmethod
    def parse(cls, stream):
        startBlock = stream.read(32)
        endBlock = stream.read(32)
        return startBlock, endBlock

    def serialize(self):
        result = self.startBlock
        result += self.endBlock
        return result 

class portlist:
    command = b'portlist'
    def __init__(self, ports = None):
        self.ports = ports

    @classmethod
    def parse(cls, s):
        ports = []
        length = read_varint(s)

        for _ in range(length):
            port = little_endian_to_int(s.read(4))
            ports.append(port)
        
        return ports

    def serialize(self):
        result = encode_varint(len(self.ports))

        for port in self.ports:
            result += int_to_little_endian(port, 4)
        
        return result

class FinishedSending:
    command = b'Finished'

    @classmethod
    def parse(cls, s):
        magic = s.read(4)

        if magic == FINISHED_SENDING:
            return "Finished"

    def serialize(self):
        result = FINISHED_SENDING 
        return result 