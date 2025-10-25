import lmdb
import json
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
MAP_SIZE = 10 * 1024 * 1024 * 1024  # 10 Gb

class LMDBManager:
    def __init__(self, db_path, map_size=MAP_SIZE, max_dbs=10):
        self.db_path = db_path
        self.map_size = map_size
        self.max_dbs = max_dbs
        self.env = None

        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.env = lmdb.open(self.db_path, map_size=self.map_size, max_dbs=self.max_dbs, lock=True, writemap=False) 
        # lock=True for multhithreading acces , writemap=False for crash safety
           

    def _serialize(self, data):
        try:
            return json.dumps(data).encode('utf-8')
        except TypeError as e:
            logging.error(f"Error while serializing data: {e} for data: {data}")
            raise

    def _deserialize(self, data_bytes):
        if data_bytes is None:
            return None
        try:
            return json.loads(data_bytes.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logging.error(f"Error while deserializing data: {e} for bytes : {data_bytes[:100]}...") 
            raise

    def _get_db(self, txn, db_name=None):
        if db_name:
            return self.env.open_db(db_name.encode('utf-8'), txn=txn, create=True)
        else:
            return self.env.open_db(txn=txn, create=False) 

    def put(self, key, value, db_name=None):
        if self.env is None:
            logging.error("Impossible to write: LMDB environment is not open")
            return False
        try:
            serialized_value = self._serialize(value)
            with self.env.begin(write=True) as txn:
                db = self._get_db(txn, db_name)
                success = txn.put(key, serialized_value, db=db)
                if not success:
                    logging.warning(f"LMDB put operation returned False for key {key} in '{db_name or 'main'}' database")
                return success
        except lmdb.Error as e:
            logging.error(f"LMDB error during put operation for key {key} in '{db_name or 'main'}' database: {e}")
            return False
        except TypeError as e: 
             logging.error(f"Serialization error during put operation for key {key}: {e}")
             return False


    def get(self, key, db_name=None):
        if self.env is None:
            logging.error("Impossible to read: LMDB environment is not open")
            return None
        try:
            with self.env.begin(write=False) as txn:
                db = self._get_db(txn, db_name)
                value_bytes = txn.get(key, db=db)
                if value_bytes:
                    return self._deserialize(value_bytes)
                else:
                    return None 
        except lmdb.Error as e:
            logging.error(f"LMDB error during get operation for key {key} in '{db_name or 'main'}' database: {e}")
            return None
        except (json.JSONDecodeError, UnicodeDecodeError) as e: 
            logging.error(f"Deserialization error during get operation for key {key}: {e}")
            return None

    def delete(self, key, db_name=None):
        if self.env is None:
            logging.error("Impossible to delete: LMDB environment is not open")
            return False
        try:
            with self.env.begin(write=True) as txn:
                db = self._get_db(txn, db_name)
                txn.delete(key, db=db)
                return True
        except lmdb.Error as e:
            logging.error(f"LMDB error during delete operation for key {key} in '{db_name or 'main'}' database: {e}")
            return False


    def get_last_key_value(self, db_name=None):
        if self.env is None:
            logging.error("Impossible to read last key: LMDB environment is not open")
            return None, None
        try:
            with self.env.begin(write=False) as txn:
                db = self._get_db(txn, db_name)
                with txn.cursor(db=db) as cursor:
                    if cursor.last():
                        key = cursor.key()
                        value_bytes = cursor.value()
                        return key, self._deserialize(value_bytes)
                    else:
                        return None, None
        except lmdb.Error as e:
            logging.error(f"LMDB error during get_last_key_value in '{db_name or 'main'}' database: {e}")
            return None, None
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logging.error(f"Deserialization error during get_last_key_value: {e}")
            return None, None


    def get_all(self, db_name=None):
        if self.env is None:
            logging.error("Impossible to read all: LMDB environment is not open")
            return []
        items = []
        try:
            with self.env.begin(write=False) as txn:
                db = self._get_db(txn, db_name)
                with txn.cursor(db=db) as cursor:
                    for key, value_bytes in cursor:
                        try:
                            value = self._deserialize(value_bytes)
                            items.append((key, value))
                        except (json.JSONDecodeError, UnicodeDecodeError) as e:
                            logging.error(f"Deserialization error for key {key}: {e}")
                            items.append((key, {"error": "failed to deserialize", "details": str(e)}))
            return items
        except lmdb.Error as e:
            logging.error(f"LMDB error during get_all in '{db_name or 'main'}' database: {e}")
            return [] 


    def clear_db(self, db_name=None):
        if self.env is None:
            logging.error("Impossible to clear database: LMDB environment is not open")
            return False
        try:
            with self.env.begin(write=True) as txn:
                db = self._get_db(txn, db_name)
                txn.drop(db, delete=False) 
            return True
        except lmdb.Error as e:
            logging.error(f"LMDB error during clear_db in '{db_name or 'main'}' database: {e}")
            return False

    def close(self):
        if self.env:
            try:
                self.env.close()
                self.env = None
            except lmdb.Error as e:
                logging.error(f"Error while closing LMDB environment: {e}")

    def __del__(self):
        self.close()