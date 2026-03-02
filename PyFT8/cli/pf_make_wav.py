import argparse
from PyFT8.transmitter import AudioOut

def cli():
    parser = argparse.ArgumentParser(prog='PyFT8', description = '')
    parser.add_argument('-m','--transmit_message', nargs='?', help = 'Transmit a message')
    parser.add_argument('-w','--wave_output_file', nargs='?', help = 'Wave output file', default = 'PyFT8_tx_wav.wav')
    args = parser.parse_args()
    transmit_message = args.transmit_message
    wave_output_file = args.wave_output_file
    audio_out = AudioOut()
    symbols = audio_out.create_ft8_symbols(transmit_message)
    audio_data = audio_out.create_ft8_wave(symbols)
    audio_out.write_to_wave_file(audio_data, wave_output_file)
    print(f"Created wave file '{wave_output_file}' with message '{transmit_message}'")

#================== TEST CODE ============================================================

if __name__ == "__main__":
    import mock
    with mock.patch('sys.argv', ['PyFT8_cli', '-w PyFT8.wav', '-m CQ G1OJS IO90']):
        cli()

