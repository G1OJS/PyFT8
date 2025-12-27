
from PyFT8.cycle_manager import Cycle_manager
from PyFT8.sigspecs import FT8
import argparse
import time
import signal

global concise
concise = False
def on_decode(c):
    decode_dict = {'cyclestart_str':c.cyclestart_str,
                   'call_a':c.call_a, 'call_b':c.call_b, 'grid_rpt':c.grid_rpt}
    if(not concise):
        decode_dict.update({'decoder':'PyFT8',
                   't_decode':f"{time.time() %15: 5.2f}", 'snr':f"{c.snr:5.0f}", 'freq':c.fHz,
                   'dt':f"{c.dt:5.1f}", 'sync_score':f"{c.pipeline.sync.result.score:5.1f}",
                   'ncheck_hist':c.pipeline.ldpc.metrics.ncheck_hist})

    print(decode_dict)

def cli():
    global concise
    parser = argparse.ArgumentParser(prog='PyFT8rx', description = 'Command Line FT8 decoder')
    parser.add_argument('inputcard_keywords', help = 'Comma-separated keywords to identify the input sound device') 
    parser.add_argument('-concise','-c', action='store_true', help = 'Concise output') 
    parser.add_argument( '-o','--outputcard_keywords', help = 'Comma-separated keywords to identify the output sound device') 
    parser.add_argument( '-v','--verbose',  action='store_true',  help = 'Verbose: include debugging output') 

    args = parser.parse_args()
    concise = args.concise
    verbose = args.verbose
    input_device_keywords = args.inputcard_keywords.replace(' ','').split(',')
    output_device_keywords = args.outputcard_keywords.replace(' ','').split(',') if args.outputcard_keywords is not None else None

    cycle_manager = Cycle_manager(FT8, on_decode, onOccupancy = None, input_device_keywords = input_device_keywords,
                                  output_device_keywords = output_device_keywords, verbose = verbose) 

    print("PyFT8 Rx running — Ctrl-C to stop")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping PyFT8 Rx")
