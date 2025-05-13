# Kernel

**Kernel** is an implementation of a blockchain in Python, complete with a build-in GUI.  
This project is directly inspired by the consensus mechanism and chain structure of **Bitcoin**.  
The consensus is based on the **Proof-of-Work algorithm**, where miners must solve complex cryptographic problems to validate new blocks and add them to the chain.  
The validation process uses the SHA-256 function to ensure the integrity of each block's data. Each block contains a hash of the previous block, creating a secure and immutable chain of blocks.

By adopting this mechanism, our project simulates adding transactions to a block, finding the correct "nonce" to solve the cryptographic problem, and managing consensus through a local network of actors. However, this is a prototype for now, with minimal security and is currently not resistant to attacks. The primary goal is to faithfully replicate the functioning of a blockchain.

Quick preview of the Pre-Release Version (Frontend Explorer):

![Home Page](https://github.com/shash64/Noctal/blob/main/KernelScreenshots/homepage.png)
![Block Page](https://github.com/shash64/Noctal/blob/main/KernelScreenshots/blockpage.png)
![Block Details Page](https://github.com/shash64/Noctal/blob/main/KernelScreenshots/blockdetails.png)
![Block Details 2 Page](https://github.com/shash64/Noctal/blob/main/KernelScreenshots/blockdetails2.png)
![Address Page](https://github.com/shash64/Noctal/blob/main/KernelScreenshots/addressExplorer.png)


GUI preview comming Soon
