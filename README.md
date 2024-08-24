# Overview

sync-keys is a helper script for eth-staking-charts. It was adapted from stakewise-cli.

# Use

Create a virtual environment and install prerequisites, then run `python3 sync_keys/main.py`


`sync-db` - takes `keystore*.json` files and uploads them to the keys database, e.g. `web3signer-keys`.
Web3signer and the validator clients will then load those keys from there.

`sync-db` takes a `postgresql://` URL and a directory name where the keystore files are.

All keys in the top level of that directory are imported without a specific fee recipient, and will use the
`suggestedFeeRecipient` of the validator chart.

Keys in a sub-directory which is named for an Ethereum address, in the form `0xEth-Hex-Address`, will use that address
as their fee recipient.

Keys in sub-directories which are named any other way will be ignored.

`sync-db` requires that all keys on the same directory level have the same password.
