import numpy as np
from PyFT8.ldpc import LdpcDecoder
import time

gray_seq = [0,1,3,2,5,6,4,7]
num_symbols = 79
tones_persymb = 8
payload_symb_idxs = list(range(7, 36)) + list(range(43, 72))
costas=[3,1,4,0,6,5,2]
    
class Candidate:
    def __init__(self, t0_idx, dt, f0_idx, df):
        self.t0_idx = t0_idx
        self.f0_idx = f0_idx
        self.origin = (t0_idx, f0_idx, dt*t0_idx, df * (f0_idx + 1))
        self.size = (79*3, 8*3)
        self.n_its = 0
        self.ldpc = LdpcDecoder()

def create_ft8_wave(symbols, fs=12000, f_base=873.0, f_step=6.25, amplitude = 0.5, added_noise = -50):
    symbol_len = int(fs * 0.160)
    t = np.arange(symbol_len) / fs
    phase = 0
    waveform = []
    for s in symbols:
        f = f_base + s * f_step
        phase_inc = 2 * np.pi * f / fs
        w = np.sin(phase + phase_inc * np.arange(symbol_len))
        waveform.append(w)
        phase = (phase + phase_inc * symbol_len) % (2 * np.pi)
    waveform = np.concatenate(waveform).astype(np.float32)
    waveform = waveform.astype(np.float32)
    waveform = amplitude * waveform / np.max(np.abs(waveform))
    if(added_noise > -50):
        noise = np.random.randn(len(waveform))
        signal_rms = np.sqrt(np.mean(waveform**2))
        noise_rms = signal_rms * 10**(added_noise / 20)
        noise *= noise_rms / np.sqrt(np.mean(noise**2))
        waveform_noisy = waveform + noise
    return waveform_noisy

def add_costas(syms: list[int]) -> list[int]:
    return costas + syms[:29] + costas + syms[29:] + costas

def crc14(bits77_int: int) -> int:
    # Generator polynomial (0x2757), width 14, init=0, refin=false, refout=false
    poly = 0x2757
    width = 14
    mask = (1 << width) - 1
    # Pad to 96 bits (77 + 14 + 5)
    nbits = 96
    reg_int = 0
    for i in range(nbits):
        # bits77 is expected MSB-first (bit 76 first)
        inbit = ((bits77_int >> (76 - i)) & 1) if i < 77 else 0
        bit14 = (reg_int >> (width - 1)) & 1
        reg_int = ((reg_int << 1) & mask) | inbit
        if bit14:
            reg_int ^= poly
    return reg_int

def append_crc(bits77_int):
    """Append 14-bit WSJT-X CRC to a 77-bit message, returning a 91-bit list."""
    bits14_int = crc14(bits77_int)
    bits91_int = (bits77_int << 14) | bits14_int
    return bits91_int, bits14_int

def check_crc(bits91_int):
    """Return True if the 91-bit message (77 data + 14 CRC) passes WSJT-X CRC-14."""
    bits14_int = bits91_int & 0b11111111111111
    bits77_int = bits91_int >> 14
    return bits14_int == crc14(bits77_int)

def bitsLE_to_int(bits):
    """bits is MSB-first."""
    n = 0
    for b in bits:
        n = (n << 1) | (b & 1)
    return n

def int_to_bitsLE(n, width):
    """Return [b(width-1), ..., b0], MSB-first."""
    return [ (n >> (width - 1 - i)) & 1 for i in range(width) ]

