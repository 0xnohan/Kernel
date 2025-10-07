import json
import socket
import configparser
import os

from src.core.client.wallet import wallet 
from src.core.client.send import Send 
from src.database.db_manager import AccountDB
from src.utils.serialization import decode_base58

def calculate_wallet_balances(wallets, utxos):
    balances = {wallet.get('PublicAddress'): 0 for wallet in wallets}
    
    for tx_obj in utxos.values():
        if hasattr(tx_obj, 'tx_outs'):
            for tx_out in tx_obj.tx_outs:
                try:
                    pubKeyHash = tx_out.script_pubkey.cmds[2]
                    for wallet in wallets:
                        wallet_h160 = decode_base58(wallet.get('PublicAddress'))
                        if wallet_h160 == pubKeyHash:
                            balances[wallet.get('PublicAddress')] += tx_out.amount
                            break
                except (AttributeError, IndexError, KeyError):
                    continue
    
    for wallet in wallets:
        balance_knl = balances.get(wallet.get('PublicAddress'), 0) / 100000000
        wallet['balance'] = balance_knl
        
    return wallets

def handleRpcCommand(command, utxos, mempool, miningProcessManager):
    cmd = command.get('command')
    params = command.get('params', {})
    
    if cmd == 'ping':
        return {"status": "success", "message": "pong"}

    elif cmd == 'start_miner':
        miningProcessManager['is_mining'] = True
        return {"status": "success", "message": "Mining process started."}
    
    elif cmd == 'stop_miner':
        miningProcessManager['is_mining'] = False
        return {"status": "success", "message": "Mining process stopped."}
        
    elif cmd == 'create_wallet':
        wallet_name = params.get('name')
        if not wallet_name:
            return {"status": "error", "message": "Wallet name is required"}
        acc = wallet()
        wallet_data = acc.createKeys(wallet_name)
        if AccountDB().save_wallet(wallet_name, wallet_data):
            return {"status": "success", "message": f"Wallet '{wallet_name}' created.", "wallet": wallet_data}
        else:
            return {"status": "error", "message": f"Wallet '{wallet_name}' already exists."}
        
    elif cmd == 'send_tx':
        fee_rate = params.get('fee_rate', 5)
        send_handler = Send(params['from'], params['to'], float(params['amount']), fee_rate, utxos, mempool)
        tx = send_handler.prepareTransaction()
        if tx:
            mempool[tx.id()] = tx
            return {"status": "success", "message": "Transaction added to mempool", "txid": tx.id()}
        else:
            return {"status": "error", "message": "Failed to create transaction. Check balance and addresses."}
    
    elif cmd == 'get_wallets':
        try:
            all_wallets = AccountDB().get_all_wallets()
            wallets_with_balances = calculate_wallet_balances(all_wallets, utxos)
            return {"status": "success", "wallets": wallets_with_balances}
        except Exception as e:
            return {"status": "error", "message": f"Could not retrieve wallets: {e}"}

    elif cmd == 'shutdown':
        miningProcessManager['shutdown_requested'] = True
        return {"status": "success", "message": "Daemon shutdown initiated"}
    
    else:
        return {"status": "error", "message": f"Command '{cmd}' not recognized"}

def rpcServer(host, rpcPort, utxos, mempool, miningProcessManager):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, rpcPort))
        s.listen()
        print(f"RPC server started, listening on port {rpcPort}")
        while True:
            conn, addr = s.accept()
            with conn:
                data = conn.recv(1024)
                if not data:
                    continue
                
                try:
                    command = json.loads(data.decode('utf-8'))
                    response = handleRpcCommand(command, utxos, mempool, miningProcessManager)
                except Exception as e:
                    response = {"status": "error", "message": f"An unexpected error occurred: {e}"}

                conn.sendall(json.dumps(response).encode('utf-8'))