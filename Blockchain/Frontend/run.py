from flask import Flask, render_template, request, redirect, url_for
from Blockchain.client.send import Send
from Blockchain.Backend.core.Tx import Tx
from Blockchain.Backend.core.database.database import BlockchainDB, NodeDB
from Blockchain.Backend.util.util import encode_base58, decode_base58
from Blockchain.Backend.core.network.syncManager import syncManager
from Blockchain.client.account import account 
from Blockchain.Backend.core.database.database import AccountDB 

from hashlib import sha256
from multiprocessing import Process
from flask_qrcode import QRcode
import time
from datetime import datetime, timezone 
import copy
from math import ceil

app = Flask(__name__)
qrcode = QRcode(app)
main_prefix = b'\x6c'
global memoryPool
memoryPool ={}


def format_time_ago(timestamp_seconds):
    if not timestamp_seconds:
        return "N/A"
    now_utc = datetime.now(timezone.utc)
    dt_object_utc = datetime.fromtimestamp(timestamp_seconds, timezone.utc)
    diff = now_utc - dt_object_utc

    seconds = diff.total_seconds()
    if seconds < 0: 
        return "just now"
    elif seconds < 60:
        return f"{int(seconds)} seconds ago"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    else:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days > 1 else ''} ago"
    
@app.route('/')
def index():
    num_wallets = 0
    total_txs = 0
    block_height = 0
    total_knl_kernel = 0
    total_knl = 0.0
    fake_price = 50000000 
    unique_addresses_set = set() 

    try:
        blockchain_db = BlockchainDB()
        blocks = blockchain_db.read()
        if blocks:
            block_height = blocks[-1]['Height']
            total_txs = sum(block.get('Txcount', 0) for block in blocks)

            for block in blocks:
                if 'Txs' in block and block['Txs']:
                    for tx in block['Txs']:
                        if 'tx_outs' in tx and tx['tx_outs']:
                            for tx_out in tx['tx_outs']:
                                try:
                                    if (isinstance(tx_out, dict) and
                                        'script_pubkey' in tx_out and
                                        isinstance(tx_out['script_pubkey'], dict) and
                                        'cmds' in tx_out['script_pubkey'] and
                                        isinstance(tx_out['script_pubkey']['cmds'], list) and
                                        len(tx_out['script_pubkey']['cmds']) > 2 and
                                        isinstance(tx_out['script_pubkey']['cmds'][2], str)):

                                        h160 = tx_out['script_pubkey']['cmds'][2]
                                        unique_addresses_set.add(h160) 
                                except (KeyError, IndexError, TypeError) as e:
                                    app.logger.warning(f"Could not extract address from tx_out: {tx_out}. Error: {e}")
                                    continue 

            num_wallets = len(unique_addresses_set) #

        if UTXOS:
            try:
                current_utxos = dict(UTXOS)
                for tx_id in current_utxos:
                    tx_obj = current_utxos[tx_id]
                    if hasattr(tx_obj, 'tx_outs'):
                         for tx_out in tx_obj.tx_outs:
                            if hasattr(tx_out, 'amount'):
                                total_knl_kernel += tx_out.amount
            except Exception as e:
                 app.logger.error(f"Error calculating total BTC from UTXOS: {e}")

        total_knl = total_knl_kernel / 100000000

    except Exception as e:
        app.logger.error(f"Error retrieving blockchain summary data: {e}")

    return render_template('home.html', block_height=block_height, total_txs=total_txs, num_wallets=num_wallets, total_knl=total_knl, fake_price=fake_price)

@app.route('/transactions/<txid>')
@app.route('/transactions')
def transactions(txid = None):
    if txid:
        return redirect(url_for('txDetail', txid = txid))
    else:
        ErrorFlag = True
        while ErrorFlag:
            try:
                allTxs = dict(UTXOS)
                ErrorFlag = False
                return render_template("transactions.html",allTransactions = allTxs,refreshtime = 10)
            except:
                ErrorFlag = True
                return render_template('transactions.html', allTransactions={}, refreshtime = 10)

