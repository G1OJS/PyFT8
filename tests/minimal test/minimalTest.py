#!/usr/bin/env python3
import os
import sys
import threading

from PyFT8.receiver import Receiver, AudioIn
nDecodes = 0

def on_decode(c):
    global nDecodes
    msg = getattr(c, 'msg', None)
    if msg is not None:
        nDecodes += 1
        print(f"{nDecodes:03d}:{msg} {c.h0_idx * 0.16/4, c.f0_idx * 6.25/2}")
   
wav_file = os.path.join('./', 'test_01.wav')
audio_in = AudioIn(3100, [wav_file])
rx = Receiver(audio_in, [200, 3100], on_decode, None)
audio_in.start_wav_load()


