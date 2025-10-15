
from src.FT8_demodulator import FT8Demodulator
from src.FT8_decoder import FT8_decode
from src.waterfall import Waterfall

demod = FT8Demodulator()
wf = Waterfall(demod.specbuff)

def read_wav(filename, chunk_size=1024, sample_rate = 12000):
     import wave
     import numpy as np
     with wave.open(filename, 'rb') as wav:
          assert wav.getframerate() == sample_rate
          assert wav.getnchannels() == 1
          assert wav.getsampwidth() == 2
          audio = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16)
     return audio
          
audio = read_wav('tests/210703_133430.wav')
demod.specbuff.load_TFGrid(audio)
candidates = demod.get_candidates(topN=5)
wf.update(demod.specbuff, candidates = candidates)
demod.demodulate(candidates)
print(FT8_decode(candidates, ldpc = False))





#133430  17  0.3 2571 ~  W1FC F5BZB -08
#133430  15 -0.1 2157 ~  WM3PEN EA6VQ -09
#133430  -3 -0.8 1197 ~  CQ F5RXL IN94      France
#133430 -13  0.3  641 ~  N1JFU EA6EE R-07
#133430  -9  0.1  723 ~  A92EE F5PSR -14
#133430  -3 -0.1 2695 ~  K1BZM EA3GP -09
#133430 -15  0.3  400 ~  W0RSJ EA3BMU RR73
#133430 -15  0.3  590 ~  K1JT HA0DU KN07
#133430  -7  0.4 2733 ~  W1DIG SV9CVY -14
#133430 -15  0.1 1648 ~  K1JT EA3AGB -15
#133430 -13  0.2 2852 ~  XE2X HA2NP RR73
#133430  -6  0.2 2522 ~  K1BZM EA3CJ JN01
#133430  -8 -0.1 2546 ~  WA2FZW DL5AXX RR73
#133430 -12  0.3 2238 ~  N1API HA6FQ -23
#133430  -2  0.2  466 ~  N1PJT HB9CQK -10
#133430 -17  0.7 1513 ~  N1API F2VX 73
#133430 -16  0.2 2606 ~  CQ DX DL8YHR JO41  Germany
#133430 -18  0.1 2039 ~  K1JT HA5WA 73
#133430  -6  0.4  472 ~  KD2UGC F6GCP R-23
#133430 -15  0.1 2280 ~  CQ EA2BFM IN83     Spain
#133430 -17  0.5  244 ~  K1BZM DK8NE -10



