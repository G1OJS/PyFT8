import argparse
import time
import signal
import threading
import matplotlib.pyplot as plt
from PyFT8.receive import receiver, AudioIn, params
from PyFT8.waterfall import Waterfall
from PyFT8.transmit import AudioOut

global concise
concise = False
def on_decode(dd):
    if(concise):
        print(f"{dd['cs']} {dd['snr']} {dd['dt']} {dd['f']} ~ {dd['msg']}")
    else:
        print(dd)

def cli():
    global concise
    parser = argparse.ArgumentParser(prog='PyFT8rx', description = 'Command Line FT8 decoder')
    parser.add_argument('-i', '--inputcard_keywords', help = 'Comma-separated keywords to identify the input sound device') 
    parser.add_argument('-c','--concise', action='store_true', help = 'Concise output') 
    parser.add_argument('-o','--outputcard_keywords', help = 'Comma-separated keywords to identify the output sound device') 
    parser.add_argument('-v','--verbose',  action='store_true',  help = 'Verbose: include debugging output')
    parser.add_argument('-m','--transmit_message', nargs='?', help = 'Transmit a message')
    parser.add_argument('-w','--wave_output_file', nargs='?', help = 'Wave output file', default = 'PyFT8_tx_wav.wav')
    
    
    args = parser.parse_args()
    concise = args.concise
    verbose = args.verbose
    input_device_keywords = args.inputcard_keywords.replace(' ','').split(',') if args.inputcard_keywords is not None else None
    output_device_keywords = args.outputcard_keywords.replace(' ','').split(',') if args.outputcard_keywords is not None else None
    transmit_message = args.transmit_message
    wave_output_file = args.wave_output_file

    if(transmit_message):
            audio_out = AudioOut()
            symbols = audio_out.create_ft8_symbols(transmit_message)
            audio_data = audio_out.create_ft8_wave(symbols)
            if(output_device_keywords):
                output_device_idx = audio_out.find_device(output_device_keywords)
                delay = 15 - time.time() % 15
                print(f"Transmitting {transmit_message} on next cycle (in {delay :3.1f}s)")
                time.sleep(delay)
                print(f"Transmitting {transmit_message}")
                audio_out.play_data_to_soundcard(audio_data, output_device_idx)
            else:
                audio_out.write_to_wave_file(audio_data, wave_output_file)
                print(f"Created wave file '{wave_output_file}' with message '{transmit_message}'")
    else:
        def start_receiver(waterfall):
            threading.Thread(target = receiver, args =(audio_in, [200, 3100], None, False, waterfall), daemon=True ).start()
        audio_in = AudioIn(input_device_keywords, 3100)
        waterfall = Waterfall(audio_in.dBgrid_main, params['HPS'], params['BPT'], start_receiver, lambda msg: print(msg))
        plt.show()

#================== TEST CODE ============================================================

if __name__ == "__main__":
    import mock
    with mock.patch('sys.argv', ['PyFT8_cli', '-i Mic, CODEC']):
#    with mock.patch('sys.argv', ['PyFT8_cli', '-o "Speak, CODEC"', '-m CQ G1OJS IO90']):
#    with mock.patch('sys.argv', ['PyFT8_cli', '-w PyFT8.wav', '-m CQ G1OJS IO90']):
        cli()

