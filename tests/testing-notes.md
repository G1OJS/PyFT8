
## Recording a suitable WAV file
```
./ffmpeg -f dshow -i audio="Microphone (7- USB Audio CODEC )" -ar 12000 -ac 1 output.wav
```

## Compiling ft8_lib
```
 gcc demo/decode_ft8.c ft8/*.c common/*.c fft/*.c     -I. -DUSE_PORTAUDIO -lportaudio -O3 -lm -o ft8_cli.exe
```
