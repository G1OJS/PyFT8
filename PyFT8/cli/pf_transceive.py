import argparse
from PyFT8.receiver import receiver, AudioIn, params
from PyFT8.waterfall import Waterfall
from PyFT8.transmitter import AudioOut

def on_decode(dd):
        print(f"{dd['cs']} {dd['snr']} {dd['dt']} {dd['f']} ~ {dd['msg']}")

def on_click_message(msg):
    print(msg)

def cli():
    global concise
    parser = argparse.ArgumentParser(prog='PyFT8rx', description = 'Command Line FT8 decoder')
    parser.add_argument('-i', '--inputcard_keywords', help = 'Comma-separated keywords to identify the input sound device') 
    parser.add_argument('-o','--outputcard_keywords', help = 'Comma-separated keywords to identify the output sound device') 
    parser.add_argument('-v','--verbose',  action='store_true',  help = 'Verbose: include debugging output')
    args = parser.parse_args()
    verbose = args.verbose
    input_device_keywords = args.inputcard_keywords.replace(' ','').split(',') if args.inputcard_keywords is not None else None
    output_device_keywords = args.outputcard_keywords.replace(' ','').split(',') if args.outputcard_keywords is not None else None

    audio_in = AudioIn(input_device_keywords, 3100)
    waterfall = Waterfall(audio_in.dBgrid_main, 4, 2, on_click_message)
    rx = Receiver(audio_in, [200, 3100], on_decode, waterfall)
    waterfall.plt.show()

#================== TEST CODE ============================================================

if __name__ == "__main__":
    import mock
    with mock.patch('sys.argv', ['pf_transceive', '-i Mic, CODEC', '-o Speak, CODEC']):
        cli()

