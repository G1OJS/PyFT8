
from PyFT8.cycle_manager import Cycle_manager
from PyFT8.sigspecs import FT8
import argparse
import time
import signal

def on_decode(decode_dict):
    print(decode_dict)

def cli():
    parser = argparse.ArgumentParser(prog='PyFT8rx', description = 'Command Line FT8 decoder')
    parser.add_argument('inputcard_keywords', help = 'Comma-separated keywords to identify the input sound device') 
    parser.add_argument('-concise','-c', action='store_true', help = 'Concise output') 
    parser.add_argument( '-o','--outputcard_keywords', help = 'Comma-separated keywords to identify the output sound device') 

    args = parser.parse_args()
    input_device_keywords = args.inputcard_keywords.replace(' ','').split(',')
    output_device_keywords = args.outputcard_keywords.replace(' ','').split(',') if args.outputcard_keywords is not None else None

    cycle_manager = Cycle_manager(FT8, on_decode, onOccupancy = None, input_device_keywords = input_device_keywords,
                                  output_device_keywords = output_device_keywords,
                                  sync_score_thresh = 4, max_ncheck = 38, max_iters = 25, concise = args.concise) 

    print("PyFT8 Rx running — Ctrl-C to stop")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping PyFT8 Rx")
