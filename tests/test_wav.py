import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")

import numpy as np
from PyFT8.rx.waterfall import Waterfall
import PyFT8.timers as timers
import PyFT8.audio as audio
from PyFT8.comms_hub import config

decoded_candidates = []
cands_to_decode = []
audio_loaded_at = None

#============================================
# reference non-threaded load and decode
#============================================

def onCandidate_found(c):
    c.created_at = timers.tnow()
    c.frozen_at_hop = c.spectrum.nHops_loaded
    cands_to_decode.append(c)
    
def onResult(c):
    #metrics = f"{c.id} {c.decoded:>7} {c.score:7.2f} {c.llr_sd:7.2f} {c.snr:7.1f} {c.n_its:7.1f} {c.time_in_decode:7.3f}"
    #timers.timedLog(metrics, logfile='success_fail_metrics.log', silent = True)
    if(c.decoded):
        decoded_candidates.append(c)
        dd = c.decode_dict
        t_after_load = timers.tnow()-audio_loaded_at
        print(f"{t_after_load:7.2f} {dd['call_a']:>8} {dd['call_b']:>8} {dd['grid_rpt']:>8} {c.frozen_at_hop} {c.score:8.3f} {c.llr_sd:8.3f} {c.synced_pwr/1e9:8.3f} {c.snr:8.0f} "
          +f"{c.origin[0]:>8} {c.origin[1]:>8} {c.n_its:>8} {c.llr_hash}")

def non_threaded_decode(audio_in):
    from PyFT8.rx.cycle_manager import FT8Demodulator, Spectrum
    global audio_loaded_at
    demod = FT8Demodulator(max_iters=30, max_stall=8, max_ncheck=30, min_sd=0.5, sync_score_thresh = 1.5 )
    demod.spectrum = Spectrum(demod)
    FFT_start_sample_idx = 0
    time_window = np.kaiser(demod.spectrum.FFT_len, 20)
    while (FFT_start_sample_idx < len(audio_in) - demod.spectrum.FFT_len):
        aud = audio_in[FFT_start_sample_idx: FFT_start_sample_idx + demod.spectrum.FFT_len] * time_window
        demod.spectrum.fine_grid_complex[demod.spectrum.nHops_loaded,:] = np.fft.rfft(aud)[:demod.spectrum.nFreqs]
        FFT_start_sample_idx += demod.samples_perhop
        demod.spectrum.nHops_loaded +=1

    audio_loaded_at = timers.tnow()
    timers.timedLog(f"[bulk_load_audio] Loaded {demod.spectrum.nHops_loaded} hops ({demod.spectrum.nHops_loaded/(demod.sigspec.symbols_persec * demod.hops_persymb):.2f}s)", logfile = 'decodes.log', )
    demod.find_candidates(demod.spectrum, onCandidate_found)
    for c in cands_to_decode:
        demod.demodulate_candidate(c, onResult)

#============================================
# threaded decode
#============================================


def threaded_decode():
    from PyFT8.rx.cycle_manager import Cycle_manager
    global audio_loaded_at
    cycle_manager = Cycle_manager(onDecode, onOccupancy = None, verbose = True, audio_in = audio_in, 
                              sync_score_thresh = 1.5, min_sd = .5,
                              max_iters = 30, max_stall = 8, max_ncheck = 30,
                              max_parallel_decodes = 10, max_candidate_lifetime = 1000)
    pending = 0
    while pending == 0:
        with cycle_manager.cand_lock:
            pending = len(cycle_manager.cands_to_decode)
        timers.sleep(0.1)
    audio_loaded_at = cycle_manager.audio_loaded_at
    while True:
        with cycle_manager.cand_lock:
            pending = len(cycle_manager.cands_to_decode)
            running = cycle_manager.decode_load
        queued = cycle_manager.decode_queue.qsize()
    #    print(pending,running,queued)
        if pending == 0 and running == 0 and queued == 0:
            break
        timers.sleep(0.1)
    cycle_manager.running = False

def onDecode(c):
    decoded_candidates.append(c)
    dd = c.decode_dict
    t_after_load = timers.tnow()-audio_loaded_at
    print(f"{t_after_load:7.2f} {dd['call_a']:>8} {dd['call_b']:>8} {dd['grid_rpt']:>8} {c.frozen_at_hop} {c.score:8.3f} {c.llr_sd:8.3f} {c.synced_pwr/1e9:8.3f} {c.snr:8.0f} "
      +f"{c.origin[0]:>8} {c.origin[1]:>8} {c.n_its:>8} {c.llr_hash}")

wav_file = "210703_133430.wav"
#wav_file = "251115_135700.wav"

timers.timedLog(f"Loading audio from {wav_file}")
audio_in = audio.read_wav_file(wav_file)
heads = ['Tload+', 'Rx call', 'Tx call', 'GrRp', 'Frozen at hop', 'SyncScr', 'LLR_sd', 'snr', 't0', 'f0', 'iters', 'llr_hash']
print(''.join([f"{t:>8} " for t in heads]))

#non_threaded_decode(audio_in)

threaded_decode()

print(f"DONE. Unique decodes = {len(decoded_candidates)}")

#wf = Waterfall(cycle_manager.spectrum)
#wf.update_main(candidates=decoded_candidates)
#wf.show_zoom(candidates=decoded_candidates)



