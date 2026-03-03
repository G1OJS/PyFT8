# PyFT8 [![PyPI Downloads](https://static.pepy.tech/personalized-badge/pyft8?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/pyft8)
# All-Python FT8 Transceiver(WIP) GUI / Command Line Modem

This repository contains the source code for PyFT8, an all-Python open source FT8 transceiver that you can run as a basic GUI or from the command line to receive and transmit.

<img width="714" height="968" alt="image" src="https://github.com/user-attachments/assets/be165135-d18d-42d9-848c-c455b9d99275" />

## Motivation
This started out as me thinking "How hard can it be, really?" after some frustration with Windows moving sound devices around and wanting to get a minimal decoder running that I can fully control. 

I didn’t want to produce yet another port of the original Fortran / C into another language: instead I wanted to see how far I could get following audio -> spectrogram -> symbols -> bits -> error correction without resyncs and special treatments, writing my own code from scratch as far as possible. Also this has been, more than I expected, an exercise in writing Python ‘Pythonically’ for speed, which means absolutely not duplicating the big nested loops of Fortran and C. It also means writing code that is wide and short rather than thin and long, which suits my thinking style perfectly!

## Installation
If you want to install this software without getting into the code, you can install from PyPI using pip install, using

```
pip install PyFT8
```

Once installed, you can use the following commands to run it. 

|Usage | Command | Notes |
|----------------------|----------------------|----------------------|
|Basic Rx GUI | pyft8 -i "Keyword1, Keyword2" | Keywords identify the input sound device - partial match is fine, e.g. "Mic, CODEC"|
|GUI with transmit (under development) | pyft8 -i "Keyword1, Keyword2" -o "Keyword1, Keyword2" | Keywords identify the input (-i) and output (-o) sound devices|
| Command line Rx without a GUI | pyft8 -i "Keyword1, Keyword2" -n| |
| Command line transmit | pyft8 -o "Keyword1, Keyword2" -m "CQ G1OJS IO90"| Tx on next cycle. You supply the PTT control method.|
| Command line create a wav file | pyft8 -w "Mywav.wav" -m "CQ G1OJS IO90"| -w "Mywav.wav" can be omitted |

Otherwise, please download or browse the code, or fork the repo and play with it! If you do fork it, please check back here as I'm constantly (as of Jan 2026) rewriting and improving.

## Performance Compared with FT8_lib and WSJT-x

The image below shows the number of decodes from PyFT8, WSJT-x V2.7.0 running in NORM mode, and FT8_lib, using the same 10 minutes of busy 20m audio that is used to test ft8_lib. 

<img width="640" height="480" alt="performance snapshot" src="https://github.com/user-attachments/assets/c19bd1c9-60ac-4d97-81b1-bbcea9bb821b" />


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
 - [WSJT-X on Sourceforge](https://sourceforge.net/p/wsjt)
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
