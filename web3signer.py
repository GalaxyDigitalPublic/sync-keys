from typing import Dict, List

import click
from eth_typing import HexStr

from encoder import Encoder
from typings import DatabaseKeyRecord, DBKeyInfo
from utils import bytes_to_str


class Web3SignerManager:
    def __init__(
        self,
        validator_capacity: int,
    ):
        self.validator_capacity = validator_capacity
        self.encoder = Encoder()

    def process_transferred_keypairs(
        self, keypairs: Dict[HexStr, DBKeyInfo]
    ) -> List[DatabaseKeyRecord]:
        """
        Returns prepared database key records from the transferred private keys.
        """

        key_records: List[DatabaseKeyRecord] = list()
        index = 0

        with click.progressbar(
            length=len(keypairs),
            label="Processing transferred key pairs:\t\t",
            show_percent=False,
            show_pos=True,
        ) as bar:
            for public_key, (private_key, fee_recipient) in keypairs.items():
                encrypted_private_key, nonce = self.encoder.encrypt(str(private_key))

                key_record = DatabaseKeyRecord(
                    public_key=public_key,
                    private_key=bytes_to_str(encrypted_private_key),
                    nonce=bytes_to_str(nonce),
                    validator_index=index // self.validator_capacity,
                    fee_recipient=fee_recipient,
                )
                key_records.append(key_record)
                index += 1
                bar.update(1)

        return key_records
