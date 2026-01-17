# PyFT8 [![PyPI Downloads](https://static.pepy.tech/personalized-badge/pyft8?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/pyft8)
# FT8 Decoding and Encoding in Python with CLI and research code
This repository contains Python code to decode and encode (all the way to audio) FT8, plus a minimal Command Line Interface for reception, and a nascent set of research code.
<img width="960" height="540" alt="Untitled presentation" src="https://github.com/user-attachments/assets/93ce8755-9d49-423c-9f35-d96eb9067740" />

This started out as me thinking "How hard can it be, really?" and has become a bit of a mission to provide the most direct,
compact, and fast FT8 decoder that I can without copying code from elsewhere, apart from constants of course. 

As I'm still exploring decoding techniques, I'm necessarily developing tools to expose what's going on in the signal's jouney from received audio to printed text. These tools aren't polished, though I'm trying to do that as I go along.

The code itself is light on explanation, but I've avoided anonymous variable names like 'n5_b' as much as possible in favour of varable names that tell the story. Also, whilst I've used AI to introduce me to coding best practice and DSP techniques, I don't let their bloat survive the cut. This has
been productive - constantly badgering AI has resulted in a very compact and very fast LDPC decoder which has increased in speed
by about 2 orders of magnitude since I first hand-translated some FORTRAN into Python.

This repository is usually a little ahead of the releases I send to PyPI, but you can pip install it from there and just use the CLI if you want to
```
pip install PyFT8
```
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

Also thanks to [Robert Morris](https://github.com/rtmrtmrtmrtm) for: 
 - [basicft8(*1)](https://github.com/rtmrtmrtmrtm/basicft8) - the first code I properly read when I was wondering whether to start this journey 
 - [weakmon](https://github.com/rtmrtmrtmrtm/weakmon/) - much good information

(*1 note: applies to FT8 pre V2)

Other useful resources:
 - [W4KEK WSJT-x git mirror](https://www.repo.radio/w4kek/WSJT-X)
 - [VK3JPK's FT8 notes](https://github.com/vk3jpk/ft8-notes) including comprehensive [Python source code](https://github.com/vk3jpk/ft8-notes/blob/master/ft8.py)
 - [Optimizing the (Web-888) FT8 Skimmer Experience](https://www.rx-888.com/web/design/digi.html) Web-888 is a hardware digimode skimmer currenly covering FT4/FT8 & WSPR, part of the [RX-888 project](https://www.rx-888.com/).
 - [WSJT-X on Sourceforge](https://sourceforge.net/p/wsjt/wsjtx/ci/master/tree/")
 - [Declercq_2003_TurboCodes.pdf](https://perso.etis-lab.fr/declercq/PDF/ConferencePapers/Declercq_2003_TurboCodes.pdf)
 - [Q65 coding discussion](https://groups.io/g/wsjtgroup/topic/q65_q65_coding/98823709#)
 - [G4JNT notes on LDPC coding process](http://www.g4jnt.com/WSJT-X_LdpcModesCodingProcess.pdf)
 - [FT8Play - full details of message to bits etc](https://pengowray.github.io/ft8play/)
 - [Post about ft8play](https://groups.io/g/FT8-Digital-Mode/topic/i_made_a_thing_ft8play/107846361)
 - [FT8_lib](https://github.com/kgoba/ft8_lib)
 - [Decoding LDPC Codes with Belief Propagation | by Yair Mazal](https://yair-mz.medium.com/decoding-ldpc-codes-with-belief-propagation-43c859f4276d)
 - ['DX-FT8-Transceiver' source code](https://github.com/chillmf/DX-FT8-Transceiver-Source-Code_V2), the firmware part of the [DX-FT8 Transceiver project](https://github.com/WB2CBA/DX-FT8-FT8-MULTIBAND-TABLET-TRANSCEIVER) 
 - ['ft8modem - a command-line software modem for FT8'](https://www.kk5jy.net/ft8modem/) Matt Roberts' implementation as an FT8 modem with a CLI interface, including [source code (C++ and Python)](https://www.kk5jy.net/ft8modem/Software/) (bottom of page)

<script data-goatcounter="https://g1ojs-github.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
