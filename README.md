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
On a quiet band with good signals, PyFT-8 typically gets 70% or 80% and often 100% of WSJT-x decodes. On a crowded band, PyFT8 performs less well. WSJT-x uses signal subtraction to improve performance with overlapping signals. PyFT8 can decode overlapping signals surprisingly well, but not as well as WSJT-x. The three plots below, showing WSJT-x and PyFT8 decodes as a function of the standard deviation of the llr (a good proxy for signal decodability) show how the quieter band has fewer overlaps and allows PyFT8 a larger percentage of decodes.

<img width="1049" height="623" alt="image" src="https://github.com/user-attachments/assets/70064f89-2bb1-442d-be46-758bca4e6270" />

I have been using the file "210703_133430.wav" (third plot above) as a reference. In NORM mode, WSJT-x gets 19 decodes. WSJT-x in FAST mode gets 14 decodes, PyFT8 gets 12, and FT8_lib gets 8. The specific decodes are shown in the table below.

<img width="658" height="429" alt="image" src="https://github.com/user-attachments/assets/3d5fc12c-b36b-4297-ac44-f3ba287a123c" />

However, a single wav file with a single FT8 cycle is not sufficient to characterise performance - it's been good for developing, but it's not enough for characterising. So, I've taken a step further by rewriting the decoding code to allow tests to be run in batch mode using a folder of 15s wav files. The image below shows the number of decodes from PyFT8 and FT8_lib both as a percentage of WSJT-x V2.7.0 running in NORM mode, for three different configurations of the PyFT8 decoder. The source wav files are copied from [https://github.com/kgoba/ft8_lib/tree/master/test/wav/20m_busy](https://github.com/kgoba/ft8_lib/tree/master/test/wav/20m_busy), and I've run ft8_lib and PyFT8 for all 38 of them, but only run WSJT-x for 20 so far as it has to be manual cut and paste.

<img width="1039" height="580" alt="image" src="https://github.com/user-attachments/assets/5ec76b0c-3bc2-425f-8ee2-c99b6cc39d4f" />

It has to be said that adding OSD and bitflipping doesn't produce as significant a difference as I had hoped! So there is certainly scope for further development. I've also seen that despite my efforts to write fast Python, FT8_lib is still considerably faster (and probably faster than WSJT-x). Overall, ignoring WSJT-X, FT8_lib wins in terms of decode numbers, being beaten by PyFT8 on only a few occasions.



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
