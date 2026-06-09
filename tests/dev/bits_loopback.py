import numpy as np
import matplotlib.pyplot as plt

HPS=1
BPT=1
SYM_RATE=6.25
SAMP_RATE=12000
T_CYC=15
HOPS_PER_CYCLE = int(T_CYC*SYM_RATE*HPS)
BASE_FREQ_IDXS = np.array([BPT * t for t in range(8)])
PAYLOAD_SYMBOL_INDEXES = list(range(7, 36)) + list(range(43, 72))
BASE_PAYLOAD_HOPS = np.array([HPS * s for s in PAYLOAD_SYMBOL_INDEXES])
#GRAY CODE
# Tone  Bits
#   0   000 (0)
#   1   001 (1)
#   2   011 (*3)
#   3   010 (*2)
#   4   110 (*6)
#   5   100 (*4)
#   6   101 (*5)
#   7   111 (7)
GRAY = [0,1,3,2,5,6,4,7]
unGRAY = [0,1,3,2,6,4,5,7]

#============== Transmitter ========================================================

generator_matrix_rows = ["8329ce11bf31eaf509f27fc",  "761c264e25c259335493132",  "dc265902fb277c6410a1bdc",  "1b3f417858cd2dd33ec7f62",  "09fda4fee04195fd034783a",  "077cccc11b8873ed5c3d48a",  "29b62afe3ca036f4fe1a9da",  "6054faf5f35d96d3b0c8c3e",  "e20798e4310eed27884ae90",  "775c9c08e80e26ddae56318",  "b0b811028c2bf997213487c",  "18a0c9231fc60adf5c5ea32",  "76471e8302a0721e01b12b8",  "ffbccb80ca8341fafb47b2e",  "66a72a158f9325a2bf67170",  "c4243689fe85b1c51363a18",  "0dff739414d1a1b34b1c270",  "15b48830636c8b99894972e",  "29a89c0d3de81d665489b0e",  "4f126f37fa51cbe61bd6b94",  "99c47239d0d97d3c84e0940",  "1919b75119765621bb4f1e8",  "09db12d731faee0b86df6b8",  "488fc33df43fbdeea4eafb4",  "827423ee40b675f756eb5fe",  "abe197c484cb74757144a9a",  "2b500e4bc0ec5a6d2bdbdd0",  "c474aa53d70218761669360",  "8eba1a13db3390bd6718cec",  "753844673a27782cc42012e",  "06ff83a145c37035a5c1268",  "3b37417858cc2dd33ec3f62",  "9a4a5a28ee17ca9c324842c",  "bc29f465309c977e89610a4",  "2663ae6ddf8b5ce2bb29488",  "46f231efe457034c1814418",  "3fb2ce85abe9b0c72e06fbe",  "de87481f282c153971a0a2e",  "fcd7ccf23c69fa99bba1412",  "f0261447e9490ca8e474cec",  "4410115818196f95cdd7012",  "088fc31df4bfbde2a4eafb4",  "b8fef1b6307729fb0a078c0",  "5afea7acccb77bbc9d99a90",  "49a7016ac653f65ecdc9076",  "1944d085be4e7da8d6cc7d0",  "251f62adc4032f0ee714002",  "56471f8702a0721e00b12b8",  "2b8e4923f2dd51e2d537fa0",  "6b550a40a66f4755de95c26",  "a18ad28d4e27fe92a4f6c84",  "10c2e586388cb82a3d80758",  "ef34a41817ee02133db2eb0",  "7e9c0c54325a9c15836e000",  "3693e572d1fde4cdf079e86",  "bfb2cec5abe1b0c72e07fbe",  "7ee18230c583cccc57d4b08",  "a066cb2fedafc9f52664126",  "bb23725abc47cc5f4cc4cd2",  "ded9dba3bee40c59b5609b4",  "d9a7016ac653e6decdc9036",  "9ad46aed5f707f280ab5fc4",  "e5921c77822587316d7d3c2",  "4f14da8242a8b86dca73352",  "8b8b507ad467d4441df770e",  "22831c9cf1169467ad04b68",  "213b838fe2ae54c38ee7180",  "5d926b6dd71f085181a4e12",  "66ab79d4b29ee6e69509e56",  "958148682d748a38dd68baa",  "b8ce020cf069c32a723ab14",  "f4331d6d461607e95752746",  "6da23ba424b9596133cf9c8",  "a636bcbc7b30c5fbeae67fe",  "5cb0d86a07df654a9089a20",  "f11f106848780fc9ecdd80a",  "1fbb5364fb8d2c9d730d5ba",  "fcb86bc70a50c9d02a5d034",  "a534433029eac15f322e34c",  "c989d9c7c3d3b8c55d75130",  "7bb38b2f0186d46643ae962",  "2644ebadeb44b9467d1f42c",  "608cc857594bfbb55d69600"]
kGEN = np.array([int(row,16)>>1 for row in generator_matrix_rows])

