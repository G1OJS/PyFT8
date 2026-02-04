# PyFT8 [![PyPI Downloads](https://static.pepy.tech/personalized-badge/pyft8?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/pyft8)
# FT8 Decoding and Encoding in Python with CLI and research code
This repository contains Python code to decode and encode (all the way to audio) FT8, plus a minimal Command Line Interface for reception, and a nascent set of research code. 
<img width="960" height="540" alt="Untitled presentation" src="https://github.com/user-attachments/assets/93ce8755-9d49-423c-9f35-d96eb9067740" />



## Motivation
This started out as me thinking "How hard can it be, really?" after some frustration with Windows moving sound devices around and wanting to get a minimal decoder running that I can fully control. 

I didn’t want to produce yet another port of the original Fortran / C into another language: instead I wanted to see how far I could get following audio -> spectrogram -> symbols -> bits -> error correction without resyncs and special treatments, writing my own code from scratch as far as possible. Also this has been, more than I expected, an exercise in writing Python ‘Pythonically’ for speed, which means absolutely not duplicating the big nested loops of Fortran and C. It also means writing code that is wide and short rather than thin and long, which suits my thinking style perfectly!

My current aim is to push the low SNR performance whilst using only one time/frequency grid and no time-domain processing. 

Code I'd like to highlight, all in 100% Python:
* [LDPC using just three 5~8 line functions](https://github.com/G1OJS/PyFT8/blob/main/PyFT8/ldpc.py) and running 250 us per iteration on a Dell Optiplex
* [Ordered Statistics Decoding](https://github.com/G1OJS/PyFT8/blob/main/PyFT8/osd.py) in about 60 lines of code & similarly fast (not measured yet)

## Uses
I use this code for my own hobby-level reseearch into FT8 decoding and Python coding techniques, and I'm also building a browser-GUI station controller (image below) which has an FT8 transceiver integrated within it. You can see that [here](https://github.com/G1OJS/station-gui) but note that it's focussed on my station, i.e. ICOM-IC-7100 with an Arduino controlling antenna switching and magloop tuning.

<img width="1521" height="815" alt="station-gui" src="https://github.com/user-attachments/assets/973eb8b5-8017-4e57-b3b5-a26cea0f4b4a" />

## Performance
On a quiet band with good signals, PyFT-8 typically gets 70% or 80% and often 100% of WSJT-x decodes. On a crowded band, PyFT8 performs less well. WSJT-x uses signal subtraction to improve performance with overlapping signals. PyFT8 can decode overlapping signals surprisingly well, but not as well as WSJT-x. The plots below show real world performance on 10m and 20m respectively over lunchtime, with relatively many signals.

<img width="1000" height="600" alt="20m lunchtime hanning window 4persymb 2pertone" src="https://github.com/user-attachments/assets/988b5b78-ee8d-4d61-b1ba-87bdcba969c1" />
<img width="1000" height="600" alt="10m lunchtime hanning window 4persymb 2pertone" src="https://github.com/user-attachments/assets/9c7d8e73-87fe-499f-acd4-4b14d17e37b4" />

I have been using the file "210703_133430.wav" (third plot above) as a reference. In NORM mode, WSJT-x gets 19 decodes. WSJT-x in FAST mode gets 14 decodes, PyFT8 gets 12, and FT8_lib gets 8. The specific decodes are shown in the table below.

<img width="658" height="429" alt="image" src="https://github.com/user-attachments/assets/3d5fc12c-b36b-4297-ac44-f3ba287a123c" />

However, a single wav file with a single FT8 cycle is not sufficient to characterise performance - it's been good for developing, but it's not enough for characterising. So, I've taken a step further by rewriting the decoding code to allow tests to be run in batch mode using a folder of 15s wav files. The image below shows the number of decodes from PyFT8 and FT8_lib both as a percentage of WSJT-x V2.7.0 running in NORM mode. The source wav files are copied from [https://github.com/kgoba/ft8_lib/tree/master/test/wav/20m_busy](https://github.com/kgoba/ft8_lib/tree/master/test/wav/20m_busy), and I've run ft8_lib and PyFT8 for all 38 of them, as well as updating the WSJT-X results to version 2.7.0.

<img width="640" height="480" alt="20m_busy_batch_tests_results_2bpt_4bps tweaked params" src="https://github.com/user-attachments/assets/e1a15f41-c9cc-4508-90b5-5ebe74d612fd" />

These tests show that PyFT8 is within a few percent of FT8_lib's performance over all 38 'busy' 20m wav file tests. Reading FT8_lib's source code gave me a few good tips to improve performance to this level:
* Swap my previous Kaiser(20) fft window for a Hanning window, at the same time as changing from 3 frequency bins per tone to 2.
* Dial down the use of OSD to improve speed
* The killer, lurking in my code and forgotten; expand the timing tolerance for signal start from my previous 0 to +1.9 seconds to a range of -1.12 to +3.48 seconds(*), allowing for signals starting as early as the cycle boundary corresponding to the first *data* symbol (#8 of 79) and signals ending as late as 15s corresponding to the last *data* symbol (#72 of 79). I had previously been throwing away good candidates!

<sub> (*) How do you sync a signal whose sync block starts before t=0? Simple - use the second Costas block in the middle of the signal.</sub>

## Contents
[being written]
* [Overview of main code and decoding process](https://github.com/G1OJS/PyFT8/blob/main/docs/main_code.md)
* [Testing and research code](https://github.com/G1OJS/PyFT8/blob/main/docs/testing_research.md)



## Installation
This repository is usually a little ahead of the releases I send to PyPI, but you can pip install it from there and just use the Command Line Interface (which can also transmit individual messages) if you want to.

<img width="981" height="511" alt="cmd" src="https://github.com/user-attachments/assets/a3df103a-0a43-4da6-a3b1-8825012f07b0" />


Install using:
```
pip install PyFT8
```

And to run, use the following (more info [here](https://github.com/G1OJS/PyFT8/blob/main/docs/cli.md))
```
PyFT8_cli "Keyword1, Keyword2" [-c][-v]
```
<sub> * where keywords identify the sound device - partial match is fine - and -c = concise, -v = verbose</sub>

Otherwise, please download or browse the code, or fork the repo and play with it! If you do fork it, please check back here as I'm constantly (as of Jan 2026) rewriting and improving.

## Limitations
In pursuit of tight code, I've concentrated on core standard messages, leaving out some of the less-used features. The receive part of the
code doesn't (yet) have the full capability of the advanced decoders used in WSJT-x, and so gets only about 60% of the decodes that WSJT-x gets, depending on band conditions (on a quiet band with only good signals PyFT8 will get close to 100%).

## Acknowledgements
This project implements a decoder for the FT8 digital mode.
FT8 was developed by Joe Taylor, K1JT, Steve Franke, K9AN, and others as part of the WSJT-X project.
Protocol details are based on information publicly described by the WSJT-X authors and in related open documentation.

Some constants and tables (e.g. Costas synchronization sequence, LDPC structure, message packing scheme) are derived from 
the publicly available WSJT-X source code and FT8 protocol descriptions. Original WSJT-X source is © the WSJT Development Group 
and distributed under the GNU General Public License v3 (GPL-3.0), hence the use of GPL-3.0 in this repository.

Also thanks to [Robert Morris](https://github.com/rtmrtmrtmrtm) for [basicft8(*1)](https://github.com/rtmrtmrtmrtm/basicft8) - the first code I properly read when I was wondering whether to start this journey. (*1 note: applies to FT8 pre V2)

## Useful resources:
**WSJTx - focussed:**
 - [WSJT-X on Sourceforge](https://sourceforge.net/p/wsjt/wsjtx/ci/master/tree/")
 - [W4KEK WSJT-x git mirror](https://www.repo.radio/w4kek/WSJT-X) (searchable)

**Other FT8 decoding repos:**
- [weakmon](https://github.com/rtmrtmrtmrtm/weakmon/)
- [FT8_lib](https://github.com/kgoba/ft8_lib)
- ['ft8modem - a command-line software modem for FT8'](https://www.kk5jy.net/ft8modem/) including [source code (C++ and Python)](https://www.kk5jy.net/ft8modem/Software/) (bottom of page)

**FT8 decoding explorations / explanations**
 - [VK3JPK's FT8 notes](https://github.com/vk3jpk/ft8-notes) including comprehensive [Python source code](https://github.com/vk3jpk/ft8-notes/blob/master/ft8.py)
 - [G4JNT notes on LDPC coding process](http://www.g4jnt.com/WSJT-X_LdpcModesCodingProcess.pdf)

**FT8 decoding in hardware**
 - [Optimizing the (Web-888) FT8 Skimmer Experience](https://www.rx-888.com/web/design/digi.html) (see also [RX-888 project](https://www.rx-888.com/) )
 - ['DX-FT8-Transceiver' source code](https://github.com/chillmf/DX-FT8-Transceiver-Source-Code_V2), the firmware part of the [DX-FT8 Transceiver project](https://github.com/WB2CBA/DX-FT8-FT8-MULTIBAND-TABLET-TRANSCEIVER)
   
**FT8 encode/decode simulators:**
 - [FT8Play - full details of message to bits etc](https://pengowray.github.io/ft8play/)
 - [Post about ft8play](https://groups.io/g/FT8-Digital-Mode/topic/i_made_a_thing_ft8play/107846361)

**Browser-based decoder/encoders**
 - [ft8js](https://e04.github.io/ft8js/example/browser/index.html) - source [github](https://github.com/e04/ft8js?tab=readme-ov-file), uses [FT8_lib](https://github.com/kgoba/ft8_lib)
 - [ChromeFT8 Browser Extension](https://github.com/Transwarp8/ChromeFT8), decoder adapted from [ft8js](https://e04.github.io/ft8js/example/browser/index.html)

<script data-goatcounter="https://g1ojs-github.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
