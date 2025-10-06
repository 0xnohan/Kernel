import configparser
import os

def get_config_path():
    return os.path.join(os.getcwd(), 'data', 'config.ini')

def load_config():
    config = configparser.ConfigParser()
    config.read(get_config_path())
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