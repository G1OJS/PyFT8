

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


### Here's my current understanding of the differences:

|Step|PyFT8|WSJT-X|
|-----|------|-------|
|Find candidate signals|Search every possible time/frequency offset for match with the Costas pattern, excluding times where candidates would not complete before the next cycle (i.e. first few seconds of the grid)| TBD |
|Syncronise signals in time | See above | TBD|
|Use of FFTs for the above | A single time-frequency grid with 3 time samples per symbol and 3 frequency samples per tone| Several FFTs per operation, details in VK3JPK's great write-up [here](https://nbviewer.org/github/vk3jpk/ft8-notes/blob/master/Receive.ipynb)|
|Demodulation|Extract 1 sample per symbol, 1 sample per tone grid. Correlate each symbol with Gray code to create Log Likelyhood Ratios for each bit. This is now done twice, using the time sync from the first and middle Costas block, and the best resulting LLR is chosen. | Noncoherent block detection over 3 symbols - creates LLRs by correlating the 512 possible tone sequences (3 symbols with 8 possible tones each) with the actual received symbols. This is done in the frequency domain by combining the whole-symbol correlations already calculated.  |
|Decoding the FEC code | Limited bit-flipping of bits associated with failing parity checks, then Belief Propagation LDPC decoder | Belief Propagation LDPC decoder |
|Further decoding if LDPC fails| Ordered Statistics Decoding | Ordered Statistics Decoding |
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
