# PyFT8 [![PyPI Downloads](https://static.pepy.tech/personalized-badge/pyft8?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/pyft8)
# FT8 Decoding and Encoding in Python with CLI and test/loopback code
This repository contains Python code to decode and encode FT8, plus a minimal Command Line Interface for reception.

This started out as me thinking "How hard can it be, really?" and has become a bit of a mission to provide the most direct,
compact, and fast FT8 decoder that I can without copying code (apart from constants of course). It's light on explanation, 
but I've avoided anonymous variable names like 'n5_b' as much as possible in favour of varable names that tell the story. Also, 
whilst I've used AI to introduce me to coding best practice and DSP techniques, I don't let their bloat survive the cut. This has
been productive - constantly badgering AI has resulted in a very compact and very fast LDPC decoder which has increased in speed
by about 2 orders of magnitude since I first hand-translated some FORTRAN into Python.

### CLI
PyFT8 can be installed using 

```
pip install PyFT8
```

and you can use 

```
PyFT8_cli "Keyword1, Keyword2" [-c]
```

to run the CLI where Keywords specify the input sound device (e.g. "Mic, CODEC") and -c means 'concise' output. Output will appear
in the command window when audio is received via the specified sound device.

You can also transmit FT8 using PyFT8 as follows. When launching the program, use

```
PyFT8_cli "Keyword1, Keyword2" [-c] -o "Keyword3, Keyword4"
```

where "Keyword3, Keyword4" specify the output sound device. Then, when you want to transmit a message, dump a file called
'PyFT8_tx_msg.txt' in the directory you launched from. The contents of this file should be for example:

```
CQ G1OJS IO90
```

with, optionally, a second line to specify the Tx audio frequency:

```
CQ G1OJS IO90
888
```

PyFT8 will wait for the *next* cycle boundary, and the file will be deleted during the transmit cycle. If you want to transmit via a transceiver,
you will have to organise your own method of controlling the PTT (e.g. [DATA]VOX, or sending your own CAT commands).

### Test scripts
Below are some screenshots from test programs that can be used to look at how the protocols actually work, illustrated with a fairly
ordinary waterfall and some zoomed-in depictions of captured signals with an overlay of the syncrhonisation tones that are used
to search for the signals (Costas patterns). To try these scripts, download the Python from this repository (clone, download raw etc)
and run in your chosen environment. These images probably need updating so don't expect exact copies, but they give the idea.

<img width="987" height="262" alt="waterfall" src="https://github.com/user-attachments/assets/bb97c336-3150-466d-b102-1885fff971b4" />

<img width="1039" height="986" alt="candidate detail" src="https://github.com/user-attachments/assets/cc9ad981-77b1-4997-a1c5-688589342ae9" />

## Approach
You won't find many comments in the code; I try to make things as obvious as possible via variable names and logical structure, to 
minimise the *need for* comments. Also - this is mainly my plaything, and I find bloated, sprawling code incredibly difficult to 
read, so I like to keep things very compact so that I can see the bigger picture. If you find an if-then-else spanning several
paragraphs, it's probably a mistake.

Do feel free to get in touch and ask how anything works. I might add some diagrams etc at some point too - especially
if I find an approach that seems to offer something improved and/or very compact (I'm very pleased for e.g. that the entire candidate
search, synch, and demodulate process all works by refering to a single time-frequency grid; read the audio, FFT 5 times for each 
symbol duration, store it, and that's used for everything that follows.)

## Limitations
In pursuit of tight code, I've concentrated on core standard messages, leaving out some of the less-used features. The receive part of the
code doesn't (yet) have the full capability of the advanced decoders used in WSJT-x, and so gets only about 50% of the decodes that WSJT-x gets.
### Here's my current understanding of the differences:

|Step|PyFT8|WSJT-X|
|-----|------|-------|
|Find candidate signals|Search every possible time/frequency offset for match with the Costas pattern, excluding times where candidates would not complete before the next cycle (i.e. first few seconds of the grid)| TBD |
|Syncronise signals in time | See above | TBD|
|Use of FFTs for the above | A single time-frequency grid with 5 time samples per symbol and 3 frequency samples per tone| Several FFTs per operation, details in VK3JPK's great write-up [here](https://nbviewer.org/github/vk3jpk/ft8-notes/blob/master/Receive.ipynb)|
|Demodulation|Extract 1 sample per symbol, 1 sample per tone grid. Correlate each symbol with Gray code to create Log Likelyhood Ratios for each bit. | Noncoherent block detection over 3 symbols - creates LLRs by correlating the 512 possible tone sequences (3 symbols with 8 possible tones each) with the actual received symbols. This is done in the frequency domain by combining the whole-symbol correlations already calculated.  |
|Decoding the FEC code | Limited bit-flipping of lowest confidence bits if the syndrome check is high, then Belief Propagation LDPC decoder | Belief Propagation LDPC decoder |
|Further decoding if LDPC fails| None | Ordered Statistics Decoding |
|Further signal extraction | None | Subtraction of the idealised power of the decoded signals, then rescanning the residual spectrum. Further synchronisation adjustments TBC|

## Performance
As of 14th Jan 2026, PyFT8 decodes around 60% to 90% of WSJTx decodes when the latter is set to "NORM" decoding. Most recently I've found that plotting decode success against
WSJT-x as a benchmark, with a measure of LLR quality as the X-axis, has enabled me to focus on which kinds of signal are and are not being decoded reliably. The decoder now has
about four ways that signals can emerge:
 - Immediately from the demapper (channel tones to bits) as a correct decode
 - Decoded via LDPC
 - Kicked along a little by random but informed bit flipping
 - Ordered Statistics Decoding

The graph below shows a typical result. This is also useful in that it proves that sorting candidates into LLR-quality order before decoding does indeed push any 
timeouts (where the processes simply run out of time before the next cycle) into places where they probably wouldn't have been decoded anyway.

<img width="1000" height="600" alt="snapshot as commit" src="https://github.com/user-attachments/assets/960b5605-26bf-4d73-9648-0beb9a55f1d0" />

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
