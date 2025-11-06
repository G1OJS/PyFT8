Document in progress to show details of creating an FT8 signal, adding it to an existing spectrum with other FT8 signals, and decoding the resulting merged spectrum to recover the original signal. 

The background spectrum is from '210703_133430.wav' which contains the following signals as decoded by WSJT-x (bold entries are also decoded by PyFT8 in this test):

<pre>
<strong>133430  17  0.3 2571 ~  W1FC F5BZB -08</strong>
<strong>133430  15 -0.1 2157 ~  WM3PEN EA6VQ -09</strong>
133430  -3 -0.8 1197 ~  CQ F5RXL IN94  
<strong>133430 -13  0.3  641 ~  N1JFU EA6EE R-07</strong>
<strong>133430  -9  0.1  723 ~  A92EE F5PSR -14</strong>
133430  -3 -0.1 2695 ~  K1BZM EA3GP -09
133430 -15  0.3  400 ~  W0RSJ EA3BMU RR73
<strong>133430 -15  0.3  590 ~  K1JT HA0DU KN07</strong>
133430  -7  0.4 2733 ~  W1DIG SV9CVY -14
133430 -15  0.1 1648 ~  K1JT EA3AGB -15
133430 -13  0.2 2852 ~  XE2X HA2NP RR73
133430  -6  0.2 2522 ~  K1BZM EA3CJ JN01
133430  -8 -0.1 2546 ~  WA2FZW DL5AXX RR73
133430 -12  0.3 2238 ~  N1API HA6FQ -23
133430  -2  0.2  466 ~  N1PJT HB9CQK -10
133430 -17  0.7 1513 ~  N1API F2VX 73
133430 -16  0.2 2606 ~  CQ DX DL8YHR JO41 
133430 -18  0.1 2039 ~  K1JT HA5WA 73
133430  -6  0.4  472 ~  KD2UGC F6GCP R-23
133430 -15  0.1 2280 ~  CQ EA2BFM IN83  
133430 -17  0.5  244 ~  K1BZM DK8NE -10
</pre>

The added signal is 'VK1ABC VK3JPK QF22' and can be seen in the outlined pattern at about 870 Hz.

<img width="987" height="262" alt="waterfall" src="https://github.com/user-attachments/assets/62bded92-5113-49c3-9287-70bcf4cef60b" />
<img width="1039" height="986" alt="candidate detail" src="https://github.com/user-attachments/assets/8eb14426-a4ec-4cb9-a563-92b9a6965511" />
<img width="1494" height="790" alt="output" src="https://github.com/user-attachments/assets/dc212f1a-3103-4bc3-80c2-713fa6ffe5cb" />
