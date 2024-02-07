import collections
from typing import List


def is_lists_equal(x: List, y: List) -> bool:
    return collections.Counter(x) == collections.Counter(y)
