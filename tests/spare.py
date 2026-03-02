import numpy as np
import matplotlib.pyplot as plt
import pickle



with open('batch_decodes.pkl', 'rb') as f:
    decodes = pickle.load(f)

dt = [d['dt'] for d in decodes]
print(np.min(dt), np.max(dt)-15) 
