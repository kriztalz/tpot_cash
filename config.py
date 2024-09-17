import argparse

parser = argparse.ArgumentParser(description='TPOT TCG Bot')
parser.add_argument('-username', type=str, help='Username for the bot')
parser.add_argument('-password', type=str, help='Password for the bot')
args = parser.parse_args()

CONFIG = {
    "user": {
        "username": args.username if args.username else "addyourusernamehere",
        "password": args.password if args.password else "addyourusernamehere"
    },
    "modules": {
        "auto_complete_collection": {
            "enabled": True
        },
        "auto_pack_opener": {
            "enabled": True,
            "pack_price": 5,
            "min_balance": 0
        },
        "auto_trader": {
            "enabled": True,
            "max_refresh_price": 10
        }
    }
}