def ldpc_encode(msg_crc: int) -> int:
    generator_matrix_rows = ["8329ce11bf31eaf509f27fc",  "761c264e25c259335493132",  "dc265902fb277c6410a1bdc",  "1b3f417858cd2dd33ec7f62",  "09fda4fee04195fd034783a",  "077cccc11b8873ed5c3d48a",  "29b62afe3ca036f4fe1a9da",  "6054faf5f35d96d3b0c8c3e",  "e20798e4310eed27884ae90",  "775c9c08e80e26ddae56318",  "b0b811028c2bf997213487c",  "18a0c9231fc60adf5c5ea32",  "76471e8302a0721e01b12b8",  "ffbccb80ca8341fafb47b2e",  "66a72a158f9325a2bf67170",  "c4243689fe85b1c51363a18",  "0dff739414d1a1b34b1c270",  "15b48830636c8b99894972e",  "29a89c0d3de81d665489b0e",  "4f126f37fa51cbe61bd6b94",  "99c47239d0d97d3c84e0940",  "1919b75119765621bb4f1e8",  "09db12d731faee0b86df6b8",  "488fc33df43fbdeea4eafb4",  "827423ee40b675f756eb5fe",  "abe197c484cb74757144a9a",  "2b500e4bc0ec5a6d2bdbdd0",  "c474aa53d70218761669360",  "8eba1a13db3390bd6718cec",  "753844673a27782cc42012e",  "06ff83a145c37035a5c1268",  "3b37417858cc2dd33ec3f62",  "9a4a5a28ee17ca9c324842c",  "bc29f465309c977e89610a4",  "2663ae6ddf8b5ce2bb29488",  "46f231efe457034c1814418",  "3fb2ce85abe9b0c72e06fbe",  "de87481f282c153971a0a2e",  "fcd7ccf23c69fa99bba1412",  "f0261447e9490ca8e474cec",  "4410115818196f95cdd7012",  "088fc31df4bfbde2a4eafb4",  "b8fef1b6307729fb0a078c0",  "5afea7acccb77bbc9d99a90",  "49a7016ac653f65ecdc9076",  "1944d085be4e7da8d6cc7d0",  "251f62adc4032f0ee714002",  "56471f8702a0721e00b12b8",  "2b8e4923f2dd51e2d537fa0",  "6b550a40a66f4755de95c26",  "a18ad28d4e27fe92a4f6c84",  "10c2e586388cb82a3d80758",  "ef34a41817ee02133db2eb0",  "7e9c0c54325a9c15836e000",  "3693e572d1fde4cdf079e86",  "bfb2cec5abe1b0c72e07fbe",  "7ee18230c583cccc57d4b08",  "a066cb2fedafc9f52664126",  "bb23725abc47cc5f4cc4cd2",  "ded9dba3bee40c59b5609b4",  "d9a7016ac653e6decdc9036",  "9ad46aed5f707f280ab5fc4",  "e5921c77822587316d7d3c2",  "4f14da8242a8b86dca73352",  "8b8b507ad467d4441df770e",  "22831c9cf1169467ad04b68",  "213b838fe2ae54c38ee7180",  "5d926b6dd71f085181a4e12",  "66ab79d4b29ee6e69509e56",  "958148682d748a38dd68baa",  "b8ce020cf069c32a723ab14",  "f4331d6d461607e95752746",  "6da23ba424b9596133cf9c8",  "a636bcbc7b30c5fbeae67fe",  "5cb0d86a07df654a9089a20",  "f11f106848780fc9ecdd80a",  "1fbb5364fb8d2c9d730d5ba",  "fcb86bc70a50c9d02a5d034",  "a534433029eac15f322e34c",  "c989d9c7c3d3b8c55d75130",  "7bb38b2f0186d46643ae962",  "2644ebadeb44b9467d1f42c",  "608cc857594bfbb55d69600"]
    kGEN = np.array([int(row,16)>>1 for row in generator_matrix_rows])
    msg_crc = int(msg_crc)
    parity_bits = 0
    for row in map(int, kGEN):
        bit = bin(msg_crc & row).count("1") & 1
        parity_bits = (parity_bits << 1) | bit
    return (msg_crc << 83) | parity_bits

