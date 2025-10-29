# src/utils/logging_config.py

import os
import sys
import logging
import logging.handlers

LOG_FILE = "data/log/debug.log"

def setup_logging():
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)  

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)  
    console_handler.setFormatter(formatter)

    file_handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3)
    file_handler.setLevel(logging.DEBUG)  
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    logging.getLogger("werkzeug").setLevel(logging.WARNING) 
    logging.getLogger("sqlitedict").setLevel(logging.WARNING)