@app.route('/tx/<txid>')
def txDetail(txid):
    blocks = readDatabase()
    for block in blocks:
        for Tx in block['Txs']:
            if Tx['TxId'] == txid:
                return render_template('txDetail.html', Tx=Tx, block = block , encode_base58 = encode_base58,
                bytes = bytes, sha256 = sha256, main_prefix = main_prefix)
    return "<h1> No Results Found </h1>"

@app.route('/mempool')
def mempool():
    mempool_for_template = {}
    try:
        if 'MEMPOOL' in globals() or 'MEMPOOL' in app.config:
            mempool_source = {}
            if 'MEMPOOL' in globals():
                 mempool_source = MEMPOOL
            elif 'MEMPOOL' in app.config:
                 mempool_source = app.config['MEMPOOL']

            current_mempool_copy = {}
            keys = list(mempool_source.keys()) 
            for txid in keys:
                txobj = mempool_source.get(txid)
                if txobj:
                     current_mempool_copy[txid] = txobj
        

            for txid, txobj in current_mempool_copy.items():
                value = 0
                if hasattr(txobj, 'tx_outs') and txobj.tx_outs:
                    try:
                        value = sum(txo.amount for txo in txobj.tx_outs if hasattr(txo, 'amount')) / 100000000
                    except AttributeError:
                        pass
                mempool_for_template[txid] = {'value': value}

    except Exception as e:
        mempool_for_template = {} 

    total_txs_count = len(mempool_for_template)

    return render_template('mempool.html', Txs=mempool_for_template, total_txs_count=total_txs_count)


@app.route('/memTx/<txid>')
def memTxDetails(txid):
    tx_detail_data = None
    try:
        mempool_source = {}
        if 'MEMPOOL' in globals():
            mempool_source = MEMPOOL
        elif 'MEMPOOL' in app.config:
            mempool_source = app.config['MEMPOOL']
        else:
             raise KeyError("Mempool source not found")

        txobj = mempool_source.get(txid)
        if txobj and hasattr(txobj, 'to_dict'):
            tx_detail_data = txobj.to_dict()
        else:
            raise KeyError(f"Tx {txid} not found in mempool or cannot be converted to dict")

        return render_template('txDetail.html', Tx=tx_detail_data, main_prefix=main_prefix, encode_base58=encode_base58, bytes=bytes, sha256=sha256, Unconfirmed=True)

    except (KeyError, AttributeError, Exception) as e:
        return redirect(url_for('transactions', txid=txid))

        
@app.route('/search')
def search():
    identifier = request.args.get('search')
    if len(identifier) == 64:
        if identifier[:4] == "0000":
            return redirect(url_for('showBlock', blockHeader = identifier))
        else:
            return redirect(url_for('txDetail', txid = identifier))
    else:
        return redirect(url_for('address', publicAddress = identifier))

""" Read data from the Blockchain """
def readDatabase():
    ErrorFlag = True
    while ErrorFlag:
        try:
            blockchain = BlockchainDB()
            blocks = blockchain.read()
            ErrorFlag = False
        except:
            ErrorFlag = True
            print("Error reading database")
    return blocks

@app.route('/block')
def block():
    header = request.args.get('blockHeader')
    if header:
        return redirect(url_for('showBlock', blockHeader=header))
    else:
        page = request.args.get('page', 1, type=int) 
        PER_PAGE = 25 

        blocks_full_list = readDatabase() 
        processed_blocks_full = []

        if blocks_full_list:
            for block_data in blocks_full_list:
                processed_block = block_data.copy()
                timestamp = processed_block.get('BlockHeader', {}).get('timestamp', 0)
                processed_block['age_str'] = format_time_ago(timestamp)
                total_sent_kernel = 0

                if 'Txs' in processed_block and processed_block['Txs']:
                    for tx in processed_block['Txs']:
                        is_coinbase = False
                        if 'tx_ins' in tx and len(tx['tx_ins']) == 1:
                            prev_tx_val = tx['tx_ins'][0].get('prev_tx', '')
                            if prev_tx_val == '00' * 32: is_coinbase = True
                        if not is_coinbase and 'tx_outs' in tx:
                            for tx_out in tx['tx_outs']:
                                total_sent_kernel += tx_out.get('amount', 0)

                processed_block['total_sent'] = total_sent_kernel / 100000000
                processed_blocks_full.append(processed_block)

            processed_blocks_full = processed_blocks_full[::-1]

            total_items = len(processed_blocks_full)
            total_pages = ceil(total_items / PER_PAGE)

            start_index = (page - 1) * PER_PAGE
            end_index = start_index + PER_PAGE

            paginated_blocks = processed_blocks_full[start_index:end_index]

            return render_template('block.html', blocks=paginated_blocks, current_page=page, total_pages=total_pages)
        else:
             return render_template('block.html', blocks=[], current_page=1, total_pages=1)
        
