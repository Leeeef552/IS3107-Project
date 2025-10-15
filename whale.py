import requests

# === CONFIGURABLE PARAMETERS ===
MIN_BTC_VALUE = 5  # Only show transactions with at least this much BTC sent
USE_TESTNET = False  # Set to True if you want testnet data

# === API SETUP ===
BASE_URL = "https://mempool.space"
if USE_TESTNET:
    BASE_URL = "https://mempool.space/testnet"

API_BLOCK_TIP = f"{BASE_URL}/api/blocks/tip/hash"
API_BLOCK_TXS = f"{BASE_URL}/api/block/{{}}/txs"

def get_latest_block_hash():
    response = requests.get(API_BLOCK_TIP)
    response.raise_for_status()
    return response.text.strip()

def get_transactions_in_block(block_hash):
    url = API_BLOCK_TXS.format(block_hash)
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def get_total_output_value_btc(tx):
    """Sum all output values in a transaction (in BTC)."""
    total_sats = sum(output['value'] for output in tx['vout'])
    return total_sats / 100_000_000  # Convert satoshis to BTC

def main():
    print("Fetching latest block hash...")
    block_hash = get_latest_block_hash()
    print(f"Latest block: {block_hash}")

    print("Fetching transactions...")
    transactions = get_transactions_in_block(block_hash)
    print(f"Total transactions in block: {len(transactions)}")

    filtered_txs = []
    for tx in transactions:
        total_btc = get_total_output_value_btc(tx)
        if total_btc >= MIN_BTC_VALUE:
            filtered_txs.append((tx['txid'], total_btc))

    print(f"\nTransactions with ≥ {MIN_BTC_VALUE} BTC:")
    print("-" * 70)
    for txid, value in filtered_txs:
        print(f"{txid} → {value:.8f} BTC")

    print(f"\nFound {len(filtered_txs)} large transactions.")

if __name__ == "__main__":
    main()