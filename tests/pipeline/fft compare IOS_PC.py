#!/usr/bin/env python3

import os, sys
import numpy as np
import time

script_dir = os.path.dirname(os.path.abspath(__file__))
#repo_root = os.path.dirname(script_dir)
files_root = os.path.dirname('⁨On My iPhone⁩/⁨Chrome⁩')
sys.path.insert(0, files_root)

x = np.random.randn(3200).astype(np.complex64)

t0 = time.perf_counter()
for i in range(10000):
    np.fft.ifft(x)

print(time.perf_counter()-t0)
        
   
    
