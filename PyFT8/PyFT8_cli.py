
from PyFT8.cycle_manager import Cycle_manager
from PyFT8.sigspecs import FT8
import argparse
import time
import signal

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
    parser.add_argument('-tx','--transmit_message', nargs='?', help = 'Transmit a message')
    parser.add_argument('-wo','--wave_output_file', nargs='?', help = 'Wave output file', default = 'PyFT8_tx_wav.wav')
    
    
    args = parser.parse_args()
    concise = args.concise
    verbose = args.verbose
    input_device_keywords = args.inputcard_keywords.replace(' ','').split(',') if args.inputcard_keywords is not None else None
    output_device_keywords = args.outputcard_keywords.replace(' ','').split(',') if args.outputcard_keywords is not None else None
    transmit_message = args.transmit_message
    wave_output_file = args.wave_output_file

    if(transmit_message):
        if(output_device_keywords):
            print(f"Transmitting {transmit_message} on next cycle (in {15 - time.time() % 15 :3.1f}s)")
            tx_msg_file = 'PyFT8_tx_msg.txt'
            with open('PyFT8_tx_msg.txt','w') as f:
                f.write(transmit_message)
        else:
            from PyFT8.audio import AudioOut
            audio_out = AudioOut()
            symbols = audio_out.create_ft8_symbols(transmit_message)
            wf = audio_out.create_ft8_wave(symbols)
            audio_out.write_to_wave_file(wf, wave_output_file)
            print(f"Created wave file '{wave_output_file}' with message '{transmit_message}'")
    else:
        cycle_manager = Cycle_manager(FT8, on_decode = on_decode, input_device_keywords = input_device_keywords,
                                  output_device_keywords = output_device_keywords, verbose = verbose) 
        print("PyFT8 Rx running — Ctrl-C to stop")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping PyFT8 Rx")
