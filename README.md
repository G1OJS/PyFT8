# PyFT8 [![PyPI Downloads](https://static.pepy.tech/personalized-badge/pyft8?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/pyft8) [![PyPI Downloads](https://static.pepy.tech/personalized-badge/pyft8?period=weekly&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads/wk)](https://pepy.tech/projects/pyft8) [PyPI link](https://pypi.org/project/PyFT8/)
An FT8 Receiver, FT8 Transmitter, and Tkinter GUI, written in three single & short Python files plus a tiny udp_comms file. Version 4 is a rewrite introducing many simplifications, including a leaner receiver and Tkinter GUI replacing the Matplotlib-based GUI used previously. Also new in version 4, the Receiver and Transmitter can be run standalone and copied for use without the GUI if desired.
 
If you're looking for the Matplotlib-based GUI with decodes overlaid on the waterfall, that's available here: [PyFT8 v3.9.1](https://github.com/G1OJS/PyFT8/releases/tag/PyPi_v3.9.1).

<img width="925" height="659" alt="Capture" src="https://github.com/user-attachments/assets/db0b9ced-8270-4683-92c7-a9a26c37d991" />

## Features
As of version 4.0.0, the key features are:
 * Written entirely in Python
 * Most decodes require only the 91 message bits
 * LDPC and OSD decoding for the rest
 * Decodes typically > 90% of decodes caught by WSJT-x v3 in FAST mode
 * Tkinter GUI
 * Receiver and Transmitter can be used standalone
 * Internal connections are via UDP (so e.g. alternative Receivers / Transmitters could be easily swapped in)
 * Rx and Tx of standard messages with optional /P and /R
 * Tx uses GFSK waveform as defined in FT8 standard
 * RX of nonstandard calls plus hashed calls
 * Launches quickly (~2 seconds on my old Dell Optiplex 790)
 * Finds sound cards by keywords so follows them if e.g. Windows moves them ...
 * Logs QSOs to user-specified ADIF file
 * Uploads spots to pskreporter
 * Controls rigs via Hamlib's rigctl.exe, which doesn't hog the rig's COM port(*)
 * Click on the spectrum display to set Tx frequency

(*) Interactions with the rig are brief and infrequent (get/set frequency, set/unset PTT), and for my own purposes I prefer not having the Hamlib rigctld running, and having to check its run status and launch it if it's not running. In fact I'd prefer not to use Hamlib at all, and simply use a direct CAT command for the radio I'm using. I included Hamlib-style control so that people who don't have the same Icom rig as me can use this software.

## Design philosophy
This isn't meant to do anything 'better' than applications like WSJT-x and MSHV, but it illustrates what can be done in a very few lines of Python, and it is written to be free of bloat. Currently, the code comprises:
 - Receiver ~ 300 lines, including LDPC and OSD decoding
 - Transmitter ~ 300 lines
 - Tkinter GUI ~ 500 lines

That's an FT8 transmitter / receiver *application* in about 1100 lines of Python. The Receiver and Transmitter are implemented in single Python files (apart from common use of a small UDP class) and communicate with the GUI *only* via UDP. The point of doing this is to keep the interfaces here minimal, so that in theory it's easy to swap out either transmitter, receiver, or GUI and replace it with something written in any other language, subject to meeting / adapting the UDP commands reference below.

## Installation and use
To use it as a 'turnkey' transceiver, just install the project via pip:
```
pip install PyFT8
```
... and then run the tk_gui either in a Python environment or by using the command: 
```
pyft8gui
```
You might have to open a new command window after pip install so that the command 'pyft8gui' is recognised. I haven't written too much of a step by step quide here, as the project is really intended for people who want to poke around and maybe modify the code. But hopefully even if you're new to Python or coding, you can have a look and work out how it's done.

To control a rig's PTT and frequency, you'll need a copy of Hamlib's rigctl.exe.

## Hacking it
The transmitter and receiver may be run independently from the GUI, as they communicate only via UDP (see below). For example, to run the receiver from Python, 
```
from PyFT8 import Receiver
rx = Receiver(output_type = 'print', input_keywords = 'Mic, CODEC')
```
Or of course copy the receiver.py file, add this line at the bottom (minus the import), and hack away.

### UDP messages
The following shows the main points of the way that the UDP messages are constructed - please see the code for the absolute reference.
1. All UDP messages apart from those sent to pskreporter.info or the waterfall data sent from the receiver to the GUI, are Python dictionaries serialised with JSON and encoded to bytes.
2. All dictionaries start with a key called 'mtype' meaning 'messsage type'. The main ones are 'decode' (indicating that the dictionary contains various entries from a decoded message), 'shutdown', 'waterfall', 'rollover', 'test_info', 'set_tx_Hz', 'generate_tx_audio', 'send_tx_audio', 'stop_tx_audio'.

As the project grows, I might write a more formal spec for these messages.

## Acknowledgements
This project implements a decoder for the FT8 digital mode. FT8 was developed by Joe Taylor, K1JT, Steve Franke, K9AN, and others as part of the WSJT-X project.
Protocol details are based on information publicly described by the WSJT-X authors and in related open documentation.

Some constants and tables (e.g. Costas synchronization sequence, LDPC structure, message packing scheme) are derived from 
the publicly available WSJT-X source code and FT8 protocol descriptions. Original WSJT-X source is © the WSJT Development Group 
and distributed under the GNU General Public License v3 (GPL-3.0), hence the use of GPL-3.0 in this repository.


