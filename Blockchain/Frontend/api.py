from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime, timezone
import hashlib
import time

from Blockchain.Backend.core.database.database import BlockchainDB
from Blockchain.Backend.util.util import encode_base58, decode_base58

app = Flask(__name__)
CORS(app) 
main_prefix = b'\x6c'
COIN = 100000000
MEMPOOL = {}

def encode_base58_checksum(h160_bytes):
    payload = main_prefix + h160_bytes
    checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    full_payload = payload + checksum
    return encode_base58(full_payload)

def read_blockchain_db():
    try:
        blockchain_db = BlockchainDB()
        blocks = blockchain_db.read()
        return blocks if blocks else []
    except Exception as e:
        app.logger.error(f"Error reading database: {e}")
        return []

def find_transaction_in_blocks(tx_id, blocks):
    for block in blocks:
        for tx in block.get("Txs", []):
            if tx.get("TxId") == tx_id:
                return tx
    return None

def format_transaction_details(tx, block, all_blocks):
    tx_id = tx.get("TxId")

    total_in = 0
    from_addresses = []
    for inp in tx.get("tx_ins", []):
        if inp.get("prev_tx") == '00' * 32:
            from_addresses.append("Coinbase")
            continue
        prev_tx_data = find_transaction_in_blocks(inp.get("prev_tx"), all_blocks)
        if prev_tx_data:
            try:
                spent_output = prev_tx_data['tx_outs'][inp.get("prev_index")]
                total_in += spent_output.get('amount', 0)
                h160_bytes = bytes.fromhex(spent_output['script_pubkey']['cmds'][2])
                from_addresses.append(encode_base58_checksum(h160_bytes))
            except (IndexError, KeyError, ValueError, TypeError):
                from_addresses.append("Error")

    total_out = 0
    to_addresses = []
    sent_value = 0
    unique_from_addresses = set(from_addresses)

    for out in tx.get("tx_outs", []):
        amount = out.get('amount', 0)
        total_out += amount
        try:
            h160_bytes = bytes.fromhex(out['script_pubkey']['cmds'][2])
            recipient_address = encode_base58_checksum(h160_bytes)
            to_addresses.append(recipient_address)
            if recipient_address not in unique_from_addresses:
                sent_value += amount
        except (IndexError, KeyError, ValueError, TypeError):
            to_addresses.append("Error")

    if "Coinbase" in from_addresses:
        fee = 0
        value = total_out
    else:
        fee = total_in - total_out
        value = sent_value if sent_value > 0 else total_out

    return {
        "hash": tx_id,
        "block_height": block.get("Height"),
        "block_hash": block.get("BlockHeader", {}).get("blockHash"),
        "from": list(set(from_addresses)),
        "to": to_addresses,
        "value": value / COIN,
        "fee": fee / COIN,
        "status": "success"
    }

def get_miner_address(block):
    if not block or not block.get('Txs'):
        return "N/A"
    
    coinbase_tx = block['Txs'][0]
    if coinbase_tx['tx_ins'][0]['prev_tx'] == '00' * 32:
        try:
            h160_hex = coinbase_tx['tx_outs'][0]['script_pubkey']['cmds'][2]
            h160_bytes = bytes.fromhex(h160_hex)
            return encode_base58_checksum(h160_bytes)
        except (IndexError, KeyError, TypeError, ValueError):
            return "Error Reading Miner Address"
    return "N/A"

@app.route('/api/stats')
def get_stats():
    blocks_db = read_blockchain_db()
    active_addresses = set()
    total_transactions = 0
    network_hashrate = "N/A"

    if blocks_db:
        for block in blocks_db:
            total_transactions += block.get('Txcount', 0)
            for tx in block.get("Txs", []):
                for tx_out in tx.get("tx_outs", []):
                    try:
                        active_addresses.add(tx_out['script_pubkey']['cmds'][2])
                    except (IndexError, KeyError, TypeError, ValueError):
                        continue

    return jsonify({
        "total_transactions": total_transactions,
        "active_addresses": len(active_addresses),
        "network_hashrate": network_hashrate
    })


@app.route('/api/blocks')
def get_blocks():
    blocks_db = read_blockchain_db()
    formatted_blocks = []
    for block in reversed(blocks_db):
        header = block.get("BlockHeader", {})
        block_size = block.get("Blocksize", 0)
        block_size_used = (block_size / 1000000) * 100

        formatted_blocks.append({
            "height": block.get("Height"),
            "hash": header.get("blockHash"),
            "timestamp": datetime.fromtimestamp(header.get('timestamp', 0)).isoformat() + "Z",
            "transaction_count": block.get("Txcount"),
            "miner": get_miner_address(block),
            "size_used": block_size_used,
            "reward": 50
        })
    return jsonify(formatted_blocks)

