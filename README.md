# Python FT8 decoder 
## Purpose
This is code that I'm playing with mainly for my own understanding, but I really hope it's helpful to anyone who wants to 
understand how FT8 works. I'm keen to avoid simply copying code from other people (or AI!), and generate my own Pythonic
solutions keeping code as tight and minimal as possible, whilst experimenting with different candidate selection algorithms
and decoding approaches.

## Acknowledgements
This project implements a decoder for the FT8 digital mode.
FT8 was developed by Joe Taylor, K1JT, Steve Franke, K9AN, and others as part of the WSJT-X project.
Protocol details are based on information publicly described by the WSJT-X authors and in related open documentation.

Some constants and tables (e.g. Costas synchronization sequence, LDPC structure, message packing scheme) are derived from 
the publicly available WSJT-X source code and FT8 protocol descriptions. Original WSJT-X source is © the WSJT Development Group 
and distributed under the GNU General Public License v3 (GPL-3.0), hence the use of GPL-3.0 in this repository.
