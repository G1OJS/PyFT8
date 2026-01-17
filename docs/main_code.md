## Overview of main code
[being written]

#### Audio In
1. Connect to an audio stream, either sound card or wav file
2. Use rfft to create a frequency spectrum once every 53.33ms (1/3 of a symbol duration)
3. Assemble successive FFTs into a time/frequency grid

#### Spectrum
1. Specify the time/frequency grid for FT8
2. Construct an array from the Costas sequence for candidate searching
3. Identify the 'hop' number after which searching can commence
4. Search for candidates

#### Candidate
1. Hold the candidate's lifetime state (sync info, Log Likelyhood Ratio (LLR), synced power grid, decoding flags, output message)
2. Demap from the main time/frequency grid to LLR
3. Functions for decoding:
  - Calculate 'ncheck'
  - Do single LDPC iterations (calls 'pass_messages' and 'calc ncheck')
  - Flip several bits & keep if ncheck improved
  - Manage the decoding progression (Flip bits, do LDPC, call OSD if failed)
  - Process decoded codewords - final CRC and pass messages to specified callback

#### Cycle Manager
1. Hold key parameters and setup for run using classes above
2. Manage the 15 second cycle using a continuous loop with a 1ms sleep:
   * Rollover - re-initialise variables, check for any Tx messages & send
   * Search - initiate candidate search, clear existing candidates, save new ones
   * Send candidates for demap once spectrum fills past candidate's last payload symbol
   * Send candidates for decode once LLR is available from demap

The code itself is light on explanation, but I've avoided anonymous variable names like 'n5_b' as much as possible in favour of varable names that tell the story. Also, whilst I've used AI to introduce me to coding best practice and DSP techniques, I don't let their bloat survive the cut. This has
been productive - constantly badgering AI has resulted in a very compact and very fast LDPC decoder which has increased in speed
by about 2 orders of magnitude since I first hand-translated some FORTRAN into Python.
