# Bitcoin Addresses Explained

## What is a Bitcoin Address?

A Bitcoin address is like a bank account number - it's where people can send Bitcoin to you. Each address is a string of 26-62 alphanumeric characters that represents a destination for Bitcoin payments.

## Address Types & Prefixes

### 1. **Legacy (P2PKH)** - Starts with `1`
**Example:** `1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2`

- **What it means:** Original Bitcoin address format from 2009
- **Length:** 26-34 characters
- **Transaction Fees:** Highest (uses most block space)
- **Who uses it:** Old wallets, some exchanges still support it
- **Format:** Pay-to-Public-Key-Hash

**When you see this:**
- 🕰️ Older wallet or service
- 💸 Higher transaction fees
- ⚠️ Less efficient

---

### 2. **Script Hash (P2SH)** - Starts with `3`
**Example:** `3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy`

- **What it means:** Multi-signature or complex script address
- **Length:** 34 characters
- **Transaction Fees:** Moderate
- **Who uses it:** Exchanges, institutional wallets, multi-sig setups
- **Format:** Pay-to-Script-Hash

**When you see this:**
- 🏦 Likely an exchange (Coinbase, Binance, Kraken, etc.)
- 🔐 Multi-signature wallet (requires multiple keys to spend)
- 🏛️ Institutional/corporate wallet
- 💼 Cold storage setup

**Why exchanges use it:**
- Enhanced security (requires multiple signatures)
- Can represent complex spending conditions
- Industry standard for large holders

---

### 3. **Native SegWit (Bech32)** - Starts with `bc1q`
**Example:** `bc1qf43tdrym26qlz8rg06f88wg35n27uhcf29zs4f`

- **What it means:** Modern, efficient SegWit address (Segregated Witness)
- **Length:** 42 characters (for P2WPKH)
- **Transaction Fees:** Lowest (40% cheaper than Legacy)
- **Who uses it:** Modern wallets (Electrum, BlueWallet, Ledger, Trezor)
- **Format:** Pay-to-Witness-Public-Key-Hash

**When you see this:**
- 💎 Modern, fee-conscious user
- ⚡ Most efficient transaction type
- ✅ Best practice for 2024+
- 🔤 Case-insensitive (can write in any case)

**Why it's better:**
- Lower fees (40% less than Legacy)
- More efficient use of blockchain space
- Built-in error detection
- Future-proof

---

### 4. **Taproot (Bech32m)** - Starts with `bc1p`
**Example:** `bc1p5cyxnuxmeuwuvkwfem96lqzszd02n6xdcjrs20cac6yqjjwudpxqkedrcr`

- **What it means:** Newest Bitcoin address type (2021)
- **Length:** 62 characters
- **Transaction Fees:** Lowest, even better than bc1q
- **Who uses it:** Cutting-edge wallets, privacy-focused users
- **Format:** Pay-to-Taproot

**When you see this:**
- 🚀 Most advanced Bitcoin tech
- 🔒 Enhanced privacy (all outputs look the same)
- 📉 Even lower fees
- 🤖 Enables complex smart contracts
- 💡 Early adopter

---

## How to Decode Whale Transactions

### Example Analysis

**Transaction:**
```
From: 3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy  (P2SH - starts with '3')
  To: bc1qf43tdrym26qlz8rg06f88wg35n27uhcf29zs4f  (SegWit - starts with 'bc1q')
```

**What this tells us:**
1. **Source (From):** `3...` = Multi-signature address
   - 🏦 **Likely:** Exchange withdrawal (Coinbase, Binance, Kraken, etc.)
   - 🏛️ **Or:** Institutional cold storage moving funds

2. **Destination (To):** `bc1q...` = Modern SegWit address
   - 💎 **Likely:** Personal wallet (Ledger, Trezor, BlueWallet)
   - ⚡ **User:** Fee-conscious, modern setup

**Most Likely Scenario:** 🏦➡️💎 Exchange withdrawal to personal wallet

---

## Common Transaction Patterns

### Exchange Withdrawal
```
From: 3... (Multisig)
  To: bc1q... (Personal SegWit)
```
💡 Someone withdrawing from an exchange to their personal wallet

### Exchange Deposit
```
From: bc1q... (Personal SegWit)
  To: 3... (Multisig)
```
💡 Someone depositing to an exchange (selling, trading)

### Institution-to-Institution
```
From: 3... (Multisig)
  To: 3... (Multisig)
```
💡 Exchange-to-exchange, or corporate transfers

### Modern Peer-to-Peer
```
From: bc1q... (SegWit)
  To: bc1q... (SegWit)
```
💡 Modern wallet users, fee-optimized

### Old Wallet Activity
```
From: 1... (Legacy)
  To: ?
```
⚠️ Old wallet, potentially dormant funds moving, higher fees

---

## Dashboard Address Badges

In the whale transaction dashboard, you'll see colored badges:

- **Legacy** (Gray) - Old format, higher fees
- **Multisig** (Purple) - Multi-signature, likely exchange/institution
- **SegWit** (Green) - Modern, efficient, personal wallet
- **Taproot** (Orange) - Newest, most advanced

---

## Quick Reference

| Prefix | Type | Fee Level | Common Use |
|--------|------|-----------|------------|
| `1...` | Legacy (P2PKH) | High | Old wallets |
| `3...` | Multisig (P2SH) | Medium | Exchanges, institutions |
| `bc1q...` | SegWit (Bech32) | Low | Modern wallets |
| `bc1p...` | Taproot (Bech32m) | Lowest | Advanced users |

---

## Using the Address Decoder

We've created a utility to decode addresses programmatically:

```bash
# Analyze any Bitcoin address
.venv/bin/python scripts/bitcoin_address_decoder.py
```

Or use it in code:
```python
from scripts.bitcoin_address_decoder import decode_address_type, analyze_whale_addresses

# Decode single address
info = decode_address_type("bc1qf43tdrym26qlz8rg06f88wg35n27uhcf29zs4f")
print(info['format'])  # "Native SegWit (Bech32)"
print(info['explanation'])  # "Native SegWit address. Lower fees..."

# Analyze whale transaction
analysis = analyze_whale_addresses(
    "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",  # From
    "bc1qf43tdrym26qlz8rg06f88wg35n27uhcf29zs4f"   # To
)
print(analysis['transaction_hints'])
# ["🏦 Likely exchange withdrawal (multisig → personal wallet)"]
```

---

## Resources

- **View addresses on blockchain:** https://mempool.space/address/{address}
- **Bitcoin Wiki on Addresses:** https://en.bitcoin.it/wiki/Address
- **Technical spec (BIP84 - SegWit):** https://github.com/bitcoin/bips/blob/master/bip-0084.mediawiki
- **Technical spec (BIP341 - Taproot):** https://github.com/bitcoin/bips/blob/master/bip-0341.mediawiki

---

## Summary

When analyzing whale transactions:

1. **Look at the prefix** - tells you the address type
2. **Consider the pattern** - `3...` to `bc1q...` usually means exchange → personal
3. **Check mempool.space** - click the address links in the dashboard
4. **Use the badge colors** - quick visual reference for address types

The address type can give you hints about:
- Who's moving the funds (exchange, individual, institution)
- How fee-conscious they are
- How modern their wallet setup is
- Potential security setup (multisig vs single-sig)
