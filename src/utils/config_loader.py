import configparser
import os
import logging
logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.getcwd(), 'data', 'config.ini')

def get_config_path():
    return CONFIG_PATH

def _create_default_config():
    config = configparser.ConfigParser()
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    
    config['NETWORK'] = {'host': '127.0.0.1'}
    config['P2P'] = {'port': '8889'}
    config['API'] = {'port': '8001'}
    config['MINING'] = {'wallet': ''}
    config['SEED_NODES'] = {}
    
    try:
        with open(CONFIG_PATH, 'w') as configfile:
            config.write(configfile)
        logger.debug(f"Default config file created at {CONFIG_PATH}")
    except IOError as e:
        logger.critical(f"Could not write default config file: {e}")
        
    return config

def load_config():
    if not os.path.exists(CONFIG_PATH):
        logger.debug("config.ini not found, creating default configuration...")
        return _create_default_config()
        
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)

    if 'MINING' not in config or 'wallet' not in config['MINING']:
        logger.warning("WARNING: 'MINING' section or 'wallet' key missing in config.ini, please create and add a wallet")
         
    return config

def get_config_dict():
    config = load_config()
    return {s: dict(config.items(s)) for s in config.sections()}

def update_config(section, key, value):
    config = load_config()
    if not config.has_section(section):
        config.add_section(section)
    config.set(section, key, str(value))
    with open(get_config_path(), 'w') as configfile:
        config.write(configfile)

def get_miner_wallet():
    config = load_config()
    try:
        return config['MINING']['wallet']
    except KeyError:
        return None