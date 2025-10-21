"""
bitfield.py
------------
Unified representation of binary data for FT8/FT4/WSPR modes.

Features:
    - construct from int, list of bits, or bitstring
    - lazy conversion between forms
    - Gray encode/decode helpers
    - generic CRC calculation (includes WSJT-X CRC14)
"""

import numpy as np

class BitField:
    def __init__(self, value, width=None):
        """Create from int, iterable of bits, or bitstring."""
        if isinstance(value, int):
            self._int = value
            self._width = width or max(1, value.bit_length())
        elif isinstance(value, (list, np.ndarray)):
            self._width = width or len(value)
            bits = "".join(str(int(b)) for b in value)
            self._int = int(bits, 2)
        elif isinstance(value, str):
            self._width = width or len(value)
            self._int = int(value, 2)
        else:
            raise TypeError(f"Unsupported BitField type: {type(value)}")

    # ---- Core representations ----
    @property
    def int(self):
        """Integer value."""
        return self._int

    @property
    def bits(self):
        """List of bits, MSB-first."""
        return [(self._int >> i) & 1 for i in reversed(range(self._width))]

    @property
    def bitstring(self):
        """Bitstring '010101'."""
        return "".join(str(b) for b in self.bits)

    def __len__(self):
        return self._width

    def __int__(self):
        return self._int

    def __str__(self):
        return self.bitstring

    # ---- Basic operations ----
    def __xor__(self, other):
        if not isinstance(other, BitField):
            return NotImplemented
        return BitField(self._int ^ other._int, max(self._width, other._width))

    def concat(self, other):
        """Concatenate two BitFields (self|other)."""
        return BitField((self._int << len(other)) | other._int,
                        self._width + len(other))

    # ---- Gray code helpers ----
    @staticmethod
    def gray_encode(n: int) -> int:
        """Return Gray-coded integer."""
        return n ^ (n >> 1)

    @staticmethod
    def gray_decode(g: int) -> int:
        """Return integer decoded from Gray code."""
        n = 0
        while g:
            n ^= g
            g >>= 1
        return n

    # ---- CRC helpers ----
    def crc(self, poly: int, width: int, init: int = 0, refin=False, refout=False) -> int:
        """
        Generic bitwise CRC calculator (MSB-first).
