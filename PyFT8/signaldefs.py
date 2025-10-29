"""
signaldefs.py
-------------
Defines the signal-specific constants for FT8, FT4, WSPR, etc.
"""

from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True)
class SignalSpec:
    name: str
    frame_secs: float
    symbols_persec: float
    num_symbols: int
    tones_persymb: int
    costas: list[int] | None = None
    costas_len: int  | None = None
    gray_map: list[int]  | None = None
    gray_map_tuples: list[()]  | None = None
    gray_mask: bool   | None = None

# ---- FT8 ----
gray_map_tuples = [(0,0,0),(0,0,1),(0,1,1),(0,1,0),(1,1,0),(1,0,0),(1,0,1),(1,1,1)]
gray_mask = np.array(gray_map_tuples, dtype=bool)
FT8  = SignalSpec("FT8",  frame_secs=15.0,  symbols_persec=6.25,  num_symbols=79,
                  tones_persymb=8, costas=[3,1,4,0,6,5,2], costas_len = 7,
                  gray_map = [0,1,3,2,5,6,4,7],gray_map_tuples = gray_map_tuples, gray_mask = gray_mask)

# ---- FT4 ----
FT4  = SignalSpec("FT4",  frame_secs=7.5,   symbols_persec=12.5,  num_symbols=105,
                  tones_persymb=4,  costas=[1,0,3,2,4,5], costas_len = 6)
# ---- WSPR ----
WSPR = SignalSpec("WSPR", frame_secs=110.6, symbols_persec=1.4648, num_symbols=162,
                  tones_persymb=4)
