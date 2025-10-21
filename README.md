# Python FT8 demodulator and decoder 

<img width="981" height="382" alt="Capture" src="https://github.com/user-attachments/assets/8eb7c645-ab75-4e4f-8ce9-1dae6045e6ba" />

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
