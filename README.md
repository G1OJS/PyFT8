# Python FT8 Rx and Tx with Browser-based UI
PyFT8 provides useable FT8 transceiving capability in a web browser, with minimal open source Python code.

It's in development (22-Nov 2025) and I hope to make it more useable for those who don't necessarily want to dig into the code.

## Key features of V5.0.4:
* Gets up to 50% of WSJT-x decodes using a very much simpler algorithm
* Gets decodes around 1 to 2 seconds *before* WSJT-X does
* Browser-based UI 'transceiver' can be used to make FT8 QSOs (Rx and Tx, just like WSJT-X)
     - Note: could be developed to run your FT8 station over the web!
* Option to use WSJT-X as an external decoder instead of the internal PyFT8 one
* CAT support for Icom IC-7100 (more to follow)
* No dependence on Hamlib or Omnirig
* Finds sound devices by *name* so is immune to Windows reordering sound devices
* Open source Python code includes test code aimed at *illustrating* the entire encode->modulate->demodulate->decode chain
* Uses only Python and Javascript

This project provides a working demo of the entire FT8 coding and decoding chain, with a working browser-based GUI.

Although the code is light on comments, I've tried to use clear variable names and structure to make the need for comments minimal. 
I've also tried to keep the code free from 'dead code' that isn't used, and generate my own 'Pythonic' solutions keeping code as 
tight and minimal as possible rather than copy from other online sources or AI (!). 

I chose to put the GUI in a browser because this allows customisation with css etc, and provides some separation between the tranmit/receive code and the GUI code.

I'm starting a document here to show the results of the end-to-end loop test: [link](https://github.com/G1OJS/PyFT8/blob/main/docs/End-to-end-loop-test.md)

<img width="891" height="788" alt="Capture" src="https://github.com/user-attachments/assets/23351f0f-5d04-476a-87c3-26c3913a76b4" />

Below are some screenshots from test programs that can be used to look at how the protocols actually work, illustrated with a fairly
ordinary waterfall and some zoomed-in depictions of captured signals with an overlay of the syncrhonisation tones that are used
to search for the signals (Costas patterns).

<img width="987" height="262" alt="waterfall" src="https://github.com/user-attachments/assets/bb97c336-3150-466d-b102-1885fff971b4" />

<img width="1039" height="986" alt="candidate detail" src="https://github.com/user-attachments/assets/cc9ad981-77b1-4997-a1c5-688589342ae9" />

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
In pursuit of tight code, I've concentrated on core standard messages, leaving out some of the less-used features. The receive part of the
code doesn't (yet) have the full capability of the advanced decoders used in WSJT-x, and so gets only about 50% of the decodes that WSJT-x gets.
### Here's my current understanding of the differences:

|Step|PyFT8|WSJT-X|
|-----|------|-------|
|Find candidate signals|Search the frequency spectrum for regions with the bandwidth of an FT8 signal that have the greatest power| TBD |
|Syncronise signals in time | Search each candidate in the time axis using the Costas synchronisation template, taking the maximum (or sum) over the three synch blocks | TBD|
|Use of FFTs for the above | A single time-frequency grid with 5 time samples per symbol and 3 frequency samples per tone| Several FFTs per operation, details TBC|
|Demodulation|Extract 1 sample per symbol, 1 sample per tone grid. Correlate each pair of symbols along with Gray code to create Log Likelyhood Ratios for each bit. | Noncoherent block detection over 3 symbols - creates LLRs by correlating the 512 possible tone sequences (3 symbols with 8 possible tones each) with the actual received symbols. This is done in the frequency domain by combining the whole-symbol correlations already calculated.  |
|Decoding the FEC code | Belief Propagation LDPC decoder | Belief Propagation LDPC decoder |
|Further decoding if LDPC fails| None | Ordered Statistics Decoding |
|Further signal extraction | None | Subtraction of the idealised power of the decoded signals, then rescanning the residual spectrum. Further synchronisation adjustments TBC|

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
