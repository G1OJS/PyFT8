import numpy as np

r = np.load(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8\dumps\candidate_20251018_094515_2425.0.npz")

# Unpack all arrays into variables with the same names as the keys
llr, bits, spectrum, meta = (r[k] for k in ['llr', 'bits', 'spectrum', 'meta'])

# Now you can use them directly
print(llr)
print(bits)
print(spectrum)
