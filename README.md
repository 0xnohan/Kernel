# Kernel

**Kernel** is an implementation of a blockchain in Python.  
This project is directly inspired by the consensus mechanism and chain structure of **Bitcoin**.  
The consensus is based on the **Proof-of-Work algorithm**, where miners must solve complex cryptographic problems to validate new blocks and add them to the chain.  
The validation process uses the SHA-256 function to ensure the integrity of each block's data. Each block contains a hash of the previous block, creating a secure and immutable chain of blocks.

By adopting this mechanism, my project simulates adding transactions to a block, finding the correct "nonce" to solve the cryptographic problem, and managing consensus through a local network of actors. However, this is a prototype for now, with minimal security and is currently not resistant to attacks. The primary goal is to faithfully replicate the functioning of a blockchain.

This project come from a deep interest in the world of cryptocurrencies and blockchain technology over the past 7 years. It is the logical continuation of numerous projects and learning experiences I have undertaken in this field.  
This project is not entirely my own work, as I do not possess the necessary skills to implement certain blockchain mechanisms myself, particularly complex cryptographic principles (e.g., elliptic curve functions, opcodes, and Merkle tree-related functions).

## 📝 Table of Contents

- [About](#about)
- [Features](#features)
- [Technologies Used](#technologies-used)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Versions](#versions)

---

## About

This project aims to gain experience while also demonstrating how a blockchain works from the ground up:
- Creation and validation of blocks.
- Implementation of a simple consensus mechanism.
- A web interface to visualize and interact with the blockchain.

## Features

- **Transaction Submission**: Users can submit transactions via the Flask interface.
- **Block Creation**: Miners can validate and add blocks to the chain.
- **Blockchain Exploration**: Users can track the current state of the blockchain through the explorer.
  
## Technologies Used

- **Python**: Main language for the blockchain logic.
- **Flask**: Web framework for the user interface.
- **HTML/CSS/JavaScript**: For the user interface.
- **External Python Files**: For cryptographic calculations.
- **Python Libraries**:
  - `flask`
  - `hashlib`
  - `json`
  - `pycryptodome`
  - `configparser`
  - `...`

## Prerequisites

Before getting started, ensure you have the following installed:

- Python 3.7 or higher
- Pip (Python package manager)
- A web browser
- An IDE

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/62nowan/Kernel.git
   cd Noctal

2. Create a virtual environment and activate it in the terminal:
   ```bash
   python -m venv venv # Or python3
   source env/bin/activate # (On Windows : .\env\Scripts\activate)

3. Install the dependencies:
   ```bash
   pip install -r requirements.txt

## Usage

 1. Run the account.py file to generate a private key and a public key:
    ```bash
    python account.py

 2. Add your keys to the tx.py file to enable block mining.

 3. Start mining using the blockchain.py file:
    ```bash
    python blockchain.py

 4. You can access the explorer via the URL:
    ```bash
    http://127.0.0.1:5900


## Versions

### Current Version

- **Kernel Version**: 1.1
- **Date**: August 2025

**Changes**:
- Kernel Blockchain
- Complete code refactoring
- Blockchain explorer redesign
- Change in the reward system (deflationary)
- Start managing network nodes and seed nodes
- Security and majors bug fixes: mempool/networks/blockchain download with peers

### Previous Versions

#### Noctal Version 1 to 1.3
- **Date**: March 2024 - March 2025

**Changes**:

- Final implementation of the blockchain with a Proof-of-Work consensus mechanism.
- Development of the Flask user interface for interacting with the blockchain: addition of transaction pages, block details, and full chain exploration.
- Establishment of the project foundations with clearer comments and code structure.
- Creation of a P2P network prototype.
- Setup of a local server and request handling.
- Synchronization of requests and sending of blockchain data files to miners. (Time synchronization issues to be resolved).

- Initial blockchain prototype: block mining, block visualization, address visualization, etc.
- First draft of the Flask user interface for chain visualization.
- Creation of the transaction principle, memory pool, pending transactions, and removal of spent transactions.
- Implementation of transaction signing and verification.
- Addition of transaction fees, autonomous adjustment of mining difficulty, and block size calculation.

- Creation of the repository and basic project structure.
- Implementation of a simple block model in a JSON file with basic hashing functions.
- First version without a user interface, only blockchain logic in Python via the terminal.
- Implementation of addresses along with private and public keys.
- Storage of data on disk.

---


*nowan*




