import os
import json
from sqlitedict import SqliteDict

class BaseDB:
    def __init__(self):
        self.basepath = "data"
        self.filepath = os.path.join(self.basepath, self.filename)

class BlockchainDB(BaseDB):
    def __init__(self):
        self.basepath = "data"
        self.db_file = os.path.join(self.basepath, "blockchain.sqlite")
        self.db = SqliteDict(self.db_file, autocommit=False)

    def read(self):
        blocks = []
        try:
            heights = sorted([int(k) for k in self.db.keys()])
        except ValueError:
            return []
        for height in heights:
            blocks.append(self.db[str(height)])
        return blocks

    def write(self, items):
        """Écrit une liste de blocs dans la base de données."""
        try:
            for block_dict in items:
                height = block_dict['Height']
                self.db[str(height)] = block_dict
            self.db.commit()
            print(f"Writing {len(items)} block(s) in db")
        except Exception as e:
            print(f"Error when writing to db: {e}")
            self.db.rollback()

    def update(self, data):
        """Écrase la base de données avec un nouvel ensemble de blocs."""
        try:
            self.db.clear()
            self.db.commit()
            self.write(data)
            print(f"Db updated with {len(data)} valid blocks")
            return True
        except Exception as e:
            print(f"Error when updating db: {e}")
            self.db.rollback()
            return False

    def lastBlock(self):
        try:
            if not self.db.keys():
                return None
            max_height = max([int(k) for k in self.db.keys()])
            return self.db[str(max_height)]
        except (ValueError, KeyError):
            # Gère le cas où la DB est vide ou les clés sont invalides
            return None

class AccountDB(BaseDB):
    def __init__(self):
        self.filename = "account"
        super().__init__()
        self.wallets_dir = os.path.join(self.basepath, "wallets")
        os.makedirs(self.wallets_dir, exist_ok=True)
    
    def get_all_wallets(self):
        wallets = []
        if not os.path.exists(self.wallets_dir):
            return wallets
        for filename in os.listdir(self.wallets_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(self.wallets_dir, filename)
                with open(filepath, "r") as file:
                    wallet_data = json.load(file)
                    wallets.append(wallet_data)

        return wallets
        
    def save_wallet(self, wallet_name, wallet_data):
        filename = f"{wallet_name}.json"
        filepath = os.path.join(self.wallets_dir, filename)

        if os.path.exists(filepath):
            print(f"Wallet with name '{wallet_name}' already exists")
            return False

        with open(filepath, "w") as file:
            json.dump(wallet_data, file, indent=4)
        return True


class NodeDB(BaseDB):
    def __init__(self):
        self.filename = "node"
        super().__init__()