def gray_encode(bits: int) -> list[int]:
    syms = []
    for _ in range(174 // 3):
        chunk = bits & 0x7
        syms.insert(0, gray_seq[chunk])
        bits >>= 3
    return syms

def encode_bits77(bits77_int):
    bits91_int, bits14_int = append_crc(bits77_int)
    bits174_int = ldpc_encode(bits91_int)
    syms = gray_encode(bits174_int)
    symbols = add_costas(syms)
    return symbols

def single_loopback(snr=20, max_its = 10):
    f_base = 1000
    
   # bits77_int = int(2**77 * np.random.rand())
    bits77_int = 133398380429840941814865
    input_bits = int_to_bitsLE(bits77_int, 77)
    symbols = encode_bits77(bits77_int)
    symbols_framed = [-10]*7
    symbols_framed.extend(symbols)
    symbols_framed.extend([-10]*7)
    audio_data = create_ft8_wave(symbols_framed, f_base = f_base, amplitude = 0.1, added_noise = -snr)

    dt = 0.16/3
    symbs_persec = 1/0.16
    sample_rate = 12000
    max_freq = 3000
    FFT_len = int(3 * 12000 // symbs_persec)
    FFT_out_len = int(FFT_len/2) + 1
    fmax_fft = sample_rate/2
    nFreqs = int(FFT_out_len * max_freq / fmax_fft)
    samps_perhop = int(12000 / (3*symbs_persec))
    fft_window = np.kaiser(FFT_len, 20)
    df = max_freq / (nFreqs)

    hops_percycle = 270
    fine_grid_complex = np.zeros((hops_percycle, nFreqs), dtype = np.complex64)
    for hop in range(hops_percycle):
        samp0 = hop*samps_perhop
        audio_for_fft = audio_data[samp0:samp0 + FFT_len]
        audio_for_fft = audio_for_fft * fft_window
        fine_grid_complex[hop,:] = np.fft.rfft(audio_for_fft)[:nFreqs]

    t0_idx=18
    f0_idx=int(f_base/df)
    c = Candidate(t0_idx, dt,  f0_idx, df)
    c.synced_grid_complex = fine_grid_complex[c.origin[0]:c.origin[0]+c.size[0], c.origin[1]:c.origin[1]+c.size[1]]
    synced_grid_complex = c.synced_grid_complex.reshape(num_symbols, 3, tones_persymb, 3)
    synced_grid_pwr = np.abs(synced_grid_complex[:,0,:,1])**2
    p = synced_grid_pwr[payload_symb_idxs] 
    llr0 = np.log(np.max(p[:,[4,5,6,7]], axis=1)) - np.log(np.max(p[:,[0,1,2,3]], axis=1))
    llr1 = np.log(np.max(p[:,[2,3,4,7]], axis=1)) - np.log(np.max(p[:,[0,1,5,6]], axis=1))
    llr2 = np.log(np.max(p[:,[1,2,6,7]], axis=1)) - np.log(np.max(p[:,[0,3,4,5]], axis=1))
    c.llr = np.column_stack((llr0, llr1, llr2)).ravel()
    c.llr_sd = np.std(c.llr)
    c.llr = np.clip(3.5 * c.llr / c.llr_sd, -3.7, 3.7)
    c.llr = np.asarray(c.llr, dtype=np.float32)
    c.llr0 = c.llr.copy()
    
    t0 = time.time()
    for n_its in range(max_its):
        c.llr, c.ncheck = c.ldpc.do_ldpc_iteration(c.llr)
        if(n_its == 0): ncheck_initial = c.ncheck
        success = (c.ncheck == 0)
        if(success): break
    t_ldpc = time.time() - t0

    output_bits = (c.llr > 0).astype(int).tolist()[:77]
    success = output_bits == input_bits
    results = {'snr':snr, 'success': success, 'llr_sd':c.llr_sd, 'sumabs_llr':np.sum(np.abs(c.llr0)), 'ncheck0':ncheck_initial, 'n_its':n_its,'t_ldpc':t_ldpc}
    
    return results

def test_vs_snr(snrs, max_its = 20, load_last = False):
    import matplotlib.pyplot as plt
    import pickle
    if(load_last):
        with open("last_montecarlo.pkl", "rb") as f:
            successes, failures = pickle.load(f)
    else:    
        successes, failures = [],[]
        for i, snr in enumerate(snrs):
            results = single_loopback(snr = snr, max_its = max_its)
            if(results['success']):
                successes.append(results)
            else:
                failures.append(results)
            if(not (i % 10)):
                print(f"{i}/{len(snrs)}")
        with open("last_montecarlo.pkl", "wb") as f:
            pickle.dump((successes, failures),f)        


    plot_params = ['llr_sd', 'sumabs_llr', 'ncheck0']
    fig, axs = plt.subplots(1, len(plot_params), figsize = (15,5))
    for iax, param in enumerate(plot_params):
        axs[iax].scatter([d['snr'] for d in successes],[d[param] for d in successes], color = 'green')
        axs[iax].scatter([d['snr'] for d in failures],[d[param] for d in failures], color = 'red')
        axs[iax].set_ylabel(param)
        axs[iax].set_xlabel("Imposed channel SNR")
    plt.suptitle("Proxies vs imposed SNR for successes and failures")
    plt.tight_layout()
    plt.show()

    plot_params = ['snr', 'llr_sd', 'sumabs_llr', 'ncheck0']
    fig, axs = plt.subplots(1, len(plot_params), figsize = (15,5))
    for iax, param in enumerate(plot_params):        
        xs = [s[param] for s in successes]
        xf = [f[param] for f in failures]
        x0 = np.min(xs)
        xn = np.max(xs)
        
        nbins = 30
        dx = (xn-x0)/(nbins -1)
        histvals = []
        xbins = np.arange(x0, xn, dx)
        for xbin in xbins:
            tot, suc = 0, 0
            for x in [x for x in xs if xbin <= x < xbin+dx]:
                tot +=1
                suc +=1
            for x in [x for x in xf if xbin <= x < xbin+dx]:
                tot +=1
            histvals.append(suc/tot if tot>0 else 0)
                
        p = axs[iax].plot(xbins,histvals, alpha = 0.7, lw=1)  
        axs[iax].set_xlabel(param)
        axs[iax].set_ylabel("Decoder success")

    plt.suptitle("Decoder performance against imposed SNR and proxies")
    plt.tight_layout()
    plt.show()


snrs = -26 + 10 * np.random.random(5000)
#test_vs_snr(snrs)
test_vs_snr(snrs, load_last = True)



"""
-24.00 dB   12.0% avg_its = 18     ms per ldpc =  3.58   ms_per_iteration = 0.20   
-23.50 dB   38.0% avg_its = 14     ms per ldpc =  2.88   ms_per_iteration = 0.21   
-23.00 dB   68.0% avg_its = 10     ms per ldpc =  2.04   ms_per_iteration = 0.21   
-22.50 dB   86.0% avg_its = 6      ms per ldpc =  1.30   ms_per_iteration = 0.22   
-22.00 dB   98.0% avg_its = 2      ms per ldpc =  0.72   ms_per_iteration = 0.35   
-21.50 dB  100.0% avg_its = 1      ms per ldpc =  0.38   ms_per_iteration = 0.37  
"""


"""
import matplotlib.pyplot as plt
fig,ax = plt.subplots()

for max_ncheck in [26,27,28,29,30,31,32,33,34]:
    res, x = test_vs_snr()
    ax.plot(x, res, label = f"{max_ncheck}")
    ax.set_title("Success vs max_ncheck")
    ax.legend()
    plt.pause(0.5)

plt.show()
"""
