# Command Line Interface

Use the following to run PyFT8 from the command line:

```
PyFT8_cli "Keyword1, Keyword2" [-c][-v]
```

where Keywords specify the input sound device (e.g. "Mic, CODEC") and -c means 'concise' output, -v means 'verbose'. Output will appear
in the command window when audio is received via the specified sound device.

You can also transmit FT8 using PyFT8 as follows. When launching the program, use

```
PyFT8_cli "Keyword1, Keyword2" [-c][-v] -o "Keyword3, Keyword4"
```

where "Keyword3, Keyword4" specify the *output* sound device. Then, when you want to transmit a message, dump a file called
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
