"""
signaldefs.py
-------------
Defines the signal-specific constants for FT8, FT4, WSPR, etc.
"""

from dataclasses import dataclass

@dataclass(frozen=True)
class SignalSpec:
    name: str
    frame_secs: float
    symbols_persec: float
    num_symbols: int
    tones_persymb: int
    costas: list[int] | None = None


# ---- Standard WSJT-X modes ----
FT8  = SignalSpec("FT8",  frame_secs=15.0,  symbols_persec=6.25,  num_symbols=79,  tones_persymb=8,
                  costas=[3,1,4,0,6,5,2])

FT4  = SignalSpec("FT4",  frame_secs=7.5,   symbols_persec=12.5,  num_symbols=105, tones_persymb=4,
                  costas=[1,0,3,2,4,5])

WSPR = SignalSpec("WSPR", frame_secs=110.6, symbols_persec=1.4648, num_symbols=162, tones_persymb=4)
