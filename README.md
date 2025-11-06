# Python FT8 Rx and Tx with Browser-based UI
This project provides a working demo of the entire FT8 coding and decoding chain, with a working browser-based GUI.
Although the code is light on comments, I've tried to use clear variable names and structure to make the need for comments minimal. 
I've also tried to keep the code free from 'dead code' that isn't used, and generate my own 'Pythonic' solutions keeping code as 
tight and minimal as possible rather than copy from other online sources or AI (!). I chose to put the GUI in a browser because
this allows customisation with css etc, and provides some separation between the tranmit/receive code and the GUI code.

<img width="891" height="788" alt="Capture" src="https://github.com/user-attachments/assets/23351f0f-5d04-476a-87c3-26c3913a76b4" />

Below are some screenshots from test programs that can be used to look at how the protocols actually work, illustrated with a fairly
ordinary waterfall and some zoomed-in depictions of captured signals with an overlay of the syncrhonisation tones that are used
to search for the signals (Costas patterns).

<img width="981" height="382" alt="Capture" src="https://github.com/user-attachments/assets/8eb7c645-ab75-4e4f-8ce9-1dae6045e6ba" />
<img width="1050" height="1000" alt="Figure_2" src="https://github.com/user-attachments/assets/087289d9-ec48-419e-875e-89012a3441f5" />

## Approach
You won't find many comments in the code; I try to make things as obvious as possible via variable names and logical structure, to 
minimise the *need for* comments. Also - this is mainly my plaything, and I find bloated, sprawling code incredibly difficult to 
read, so I like to keep things very compact so that I can see the bigger picture. If you find an if-then-else spanning several
paragraphs, it's probably a mistake.

Do feel free to get in touch and ask how anything works. I might add some diagrams etc at some point too - especially
if I find an approach that seems to offer something improved and/or very compact (I'm very pleased for e.g. that the entire candidate
search, synch, and demodulate process all works by refering to a single time-frequency grid; read the audio, FFT 3 times for each 
symbol duration, store it, and that's used for everything that follows.)

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
 - [basicft8(*1)](https://github.com/rtmrtmrtmrtm/basicft8) - the first code I properly read when I was wondering whether to start this journey 
 - [weakmon](https://github.com/rtmrtmrtmrtm/weakmon/) - much good information

(*1 note: applies to FT8 pre V2)

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