def ldpc_encode(msg_crc: int) -> int:
    msg_crc = int(msg_crc)
    parity_bits = 0
    for row in map(int, kGEN):
        bit = bin(msg_crc & row).count("1") & 1
        parity_bits = (parity_bits << 1) | bit
    return (msg_crc << 83) | parity_bits, parity_bits

def gray_encode(bits: int) -> list[int]:
    syms = []
    for _ in range(174 // 3):
        chunk = bits & 0x7
        syms.insert(0, GRAY[chunk])
        bits >>= 3
    return syms

def append_crc(bits77_int):
    poly = 0x2757
    width = 14
    mask = (1 << width) - 1
    # Pad to 96 bits (77 + 14 + 5)
    nbits = 96
    bits14_int = 0
    for i in range(nbits):
        # bits77 is expected MSB-first (bit 76 first)
        inbit = ((bits77_int >> (76 - i)) & 1) if i < 77 else 0
        bit14 = (bits14_int >> (width - 1)) & 1
        bits14_int = ((bits14_int << 1) & mask) | inbit
        if bit14:
            bits14_int ^= poly
    bits91_int = (bits77_int << 14) | bits14_int
    return bits91_int, bits14_int

def create_ft8_wave(channel_symbols, fs=12000, f_base=100.0, f_step=6.25, amplitude = 0.5, added_noise = -50):
    symbol_len = int(fs * 0.160)
    t = np.arange(symbol_len) / fs
    start_sample = int(fs*0.0)
    phase = 0
    waveform = []
    for s in channel_symbols:
      #  s=4
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
        waveform += noise
    outframe = np.zeros(int(T_CYC*SAMP_RATE))
    outframe[start_sample:start_sample+len(waveform)] = waveform
    return outframe
#============== Receiver ========================================================

def spectrum(audio, max_freq = 300):
    fft_len = int(BPT * SAMP_RATE // SYM_RATE)
    fft_out_len = fft_len // 2 + 1
    nFreqs = int(fft_out_len * 2 * max_freq / SAMP_RATE)
    fft_window = np.hanning(fft_len).astype(np.float32)
    fft_phase = np.linspace(0, np.pi, fft_len)
    dt = T_CYC / HOPS_PER_CYCLE
    df = max_freq / nFreqs
    samps_perhop = int(SAMP_RATE // (HPS*SYM_RATE))
    spec_pwr = np.ones((HOPS_PER_CYCLE, nFreqs), dtype = np.float32)
    spec_phase = np.zeros((HOPS_PER_CYCLE, nFreqs), dtype = np.float32)
    for hop in range(79*HPS):
        s0 = hop*samps_perhop
        #aw = audio[s0: s0+fft_len] * fft_window
        aw = audio[s0: s0+fft_len]
        #aw = aw * np.exp(1j * fft_phase)
        z = np.fft.fft(aw)[:nFreqs]
        p = np.clip(z.real*z.real + z.imag*z.imag, 0.001, None)
        spec_pwr[hop, :] = p
        spec_phase[hop, :] = np.atan2(z.imag, z.real)
    return spec_pwr, spec_phase, df

def check_crc(bits91_int):
    bits77_int = bits91_int >> 14
    if(bits77_int > 0):
        crc14_int = 0
        for i in range(96):
            inbit = ((bits77_int >> (76 - i)) & 1) if i < 77 else 0
            bit14 = (crc14_int >> (14 - 1)) & 1
            crc14_int = ((crc14_int << 1) & ((1 << 14) - 1)) | inbit
            if bit14:
                crc14_int ^= 0x2757
        if(crc14_int == bits91_int & 0b11111111111111):
            return bits77_int

class LdpcDecoder:
    def __init__(self):
        self.CV6idx = np.array([[4,31,59,92,114,145],[5,23,60,93,121,150],[6,32,61,94,95,142],[5,31,63,96,125,137],[8,34,65,98,138,145],[9,35,66,99,106,125],[11,37,67,101,104,154],[12,38,68,102,148,161],[14,41,58,105,122,158],[0,32,71,105,106,156],[15,42,72,107,140,159],[10,43,74,109,120,165],[7,45,70,111,118,165],[18,37,76,103,115,162],[19,46,69,91,137,164],[1,47,73,112,127,159],[21,46,57,117,126,163],[15,38,61,111,133,157],[22,42,78,119,130,144],[19,35,62,93,135,160],[13,30,78,97,131,163],[2,43,79,123,126,168],[18,45,80,116,134,166],[11,49,60,117,118,143],[12,50,63,113,117,156],[23,51,75,128,147,148],[20,53,76,99,139,170],[34,81,132,141,170,173],[13,29,82,112,124,169],[3,28,67,119,133,172],[51,83,109,114,144,167],[6,49,80,98,131,172],[22,54,66,94,171,173],[25,40,76,108,140,147],[26,39,55,123,124,125],[17,48,54,123,140,166],[5,32,84,107,115,155],[8,53,62,130,146,154],[21,52,67,108,120,173],[2,12,47,77,94,122],[30,68,132,149,154,168],[4,38,74,101,135,166],[1,53,85,100,134,163],[14,55,86,107,118,170],[22,33,70,93,126,152],[10,48,87,91,141,156],[28,33,86,96,146,161],[21,56,84,92,139,158],[27,31,71,102,131,165],[0,25,44,79,127,146],[16,26,88,102,115,152],[50,56,97,162,164,171],[20,36,72,137,151,168],[15,46,75,129,136,153],[2,23,29,71,103,138],[8,39,89,105,133,150],[17,41,78,143,145,151],[24,37,64,98,121,159],[16,41,74,128,169,171]], dtype = np.int16)
        self.CV7idx = np.array([[3,30,58,90,91,95,152],[7,24,62,82,92,95,147],[4,33,64,77,97,106,153],[10,36,66,86,100,138,157],[7,39,69,81,103,113,144],[13,40,70,87,101,122,155],[16,36,73,80,108,130,153],[44,54,63,110,129,160,172],[17,35,75,88,112,113,142],[20,44,77,82,116,120,150],[18,34,58,72,109,124,160],[6,48,57,89,99,104,167],[24,52,68,89,100,129,155],[19,45,64,79,119,139,169],[0,3,51,56,85,135,151],[25,50,55,90,121,136,167],[1,26,40,60,61,114,132],[27,47,69,84,104,128,157],[11,42,65,88,96,134,158],[9,43,81,90,110,143,148],[29,49,59,85,136,141,161],[9,52,65,83,111,127,164],[27,28,83,87,116,142,149],[14,57,59,73,110,149,162]], dtype = np.int16)
        self.mC2V_prev6 = None
        self.mC2V_prev7 = None
        
    def calc_ncheck(self, llr):
        bits6 = llr[self.CV6idx] > 0
        self.parity6 = np.sum(bits6, axis=1) & 1
        bits7 = llr[self.CV7idx] > 0
        self.parity7 = np.sum(bits7, axis=1) & 1
        return int(np.sum(self.parity7) + np.sum(self.parity6))

    def _pass_messages(self, llr, CVidx, mC2V_prev, update_collector):
        if mC2V_prev is None:
            mC2V_prev = np.zeros(CVidx.shape, dtype=np.float32)
        mV2C = llr[CVidx] - mC2V_prev
        tanh_mV2C = np.tanh(-mV2C)
        tanh_mC2V = np.prod(tanh_mV2C, axis=1, keepdims=True)
        tanh_mC2V = tanh_mC2V / (tanh_mV2C + 0.001)
        alpha_atanh_approx = 1.18
        mC2V_curr  = tanh_mC2V / ((tanh_mC2V - alpha_atanh_approx) * (alpha_atanh_approx + tanh_mC2V))
        np.add.at(update_collector, CVidx, mC2V_curr - mC2V_prev)
        return mC2V_curr
    
    def do_ldpc_iteration(self, llr):
        update_collector = np.zeros_like(llr)
        self.mC2V_prev6 = self._pass_messages(llr, self.CV6idx, self.mC2V_prev6, update_collector)
        self.mC2V_prev7 = self._pass_messages(llr, self.CV7idx, self.mC2V_prev7, update_collector)
        llr += update_collector
        return llr, self.calc_ncheck(llr)

def demap_argmax(dBgrid_main, h0_idx, f0_idx, df, target_params = (3.3, 3.7)):
    hops = [i*HPS for i in range(79)]
    freq_idxs = f0_idx + BASE_FREQ_IDXS
    hops = h0_idx + BASE_PAYLOAD_HOPS
    dBgrid = dBgrid_main[np.ix_(hops, freq_idxs)]
    tones = np.argmax(dBgrid, axis = 1)
    bits_decoded_str = ''.join([f"{unGRAY[t]:03b}" for t in tones])
    llr = [-target_params[1]+2*target_params[1]*int(b) for b in bits_decoded_str]
    return llr

def demap(dBgrid_main, h0_idx, f0_idx, df, target_params = (3.3, 3.7)):
    freq_idxs = f0_idx + BASE_FREQ_IDXS
    hops = h0_idx + BASE_PAYLOAD_HOPS
    p = dBgrid_main[np.ix_(hops, freq_idxs)]
    pmax = np.max(p)
    snr = np.clip(int(pmax - np.min(p) - 58), -24, 24)
    llra = np.max(p[:, [4,5,6,7]], axis=1) - np.max(p[:, [0,1,2,3]], axis=1)
    llrb = np.max(p[:, [2,3,4,7]], axis=1) - np.max(p[:, [0,1,5,6]], axis=1)
    llrc = np.max(p[:, [1,2,6,7]], axis=1) - np.max(p[:, [0,3,4,5]], axis=1)
    llr = np.column_stack((llra, llrb, llrc))
    llr = llr.ravel() 
    llr_sd = int(0.5+100*np.std(llr))/100.0
    llr = target_params[0] * llr / (1e-12 + llr_sd)
    llr = np.clip(llr, -target_params[1], target_params[1])
    return [l for l in llr]

#============== Charts ========================================================
def show_spectrum(dBgrid_main, phase, f0, fn):
    fig, axs = plt.subplots(2, figsize=(4,12))
    axs[0].set_title("Signal amplitude")
    axs[0].imshow(dBgrid_main[:,f0:fn], origin = 'lower', aspect = 'auto', interpolation = 'nearest')
    axs[1].set_title("Signal phase")
    axs[1].imshow(phase, origin = 'lower', aspect = 'auto', interpolation = 'nearest')

def show_llr(encoded_bits174_str, llr, target_params = (3.3, 3.7)):
    fig, ax = plt.subplots(figsize=(15,4))
    encoded_bits174 = [-target_params[1]+2*target_params[1]*int(b) for b in encoded_bits174_str]
    ax.set_title("Demapped LLR overlaid on transmitted payload bits")
    ax.plot(encoded_bits174)
    ax.plot(llr)


#============== Main ========================================================

bits77_int = 0b00000000000000000000000000100000010010000000000111000001100011111000010010001
f_base = 40*6.25

bits91_int, bits14_int = append_crc(bits77_int)
bits174_int, bits83_int = ldpc_encode(bits91_int)
channel_payload_symbols = gray_encode(bits174_int)
costas=[3,1,4,0,6,5,2]
channel_symbols = costas + channel_payload_symbols[:29] + costas + channel_payload_symbols[29:] + costas

transmitted_payload_bits = "0"*174
bits = f"{bits174_int:03b}"
transmitted_payload_bits = "0"*(174-len(bits)) + bits 
print(f"{transmitted_payload_bits =                   }")
transmitted_payload_symbols_str = ''.join([str(s) for s in channel_payload_symbols])
print(f"{transmitted_payload_symbols_str=             }")

audio = create_ft8_wave(channel_symbols, f_base = f_base, added_noise = 0)
power, phase, df = spectrum(audio, max_freq = 3000)
f0_idx = int(f_base / df) 

dBgrid_main = 20*np.log10(power)
dBgrid_main = np.clip(dBgrid_main, np.max(dBgrid_main)-20, None)
show_spectrum(power, phase, f0_idx, f0_idx + 8*BPT)

llr = demap(power, 0, f0_idx, df)
#llr = demap_argmax(dBgrid_main, 0, f0_idx, df)
show_llr(transmitted_payload_bits, llr)
recovered_payload_bits_unGrayed_str = ''.join([f"{b}" for b in (np.array(llr) > 0).astype(int)])

print(f"{recovered_payload_bits_unGrayed_str=         }")

recovered_payload_symbols_unGrayed_str = ''.join([f"{int('0b'+s,2)}" for s in [recovered_payload_bits_unGrayed_str[i*3:i*3+3] for i in range(58)] ] )
inferred_payload_symbols_str = ''.join([str(GRAY[int(s)]) for s in recovered_payload_symbols_unGrayed_str])
print(f"{inferred_payload_symbols_str=                }")

bit_errors = [1 if a!=recovered_payload_bits_unGrayed_str[i] else 0 for i, a in enumerate(transmitted_payload_bits)]
print(f"Bit errors {np.sum(bit_errors)}")

plt.show()



