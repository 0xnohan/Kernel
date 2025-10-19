# Kernel

**Kernel** is a simplified implementation of a blockchain in Python.  
This project is directly inspired by the consensus mechanism and chain structure of **Bitcoin**.  
The consensus is based on the **Proof-of-Work algorithm**, where miners must solve complex cryptographic problems to validate new blocks and add them to the chain.  
The validation process uses the SHA-256 function to ensure the integrity of each block's data. Each block contains a hash of the previous block, creating a secure and immutable chain of blocks.

By adopting this mechanism, my project simulates adding transactions to a block, finding the correct "nonce" to solve the cryptographic problem, and managing consensus through a local network of actors. However, this is a prototype with minimal security and is currently not resistant to attacks. The primary goal is to faithfully replicate the functioning of a blockchain.

## 📝 Table of Contents

- [Architecture](#architecture)
- [Features](#features)
- [Technologies Used](#technologies-used)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Versions](#versions)

---
## Architecture

The project is now structured around a client-daemon architecture for better modularity and extensibility:

- **Kernel Daemon** (KernelD.py): The core of the system. It manages the P2P network, the mining process, the blockchain database, and exposes an API for the explorer.

- **Kernel CLI** (KernelCLI.py): A command-line client that communicates with the daemon to perform actions like starting/stopping mining, creating a wallet, or sending transactions.

- **API** (serverAPI.py): A Flask API that allows querying the state of the blockchain. It is designed to be used by block explorers like the Kernel Explorer.

## Features

- **P2P Network**: Nodes can discover each other (local) and synchronize the blockchain.
- **Proof-of-Work Mining**: Miners can validate transactions and create new blocks to earn a reward.
- **Wallet Management**: Create addresses and send transactions directly from the command-line client.
- **Explorer API**: Exposes endpoints to track the chain's status, and view blocks, transactions, and addresses.
- **Block Reward**: The block reward consist of an initial reward of 50 KNL per block. The reward is reduced by 25% every 250,000 blocks.
  Amounts are denominated in KNL, divisible down to the smallest unit, the kernel (1 KNL = 10^8 kores).
  This geometrically decreasing reward ensures a finite total coin supply of 50 000 000 KNL
  
## Technologies Used

- **Python**: Main language for the blockchain logic.
- **Flask**: Web framework for server API.
- **Cryptographic Libraries**: `pycryptodome` for asymmetric cryptography and `hashlib` for hashing functions.
- **Communication**: Native Sockets for the P2P network and RPC interface.

## Prerequisites

Before getting started, ensure you have the following installed:

- Python 3.7 or higher
- Pip (Python package manager)
- A terminal or command prompt

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/0xnohan/Kernel.git
   cd Kernel

2. Create a virtual environment and activate it in the terminal:
   ```bash
   python -m venv venv # Or python3
   source env/bin/activate # (On Windows : .\env\Scripts\activate)

3. Install the dependencies:
   ```bash
   pip install -r requirements.txt

## Usage
    
 1. To test the project, start the Client and follow the instructions:
    ```bash
    python KernelCLI.py

 2. For a graphical interface, use the Kernel Explorer:
  - Download the project here: [Kernel Explorer](https://github.com/0xnohan/KernelExplorer):
  - Run it:
    ```bash
    npm install
    npm run dev

 3. To test with multiple nodes locally:
  - Duplicate the project folder for each additional node
  
  - In each duplicated folder, modify the `data/config.ini` file:
    - Change the P2P and API ports to unique values (ex: port = 9999 for `[P2P]` and port = 9001 for `[API]`)
    - Add the first node as a "seed node" (no value)
    - In the `[SEED_NODES]` section (node2, node3,...), add the address of the first node (ex: node1 = 127.0.0.1:8889)

  - Run: 
    ```bash
    python KernelCLI.py # in each folder
    
  - Create a new wallet(4) and change miner address in settings(5) to the name of the new wallet 

## Versions

### Current Version

- **Kernel Version**: 1.32.3
- **Date**: October 2025

**New Changes**:
- Fix bugs in validator.py, miner.py, sync_manager.py
- Add a stable p2p system (mining race, messages (inv, addr, headers,...), timeout, broadcast inventory, share peers)
- Implement connection between nodes
- Change for sqldict instead of .json for a better structure (test for now)
- Add dynamics fees for transactions

**Last Changes**:
- Changed the architecture of the project to split the files for better understanding
- Added settings in the client to configure the ini file (ports, miner, host,...)
- Added new utils files to load configurations
- Added a mempool file and class for better mempool management
- Split the blockchain.py file in different processes (pow, utxos_manager, mempool and chain)
- Bug fixes for data type in blockheader
- Renaming files and removing unused imports/packages
- Minors bug fixes

### Previous Versions


#### Kernel 1.23
- **Date**: September 2025

**Changes**:
- Add a Client & Deamon to simplify future implementations and the development of the node/network system
- Architecture change when launching the daemon
- Delete the run.py file for a new server API for frontend explorer
- Ability to create a wallet and send coins directly from the CLI
- Minors bug fixes

#### Kernel 1.10
- **Date**: August 2025

**Changes**:
- Kernel Blockchain
- Complete code refactoring
- Blockchain explorer redesign
- Change in the reward system (deflationary)
- Start managing network nodes and seed nodes
- Security and majors bug fixes: mempool/networks/blockchain download with peers


#### Noctal Version 1 
- **Date**: March 2024 - March 2025

**Changes**:

- View all changes -> [Noctal V1](https://github.com/0xnohan/Noctal)

---

*nohan*
