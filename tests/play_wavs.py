import threading, pyaudio
from PyFT8.time_utils import time_utils
SAMP_RATE =12000

class SoundcardOut:
    def __init__(self, outputcard_keywords, wav_files):
        self.output_device_index = None
        self.pya = pyaudio.PyAudio()
        threading.Thread(target = self.play_wavs, args = (wav_files,), daemon = True).start()
        
        if outputcard_keywords:
            for dev_idx in range(self.pya.get_device_count()):
                name = self.pya.get_device_info_by_index(dev_idx)['name']
                match = True
                for pattern in outputcard_keywords.replace(' ','').split(','):
                    if (not pattern in name): match = False
                if(match):
                    self.output_device_index = dev_idx
                    break
            if not self.output_device_index:
                time_utils.tlog(f"[Audio Out] No output audio device found matching {outputcard_keywords}", verbose = True)
                sys.exit(1)

    def play_wavs(self, wav_files, sr=12000):
        import wave
        t = 15.05-time_utils.cycle_time()
        print(t)
        time_utils.sleep(t)
        dt = 0.6/4
        for i, w in enumerate(wav_files):
            print(f"File {i}")
            wv = wave.open(w, 'rb')
            audio_bytes = wv.readframes(sr*16)
            audio_bytes = audio_bytes[-int(sr*(15-dt))*2:]

            stream = self.pya.open(format=pyaudio.paInt16, channels=1, rate = sr, output=True,
                              output_device_index = self.output_device_index)
            stream.write(audio_bytes)
            stream.stop_stream()
            stream.close()

def play_wavs(i0, i1):
    wav_files = []
    for idx in range(i0, i1):
        wav_files.append(f"{wav_folder}/test_{idx:02d}.wav")
    soundout = SoundcardOut("CABLE, Input", wav_files)
 
wav_folder = "C:/Users/drala/Documents/Projects/GitHub/ft8_lib/test/wav/20m_busy"
play_wavs(1,30)