@app.route('/api/block/<block_hash>')
def get_block_details(block_hash):
    blocks_db = read_blockchain_db()
    
    for block in blocks_db:
        header = block.get("BlockHeader", {})
        if header.get("blockHash") == block_hash:
            formatted_txs = []
            if block.get("Txs"):
                for tx in block["Txs"]:
                    inputs = []
                    for inp in tx.get("tx_ins", []):
                        if inp.get("prev_tx") == '00' * 32:
                            inputs.append({"address": "Coinbase"})
                        else:
                            prev_tx_data = find_transaction_in_blocks(inp.get("prev_tx"), blocks_db)
                            sender_address = "Address not found"
                            if prev_tx_data:
                                try:
                                    spent_output = prev_tx_data['tx_outs'][inp.get("prev_index")]
                                    h160_hex = spent_output['script_pubkey']['cmds'][2]
                                    h160_bytes = bytes.fromhex(h160_hex)
                                    sender_address = encode_base58_checksum(h160_bytes)
                                except (IndexError, KeyError, TypeError, ValueError):
                                    sender_address = "Error reading address"
                            inputs.append({"address": sender_address})

                    outputs = []
                    for out in tx.get("tx_outs", []):
                         if 'script_pubkey' in out and len(out['script_pubkey'].get('cmds', [])) > 2:
                            try:
                                h160_hex = out['script_pubkey']['cmds'][2]
                                h160_bytes = bytes.fromhex(h160_hex)
                                address = encode_base58_checksum(h160_bytes)
                                amount = out.get("amount", 0) / 100000000
                                outputs.append({"address": address, "amount": amount})
                            except (IndexError, KeyError, TypeError, ValueError):
                                continue

                    formatted_txs.append({
                        "hash": tx.get("TxId"),
                        "inputs": inputs,
                        "outputs": outputs
                    })
            
            return jsonify({
                "block_number": block.get("Height"),
                "hash": header.get("blockHash"),
                "previous_hash": header.get("prevBlockHash"),
                "confirmations": len(blocks_db) - block.get("Height"),
                "transaction_count": block.get("Txcount"),
                "miner": get_miner_address(block),
                "size": block.get("Blocksize"),
                "merkle_root": header.get("merkleRoot"),
                "nonce": header.get("nonce"),
                "timestamp": datetime.fromtimestamp(header.get('timestamp', 0)).isoformat() + "Z",
                "transactions": formatted_txs,
                "reward": 50
            })
            
    return jsonify({"error": "Block not found"}), 404


@app.route('/api/address/<public_address>')
def get_address_details(public_address):
    try:
        target_h160 = decode_base58(public_address)
        if not target_h160:
            raise ValueError("Invalid address format")
    except Exception as e:
        app.logger.error(f"Error decoding address {public_address}: {e}")
        return jsonify({"error": "Invalid address format"}), 400

    blocks_db = read_blockchain_db()
    
    total_received_kernel = 0
    total_sent_kernel = 0
    address_transactions = []
    processed_tx_ids = set()

    for block in blocks_db:
        for tx in block.get("Txs", []):
            tx_id = tx.get("TxId")
            if tx_id in processed_tx_ids:
                continue

            is_sender = False
            is_receiver = False
            value_in = 0
            value_out = 0
            from_addresses = set()
            to_addresses = []

            for tx_in in tx.get("tx_ins", []):
                if tx_in.get("prev_tx") == '00' * 32:
                    from_addresses.add("Coinbase")
                    continue
                
                prev_tx = find_transaction_in_blocks(tx_in.get("prev_tx"), blocks_db)
                if prev_tx:
                    try:
                        spent_output = prev_tx["tx_outs"][tx_in.get("prev_index")]
                        h160_bytes = bytes.fromhex(spent_output['script_pubkey']['cmds'][2])
                        sender_address = encode_base58_checksum(h160_bytes)
                        from_addresses.add(sender_address)

                        if h160_bytes == target_h160:
                            is_sender = True
                            value_out += spent_output.get('amount', 0)
                    except (IndexError, KeyError, ValueError, TypeError):
                        continue
            
            for tx_out in tx.get("tx_outs", []):
                try:
                    h160_bytes = bytes.fromhex(tx_out.get('script_pubkey', {}).get('cmds', [])[2])
                    receiver_address = encode_base58_checksum(h160_bytes)
                    amount = tx_out.get('amount', 0)
                    to_addresses.append({"address": receiver_address, "amount": amount / COIN})

                    if h160_bytes == target_h160:
                        is_receiver = True
                        value_in += amount
                except (ValueError, TypeError, IndexError):
                    continue
            
            if is_sender or is_receiver:
                net_effect = (value_in - value_out) / COIN
                direction = "IN" if net_effect > 0 else "OUT"
                if is_sender:
                    total_sent_kernel += value_out
                if is_receiver:
                    total_received_kernel += value_in

                address_transactions.append({
                    "hash": tx_id,
                    "block_height": block.get("Height"),
                    "timestamp": datetime.fromtimestamp(block.get("BlockHeader", {}).get('timestamp', 0)).isoformat() + "Z",
                    "from": list(from_addresses),
                    "to": to_addresses,
                    "direction": direction,
                    "value": abs(net_effect)
                })
                processed_tx_ids.add(tx_id)

    current_balance_kernel = total_received_kernel - total_sent_kernel

    return jsonify({
        "address": public_address,
        "total_received": total_received_kernel / COIN,
        "total_sent": total_sent_kernel / COIN,
        "current_balance": current_balance_kernel / COIN,
        "transaction_count": len(address_transactions),
        "transactions": sorted(address_transactions, key=lambda x: x['block_height'], reverse=True)
    })


