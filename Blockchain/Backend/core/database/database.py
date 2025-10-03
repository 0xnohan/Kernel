import os
import json


class BaseDB:
    def __init__(self):
        self.basepath = "data"
        self.filepath = "/".join((self.basepath, self.filename))

    def read(self):
        if not os.path.exists(self.filepath):
            print(f"File {self.filepath} not available")
            return False

        with open(self.filepath, "r") as file:
            raw = file.readline()

        if len(raw) > 0:
            data = json.loads(raw)
        else:
            data = []
        return data

    def update(self, data):
        with open(self.filepath,'w+') as f:
            f.write(json.dumps(data))
        return True

    def write(self, item):
        data = self.read()
        if data:
            data = data + item
        else:
            data = item

        with open(self.filepath, "w+") as file:
            file.write(json.dumps(data))


class BlockchainDB(BaseDB):
    def __init__(self):
        self.filename = "blockchain"
        super().__init__()

    def lastBlock(self):
        data = self.read()

        if data:
            return data[-1]


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