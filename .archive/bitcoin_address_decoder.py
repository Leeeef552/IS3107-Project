"""
Bitcoin Address Decoder - Utility to analyze and explain Bitcoin addresses
"""

def decode_address_type(address: str) -> dict:
    """
    Decode a Bitcoin address and return information about it.

    Args:
        address: Bitcoin address string

    Returns:
        Dictionary with address type, format, and explanation
    """
    if not address:
        return {
            "type": "Unknown",
            "format": "N/A",
            "explanation": "No address provided"
        }

    # P2PKH - Legacy addresses (Pay to Public Key Hash)
    if address.startswith('1'):
        return {
            "type": "P2PKH",
            "format": "Legacy",
            "prefix": "1",
            "explanation": "Original Bitcoin address format. Higher transaction fees.",
            "features": [
                "Most widely supported",
                "Higher transaction fees than SegWit",
                "26-34 characters",
                "Case-sensitive"
            ],
            "mempool_url": f"https://mempool.space/address/{address}"
        }

    # P2SH - Script Hash addresses (often used for multisig)
    elif address.startswith('3'):
        return {
            "type": "P2SH",
            "format": "Script Hash",
            "prefix": "3",
            "explanation": "Can represent multisig wallets or complex scripts. Often used by exchanges.",
            "features": [
                "Enables multisignature wallets",
                "Used by many exchanges/institutions",
                "More flexible than legacy",
                "Moderate transaction fees"
            ],
            "mempool_url": f"https://mempool.space/address/{address}"
        }

    # Native SegWit - Bech32 format (P2WPKH or P2WSH)
    elif address.startswith('bc1q'):
        return {
            "type": "P2WPKH",
            "format": "Native SegWit (Bech32)",
            "prefix": "bc1q",
            "explanation": "Native SegWit address. Lower fees, more efficient. Most modern wallets.",
            "features": [
                "Lowest transaction fees (SegWit)",
                "More efficient block space usage",
                "Case-insensitive",
                "42 characters for P2WPKH",
                "Error detection built-in"
            ],
            "mempool_url": f"https://mempool.space/address/{address}"
        }

    # Taproot - Bech32m format (P2TR)
    elif address.startswith('bc1p'):
        return {
            "type": "P2TR",
            "format": "Taproot (Bech32m)",
            "prefix": "bc1p",
            "explanation": "Newest address type. Enhanced privacy, lower fees, supports smart contracts.",
            "features": [
                "Most advanced Bitcoin address",
                "Enhanced privacy (all look the same)",
                "Lower fees than SegWit",
                "Enables complex smart contracts",
                "62 characters"
            ],
            "mempool_url": f"https://mempool.space/address/{address}"
        }

    # Unknown format
    else:
        return {
            "type": "Unknown",
            "format": "Unrecognized",
            "prefix": address[:4] if len(address) >= 4 else address,
            "explanation": "Address format not recognized",
            "mempool_url": f"https://mempool.space/address/{address}"
        }


def analyze_whale_addresses(input_addr: str, output_addr: str) -> dict:
    """
    Analyze both input and output addresses from a whale transaction.

    Args:
        input_addr: Source address
        output_addr: Destination address

    Returns:
        Dictionary with analysis of both addresses
    """
    from_info = decode_address_type(input_addr)
    to_info = decode_address_type(output_addr)

    # Determine likely transaction type
    transaction_hints = []

    # Exchange patterns
    if from_info['type'] == 'P2SH' and to_info['type'] == 'P2WPKH':
        transaction_hints.append("🏦 Likely exchange withdrawal (multisig → personal wallet)")
    elif from_info['type'] == 'P2WPKH' and to_info['type'] == 'P2SH':
        transaction_hints.append("🏦 Likely exchange deposit (personal wallet → multisig)")
    elif from_info['type'] == 'P2SH' and to_info['type'] == 'P2SH':
        transaction_hints.append("🏛️ Likely institution-to-institution transfer")

    # Modern wallet usage
    elif from_info['type'] in ['P2WPKH', 'P2TR'] and to_info['type'] in ['P2WPKH', 'P2TR']:
        transaction_hints.append("💎 Modern wallet-to-wallet transfer (fee optimized)")

    # Legacy patterns
    elif from_info['type'] == 'P2PKH' or to_info['type'] == 'P2PKH':
        transaction_hints.append("🕰️ Using older address format (higher fees)")

    return {
        "from_address": {
            "address": input_addr,
            "info": from_info
        },
        "to_address": {
            "address": output_addr,
            "info": to_info
        },
        "transaction_hints": transaction_hints
    }


def format_address_summary(address: str) -> str:
    """
    Create a human-readable summary of an address.

    Args:
        address: Bitcoin address

    Returns:
        Formatted string with address type and key features
    """
    info = decode_address_type(address)

    summary = f"{info['format']} ({info['type']})"
    if 'features' in info and info['features']:
        summary += f" - {info['features'][0]}"

    return summary


if __name__ == "__main__":
    # Example usage
    test_address = "bc1qf43tdrym26qlz8rg06f88wg35n27uhcf29zs4f"

    print("=" * 70)
    print("Bitcoin Address Decoder")
    print("=" * 70)
    print()

    info = decode_address_type(test_address)

    print(f"Address: {test_address}")
    print()
    print(f"Type: {info['type']}")
    print(f"Format: {info['format']}")
    print(f"Prefix: {info['prefix']}")
    print()
    print(f"Explanation: {info['explanation']}")
    print()
    print("Features:")
    for feature in info.get('features', []):
        print(f"  • {feature}")
    print()
    print(f"View on Mempool: {info['mempool_url']}")
    print()

    # Example whale transaction analysis
    print("=" * 70)
    print("Whale Transaction Analysis Example")
    print("=" * 70)
    print()

    example_from = "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"  # P2SH (exchange)
    example_to = "bc1qf43tdrym26qlz8rg06f88wg35n27uhcf29zs4f"  # SegWit (personal)

    analysis = analyze_whale_addresses(example_from, example_to)

    print(f"From: {example_from}")
    print(f"  → {analysis['from_address']['info']['format']}")
    print(f"  → {analysis['from_address']['info']['explanation']}")
    print()
    print(f"To: {example_to}")
    print(f"  → {analysis['to_address']['info']['format']}")
    print(f"  → {analysis['to_address']['info']['explanation']}")
    print()
    print("Transaction Insights:")
    for hint in analysis['transaction_hints']:
        print(f"  {hint}")