@app.route('/api/transactions')
def get_transactions():
    blocks_db = read_blockchain_db()
    all_txs = []
    limit = 50

    if not blocks_db:
        return jsonify([])

    for block in reversed(blocks_db):
        if len(all_txs) >= limit:
            break
        for tx in reversed(block.get("Txs", [])[1:]):
            if len(all_txs) >= limit:
                break
            
            formatted_tx = format_transaction_details(tx, block, blocks_db)
            all_txs.append(formatted_tx)
            
    return jsonify(all_txs)


@app.route('/api/tx/<tx_hash>')
def get_transaction_details(tx_hash):
    blocks_db = read_blockchain_db()
    if not blocks_db:
        return jsonify({"error": "Blockchain not found or empty"}), 404

    for block in blocks_db:
        for tx in block.get("Txs", []):
            if tx.get("TxId") == tx_hash:
                formatted_tx = format_transaction_details(tx, block, blocks_db)
                formatted_tx['status'] = "Confirmed"
                formatted_tx['timestamp'] = datetime.fromtimestamp(block.get("BlockHeader", {}).get('timestamp', 0)).isoformat() + "Z"
                formatted_tx['confirmations'] = len(blocks_db) - block.get("Height")
                detailed_inputs = []
                for inp in tx.get("tx_ins", []):
                    if inp.get("prev_tx") == '00' * 32:
                        detailed_inputs.append({"address": "Coinbase", "value": None})
                    else:
                        prev_tx_data = find_transaction_in_blocks(inp.get("prev_tx"), blocks_db)
                        if prev_tx_data:
                            spent_output = prev_tx_data['tx_outs'][inp.get("prev_index")]
                            h160_bytes = bytes.fromhex(spent_output['script_pubkey']['cmds'][2])
                            address = encode_base58_checksum(h160_bytes)
                            value = spent_output.get('amount', 0) / COIN
                            detailed_inputs.append({"address": address, "value": value})

                detailed_outputs = []
                for out in tx.get("tx_outs", []):
                    h160_bytes = bytes.fromhex(out['script_pubkey']['cmds'][2])
                    address = encode_base58_checksum(h160_bytes)
                    value = out.get('amount', 0) / COIN
                    detailed_outputs.append({"address": address, "value": value})
                
                formatted_tx['inputs'] = detailed_inputs
                formatted_tx['outputs'] = detailed_outputs

                return jsonify(formatted_tx)

    return jsonify({"error": "Transaction not found"}), 404

@app.route('/api/mempool')
def get_mempool():
    formatted_txs = []
    if MEMPOOL:
        current_mempool = dict(MEMPOOL)
        for tx_id, tx_obj in current_mempool.items():
            try:
                tx_dict = tx_obj.to_dict()
                total_value = sum(out.get('amount', 0) for out in tx_dict.get("tx_outs", []))
                
                formatted_txs.append({
                    "hash": tx_id,
                    "value": total_value / COIN,
                    "received_time": getattr(tx_obj, 'received_time', time.time()) 
                })
            except Exception as e:
                app.logger.error(f"Error processing mempool tx {tx_id}: {e}")
                continue
            
    return jsonify(formatted_txs)

def main(utxos, MemPool, port, localPort):
    global UTXOS
    global MEMPOOL
    global localHostPort 
    UTXOS = utxos
    MEMPOOL = MemPool
    localHostPort = localPort
    app.run(port = port)