@app.route('/block/<blockHeader>')
def showBlock(blockHeader):
    blocks = readDatabase() 
    target_block_data = None
    confirmations = 0 

    if not blocks: 
         return "<h1>Blockchain is empty</h1>", 404

    latest_block_height = blocks[-1].get('Height', 0)
    for block_iter in blocks:
        current_block_hash = block_iter.get('BlockHeader', {}).get('blockHash')
        if current_block_hash == blockHeader:
            target_block_data = block_iter 
            current_height = target_block_data.get('Height', 0)
            confirmations = latest_block_height - current_height + 1
            break 

    if target_block_data:
         return render_template('blockDetails.html', block = target_block_data, confirmations = confirmations, main_prefix = main_prefix, encode_base58 = encode_base58, bytes = bytes, sha256 = sha256)
    else: 
        return "<h1>Block not found</h1>", 404


@app.route('/address/<publicAddress>')
def address(publicAddress):
    COIN = 100000000
    tx_page = request.args.get('tx_page', 1, type=int)
    TX_PER_PAGE = 10 

    try:
        target_h160 = decode_base58(publicAddress)
        if not target_h160: 
            raise ValueError("Invalid address format")

        total_received_satoshi = 0
        all_tx_ids_involving_address = set()
        try:
             all_blocks = readDatabase()
             if all_blocks:
                for block in all_blocks:
                    if 'Txs' in block and block['Txs']:
                        for tx in block['Txs']:
                            tx_id = tx.get('TxId')
                            if not tx_id: continue
                            relevant_to_address_hist = False
                            if 'tx_outs' in tx and tx['tx_outs']:
                                for tx_out in tx['tx_outs']:
                                     try:
                                         script_cmds = tx_out.get('script_pubkey', {}).get('cmds', [])
                                         if len(script_cmds) > 2:
                                             out_h160_bytes = bytes.fromhex(script_cmds[2]) if isinstance(script_cmds[2], str) else script_cmds[2]
                                             if out_h160_bytes == target_h160:
                                                 total_received_satoshi += tx_out.get('amount', 0)
                                                 relevant_to_address_hist = True
                                     except (ValueError, TypeError, IndexError): pass
                            if relevant_to_address_hist:
                                all_tx_ids_involving_address.add(tx_id)

             total_tx_count = len(all_tx_ids_involving_address)
             total_received = total_received_satoshi / COIN

        except Exception as e:
            total_tx_count = 0
            total_received = 0.0


        current_balance_kernel = 0
        AccountUtxo_Tx_Objects_All = [] 
        try:
            current_utxos_dict = dict(UTXOS) 
            processed_utxo_tx_ids = set()
            for tx_id, tx_obj in current_utxos_dict.items():
                 if not hasattr(tx_obj, 'tx_outs') or not isinstance(tx_obj.tx_outs, list): continue
                 found_utxo_in_tx = False
                 for tx_out in tx_obj.tx_outs:
                     if hasattr(tx_out, 'script_pubkey') and \
                        hasattr(tx_out.script_pubkey, 'cmds') and \
                        len(tx_out.script_pubkey.cmds) > 2:
                        try:
                            h160_bytes = tx_out.script_pubkey.cmds[2]
                            if isinstance(h160_bytes, str):
                                h160_bytes = bytes.fromhex(h160_bytes)

                            if h160_bytes == target_h160:
                                current_balance_kernel += tx_out.amount
                                found_utxo_in_tx = True
                        except (TypeError, IndexError, ValueError): pass

                 if found_utxo_in_tx and tx_id not in processed_utxo_tx_ids:
                     AccountUtxo_Tx_Objects_All.append(copy.deepcopy(tx_obj))
                     processed_utxo_tx_ids.add(tx_id)
        except Exception as e:
            current_balance_kernel = 0

        unspent_tx_count = len(AccountUtxo_Tx_Objects_All)
        balance_display = current_balance_kernel / COIN

        tx_total_items = unspent_tx_count
        tx_total_pages = ceil(tx_total_items / TX_PER_PAGE)
        tx_start_index = (tx_page - 1) * TX_PER_PAGE
        tx_end_index = tx_start_index + TX_PER_PAGE
        paginated_txs = AccountUtxo_Tx_Objects_All[tx_start_index:tx_end_index]

        return render_template('address.html',
                               publicAddress = publicAddress,
                               Txs = paginated_txs,
                               tx_current_page = tx_page,
                               tx_total_pages = tx_total_pages,
                               amount = current_balance_kernel,
                               balance_display = balance_display,
                               unspent_tx_count = unspent_tx_count,
                               total_tx_count = total_tx_count,
                               total_received = total_received,
                               main_prefix = main_prefix, 
                               encode_base58 = encode_base58, 
                               bytes = bytes, 
                               sha256 = sha256, 
                               qrcode = qrcode
                              )

    except ValueError as ve:
         return "<h1>Invalid Address Format</h1>", 400
    except Exception as e:
        return "<h1>Error processing address details</h1>", 500


