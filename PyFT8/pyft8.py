import argparse
import time
from PyFT8.receiver import Receiver, AudioIn
from PyFT8.gui import Gui
from PyFT8.transmitter import AudioOut

def wait_for_keyboard():
    import time
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

def on_decode(c):
    print(f"{c.cyclestart_str} {c.snr} {c.dt:4.1f} {c.fHz} ~ {c.msg}")

def on_click_message(msg):
    print(msg)

def cli():
    global concise
    import time
    parser = argparse.ArgumentParser(prog='PyFT8rx', description = 'Command Line FT8 decoder')
    parser.add_argument('-i', '--inputcard_keywords', help = 'Comma-separated keywords to identify the input sound device') 
    parser.add_argument('-v','--verbose',  action='store_true',  help = 'Verbose: include debugging output')    
    parser.add_argument('-o','--outputcard_keywords', help = 'Comma-separated keywords to identify the output sound device')
    parser.add_argument('-n','--no_gui',  action='store_true',  help = 'Dont create a gui')
    parser.add_argument('-m','--transmit_message', nargs='?', help = 'Transmit a message')
    parser.add_argument('-w','--wave_output_file', nargs='?', help = 'Wave output file', default = 'PyFT8.wav')
    args = parser.parse_args()

    run = True

    output_device_idx = None
    gui = None

    if args.transmit_message:
        run = False
        audio_out = AudioOut()
        symbols = audio_out.create_ft8_symbols(args.transmit_message)
        audio_data = audio_out.create_ft8_wave(symbols)
        if args.outputcard_keywords:
            outputcard_keywords = args.outputcard_keywords.replace(' ','').split(',')
            output_device_idx = audio_out.find_device(outputcard_keywords)
            if output_device_idx is not None:
                delay = 15 - time.time() % 15
                print(f"Transmitting {args.transmit_message} on next cycle (in {delay :3.1f}s)")
                time.sleep(delay)
                print(f"Transmitting {args.transmit_message} on device index {output_device_idx}")
                audio_out.play_data_to_soundcard(audio_data, output_device_idx)
            else:
                print("No output device")
        else:
            audio_out.write_to_wave_file(audio_data, args.wave_output_file)
            print(f"Created wave file {args.wave_output_file}")          
    else:
        if args.inputcard_keywords:
            audio_in = AudioIn(3100)
            input_device_idx = audio_in.find_device(args.inputcard_keywords.replace(' ','').split(','))
            if input_device_idx:
                gui = None if args.no_gui else Gui(audio_in.dBgrid_main, 4, 2, lambda msg: print(msg))
                rx = Receiver(audio_in, [200, 3100], on_decode, gui)
                audio_in.start_streamed_audio(input_device_idx)
                if gui is not None:
                    gui.plt.show()
                else:
                    wait_for_keyboard()
        else:
            print("No input device specified")

    
#================== TEST CODE ============================================================
print(__name__)
if __name__ == "__main__":
    import mock
    #with mock.patch('sys.argv', ['pyft8', '-i Mic, CODEC', '-o Speak, CODEC']):
    with mock.patch('sys.argv', ['pyft8', '-i Mic, CODEC']):
        cli()
