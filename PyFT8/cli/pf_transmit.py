import argparse
import time
from PyFT8.transmitter import AudioOut

def cli():
    global concise
    parser = argparse.ArgumentParser(prog='PyFT8', description = '')
    parser.add_argument('-o','--outputcard_keywords', help = 'Comma-separated keywords to identify the output sound device') 
    parser.add_argument('-m','--transmit_message', nargs='?', help = 'Transmit a message')
    parser.add_argument('-w','--wave_output_file', nargs='?', help = 'Wave output file', default = 'PyFT8_tx_wav.wav')
    
    args = parser.parse_args()
    transmit_message = args.transmit_message
    wave_output_file = args.wave_output_file

    audio_out = AudioOut()
    symbols = audio_out.create_ft8_symbols(transmit_message)
    audio_data = audio_out.create_ft8_wave(symbols)
    output_device_keywords = args.outputcard_keywords.replace(' ','').split(',') if args.outputcard_keywords is not None else None
    output_device_idx = audio_out.find_device(output_device_keywords)
    delay = 15 - time.time() % 15
    print(f"Transmitting {transmit_message} on next cycle (in {delay :3.1f}s)")
    time.sleep(delay)
    print(f"Transmitting {transmit_message}")
    audio_out.play_data_to_soundcard(audio_data, output_device_idx)
   
#================== TEST CODE ============================================================

if __name__ == "__main__":
    import mock
    with mock.patch('sys.argv', ['PyFT8_cli', '-o "Speak, CODEC"', '-m CQ G1OJS IO90']):
        cli()

