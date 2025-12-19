from utils import bytes_to_str, is_lists_equal, str_to_bytes


class TestIsListsEqual:
    def test_equal_lists_same_order(self):
        assert is_lists_equal([1, 2, 3], [1, 2, 3]) is True

    def test_equal_lists_different_order(self):
        assert is_lists_equal([1, 2, 3], [3, 2, 1]) is True

    def test_different_lists(self):
        assert is_lists_equal([1, 2, 3], [1, 2, 4]) is False

    def test_different_lengths(self):
        assert is_lists_equal([1, 2], [1, 2, 3]) is False

    def test_empty_lists(self):
        assert is_lists_equal([], []) is True

    def test_with_duplicates(self):
        assert is_lists_equal([1, 1, 2], [1, 2, 1]) is True
        assert is_lists_equal([1, 1, 2], [1, 2, 2]) is False


class TestBytesStrConversion:
    def test_bytes_to_str(self):
        result = bytes_to_str(b"hello")
        assert isinstance(result, str)
        assert result == "aGVsbG8="  # base64 of "hello"

    def test_str_to_bytes(self):
        result = str_to_bytes("aGVsbG8=")
        assert isinstance(result, bytes)
        assert result == b"hello"

    def test_roundtrip_bytes_to_str_to_bytes(self):
        original = b"test data with special chars: \x00\xff"
        encoded = bytes_to_str(original)
        decoded = str_to_bytes(encoded)
        assert decoded == original

    def test_roundtrip_str_to_bytes_to_str(self):
        original = "dGVzdCBkYXRh"  # base64 encoded "test data"
        decoded = str_to_bytes(original)
        encoded = bytes_to_str(decoded)
        assert encoded == original
