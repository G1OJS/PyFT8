# Python FT8 Rx and Tx with Browser-based UI
V2.1.0:
* Getting ~50% of WSJT-x decodes
* Decodes finish about 1 second into the next frame
* Click-settable Rx freq gets priority decode
* Uses single time-frequency grid with 281 FFTs
* Simple decode sequence
    - scan spectrum for power, deduplicate frequencies, costas sync, LLR-LDPC-Unpack
* Tightly coded LDPC
* All in Python
* Visualisation of individual signals with costas overlays
* Browser-based UI in progress to enable use as WSJT-x replacement
* CAT control for PTT of IC-7100
* End to end loop tests to illustrate protocol & steps

<img width="981" height="382" alt="Capture" src="https://github.com/user-attachments/assets/8eb7c645-ab75-4e4f-8ce9-1dae6045e6ba" />
<img width="466" height="351" alt="Capture" src="https://github.com/user-attachments/assets/257e5a86-420b-4b82-aee0-ff360b93e3d4" />
<img width="1050" height="1000" alt="Figure_2" src="https://github.com/user-attachments/assets/087289d9-ec48-419e-875e-89012a3441f5" />

## Purpose
This is code that I'm playing with mainly for my own understanding, but I really hope it's helpful to anyone who wants to 
understand how FT8 works. I'm keen to avoid simply copying code from other people (or AI!), and generate my own Pythonic
solutions keeping code as tight and minimal as possible, whilst experimenting with different candidate selection algorithms
and decoding approaches.

## Approach
You won't find many comments in the code; I try to make things as obvious as possible via variable names and logical structure.
Also - this is mainly my plaything. Do feel free however to get in touch and ask how anything works. I might add some diagrams
etc at some point too - especially if I find an approach that seems to offer something improved and/or very compact.

## Limitations
In pursuit of tight code, I've concentrated on core standard messages, leaving out some of the less-used features.

## Acknowledgements
This project implements a decoder for the FT8 digital mode.
FT8 was developed by Joe Taylor, K1JT, Steve Franke, K9AN, and others as part of the WSJT-X project.
Protocol details are based on information publicly described by the WSJT-X authors and in related open documentation.

Some constants and tables (e.g. Costas synchronization sequence, LDPC structure, message packing scheme) are derived from 
the publicly available WSJT-X source code and FT8 protocol descriptions. Original WSJT-X source is © the WSJT Development Group 
and distributed under the GNU General Public License v3 (GPL-3.0), hence the use of GPL-3.0 in this repository.

Also thanks to [Robert Morris](https://github.com/rtmrtmrtmrtm) for: 
 - [basicft8](https://github.com/rtmrtmrtmrtm/basicft8) - the first code I properly read (note: applies to FT8 pre V2)
 - [weakmon](https://github.com/rtmrtmrtmrtm/weakmon/) - much good information

Other useful resources:
 - [W4KEK WSJT-x git mirror](https://www.repo.radio/w4kek/WSJT-X)
 - [VK3JPK's FT8 notes](https://github.com/vk3jpk/ft8-notes)
 - [Web-888 FT8 skimmer](https://www.rx-888.com/web/design/digi.html)
 - [WSJT-X on Sourceforge](https://sourceforge.net/p/wsjt/wsjtx/ci/master/tree/")
 - [Declercq_2003_TurboCodes.pdf](https://perso.etis-lab.fr/declercq/PDF/ConferencePapers/Declercq_2003_TurboCodes.pdf)
 - [Q65 coding discussion](https://groups.io/g/wsjtgroup/topic/q65_q65_coding/98823709#)
 - [G4JNT notes on LDPC coding process](http://www.g4jnt.com/WSJT-X_LdpcModesCodingProcess.pdf)
 - [FT8Play - full details of message to bits etc](https://pengowray.github.io/ft8play/)
 - [Post about ft8play](https://groups.io/g/FT8-Digital-Mode/topic/i_made_a_thing_ft8play/107846361)
 - [FT8_lib](https://github.com/kgoba/ft8_lib)
 - [Decoding LDPC Codes with Belief Propagation | by Yair Mazal](https://yair-mz.medium.com/decoding-ldpc-codes-with-belief-propagation-43c859f4276d)
 - ['DX-FT8-Transceiver' source code](https://github.com/chillmf/DX-FT8-Transceiver-Source-Code_V2)

<script data-goatcounter="https://g1ojs-github.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
