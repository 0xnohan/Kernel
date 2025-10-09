from src.core.primitives.transaction import Tx as TxClass

class Tx(TxClass):
    command = b'tx'
