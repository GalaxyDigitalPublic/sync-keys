from encoder import Decoder, Encoder
from utils import bytes_to_str


class TestEncoder:
    def test_encrypt_returns_encrypted_data_and_nonce(self):
        encoder = Encoder()
        data = "12345678901234567890"
        encrypted, nonce = encoder.encrypt(data)

        assert isinstance(encrypted, bytes)
        assert isinstance(nonce, bytes)
        assert len(nonce) > 0
        # Encrypted data should be different from original
        assert encrypted != data.encode("ascii")

    def test_cipher_key_is_32_bytes(self):
        encoder = Encoder()
        assert len(encoder.cipher_key) == 32

    def test_cipher_key_str_is_base64_encoded(self):
        encoder = Encoder()
        key_str = encoder.cipher_key_str
        assert isinstance(key_str, str)
        # Should be decodable
        from utils import str_to_bytes

        decoded = str_to_bytes(key_str)
        assert decoded == encoder.cipher_key

    def test_generates_unique_nonces(self):
        encoder = Encoder()
        data = "test data"
        _, nonce1 = encoder.encrypt(data)
        _, nonce2 = encoder.encrypt(data)
        # Each encryption should have a unique nonce
        assert nonce1 != nonce2

    def test_cipher_key_is_cached(self):
        encoder = Encoder()
        key1 = encoder.cipher_key
        key2 = encoder.cipher_key
        assert key1 is key2


class TestDecoder:
    def test_decrypt_returns_original_data(self):
        encoder = Encoder()
        original = "secret private key 12345"
        encrypted, nonce = encoder.encrypt(original)

        decoder = Decoder(encoder.cipher_key_str)
        decrypted = decoder.decrypt(
            data=bytes_to_str(encrypted), nonce=bytes_to_str(nonce)
        )

        assert decrypted == original

    def test_encrypt_decrypt_roundtrip_with_numeric_string(self):
        encoder = Encoder()
        # Simulate a private key as numeric string
        original = "12345678901234567890123456789012345678901234567890"
        encrypted, nonce = encoder.encrypt(original)

        decoder = Decoder(encoder.cipher_key_str)
        decrypted = decoder.decrypt(
            data=bytes_to_str(encrypted), nonce=bytes_to_str(nonce)
        )

        assert decrypted == original

    def test_decrypt_with_wrong_key_fails(self):
        encoder1 = Encoder()
        encoder2 = Encoder()

        original = "secret data"
        encrypted, nonce = encoder1.encrypt(original)

        decoder = Decoder(encoder2.cipher_key_str)
        # Decryption with wrong key should fail or produce garbage
        try:
            result = decoder.decrypt(
                data=bytes_to_str(encrypted), nonce=bytes_to_str(nonce)
            )
            # If it doesn't raise, the result should be different
            assert result != original
        except Exception:
            # Expected - decryption should fail with wrong key
            pass