@app.route("/wallet", methods=["GET", "POST"])
def wallet():
    message = ""
    acc_db = AccountDB()
    wallets = acc_db.read() or []

    if request.method == "POST":
        action = request.form.get("action")

        if action == "send":

            FromAddress = request.form.get("fromAddress")
            ToAddress = request.form.get("toAddress")
    
            Amount_str = request.form.get("Amount") 
            Amount_float = None 

            if Amount_str:
                try:
                    Amount_float = float(Amount_str) 
                    if Amount_float <= 0:
                        message = "Amount must be positive."
                        Amount_float = None 
                except ValueError:
                    message = "Invalid Amount entered."
                    Amount_float = None 
            else:
                message = "Amount is required."

            if Amount_float is not None and not message:
                global MEMPOOL, UTXOS
                sendCoin = Send(FromAddress, ToAddress, Amount_float, UTXOS, MEMPOOL)

                TxObj = sendCoin.prepareTransaction()

                verified = True 

                if not TxObj:
                    if hasattr(sendCoin, 'isBalanceEnough') and not sendCoin.isBalanceEnough:
                        message = "Insufficient Balance."
                    else:
                        message = "Invalid Transaction Details or Failed Preparation." 
                elif isinstance(TxObj, Tx):
                    if verified: 
                        MEMPOOL[TxObj.TxId] = TxObj
                        global localHostPort
                        if 'localHostPort' in globals():
                            relayTxs = Process(target=broadcastTx, args=(TxObj, localHostPort))
                            relayTxs.start()
                            message = "Transaction added to Memory Pool"
                        else:
                            message = "Transaction prepared but cannot determine local port to broadcast"
        elif action == "create":
            try:
                new_wallet_account = account()
                new_wallet_data = new_wallet_account.createKeys()
                acc_db.write([new_wallet_data]) 
                message = f"New wallet created successfully: {new_wallet_data['PublicAddress']}"
                wallets = acc_db.read() or []
            except Exception as e:
                message = f"Error creating wallet: {e}"

        elif action == "delete":
            address_to_delete = request.form.get("publicAddress")
            if address_to_delete:
                updated_wallets = [w for w in wallets if w.get('PublicAddress') != address_to_delete]
                acc_db.update(updated_wallets) 
                message = f"Wallet {address_to_delete[:10]}... deleted."
                wallets = updated_wallets 
            
    return render_template("wallet.html", message=message, wallets=wallets) 

def broadcastTx(TxObj, localHostPort = None):
    try:
        node = NodeDB()
        portList = node.read()

        for port in portList:
            if localHostPort != port:
                sync = syncManager('127.0.0.1', port)
                try:
                    sync.connectToHost(localHostPort - 1, port)
                    sync.publishTx(TxObj)
                
                except Exception as err:
                    pass
                
    except Exception as err:
        pass

def main(utxos, MemPool, port, localPort):
    global UTXOS
    global MEMPOOL
    global localHostPort 
    UTXOS = utxos
    MEMPOOL = MemPool
    localHostPort = localPort
    app.run(port = port)
