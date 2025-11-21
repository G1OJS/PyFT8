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
    cycle_seconds: int
    signal_seconds: float
    payload_symb_idxs: list[int]
    tones_persymb: int
    bw_Hz: float
    costas: list[int] | None = None
    costas_len: int  | None = None
    gray_map: list[int]  | None = None
    gray_map_tuples: list[()]  | None = None
    gray_mask: bool   | None = None
    block_decode_wt2: int | None = None

# ---- FT8 ----
gray_map = np.array([[0,0,0],[0,0,1],[0,1,1],[0,1,0],[1,1,0],[1,0,0],[1,0,1],[1,1,1]])

# - weights for 2-symbol block decoder if used
w = np.zeros((6, 8, 8), dtype=np.int8)
for b in range(3):
    w[b] = np.where(gray_map[:, b].astype(bool)[:, None], +1, -1)
    w[b+3] = np.where(gray_map[:, b].astype(bool)[None, :], +1, -1)
block_decode_wt2 = w[None, :, :, :]

# gray mask for logaddexp decoder
gray_mask = np.array(gray_map, dtype=bool)

payload_symb_idxs = list(range(7, 36)) + list(range(43, 72))

FT8  = SignalSpec("FT8",  frame_secs=15.0,  symbols_persec=6.25, cycle_seconds = 15,
                  num_symbols=79, signal_seconds = 79*0.16, payload_symb_idxs = payload_symb_idxs,
                  tones_persymb=8, bw_Hz = 8*6.25, costas=[3,1,4,0,6,5,2], costas_len = 7,
                  gray_map = [0,1,3,2,5,6,4,7],
                  gray_mask = gray_mask,
                  block_decode_wt2 = block_decode_wt2)

# ---- FT4 ----
#FT4  = SignalSpec("FT4",  frame_secs=7.5,   symbols_persec=12.5,  num_symbols=105, payload_symb_idxs = []
#                  tones_persymb=4,  costas=[1,0,3,2,4,5], costas_len = 6)
# ---- WSPR ----
#WSPR = SignalSpec("WSPR", frame_secs=110.6, symbols_persec=1.4648, num_symbols=162, payload_symb_idxs = []
#                  tones_persymb=4)
