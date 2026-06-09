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
        aw = audio[s0: s0+fft_len] * fft_window
        aw = audio[s0: s0+fft_len]
        #aw = aw * np.exp(1j * fft_phase)
        z = np.fft.fft(aw)[:nFreqs]
        p = np.clip(z.real*z.real + z.imag*z.imag, 0.001, None)
        spec_pwr[hop, :] = p
        spec_phase[hop, :] = np.atan2(z.imag, z.real)
    return spec_pwr, spec_phase, df

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

def show_llr(encoded_bits174_str, llr, llr_hard, target_params = (3.3, 3.7)):
    fig, ax = plt.subplots(figsize=(15,4))
    encoded_bits174 = [-target_params[1]+2*target_params[1]*int(b) for b in encoded_bits174_str]
    ax.set_title(f"Demapped LLR overlaid on transmitted payload bits with {added_noise}dB added noise")
    ax.plot(encoded_bits174, label = 'Encoded bits')
    ax.plot(llr, label = f"llr ({assess_llr(transmitted_payload_bits, llr)} bit errors)")
    ax.plot(llr_hard, label = f"llr_hard ({assess_llr(transmitted_payload_bits, llr_hard)} bit errors)")
    plt.legend()

def assess_llr(transmitted_payload_bits, llr):
    recovered_payload_bits_unGrayed_str = ''.join([f"{b}" for b in (np.array(llr) > 0).astype(int)])
    #print(f"{recovered_payload_bits_unGrayed_str=         }")
    recovered_payload_symbols_unGrayed_str = ''.join([f"{int('0b'+s,2)}" for s in [recovered_payload_bits_unGrayed_str[i*3:i*3+3] for i in range(58)] ] )
    inferred_payload_symbols_str = ''.join([str(GRAY[int(s)]) for s in recovered_payload_symbols_unGrayed_str])
    #print(f"{inferred_payload_symbols_str=                }")
    bit_errors = [1 if a!=recovered_payload_bits_unGrayed_str[i] else 0 for i, a in enumerate(transmitted_payload_bits)]
    #print(f"Bit errors {np.sum(bit_errors)}")
    return np.sum(bit_errors)

#============== Main ========================================================

print("**Now internally consistent and ready to test alternative demappers e.g. correlated**")
print("**Also worth looking at refactoring to allow montecarlo tests against added noise levels**")
print("**Could strip out the faithful bits174_int generation and use random**\n")

bits77_int = 0b00000000000000000000000000100000010010000000000111000001100011111000010010001
f_base = 40*6.25
added_noise = 25

bits91_int, bits14_int = append_crc(bits77_int)
bits174_int, bits83_int = ldpc_encode(bits91_int)
channel_payload_symbols = gray_encode(bits174_int)
costas=[3,1,4,0,6,5,2]
channel_symbols = costas + channel_payload_symbols[:29] + costas + channel_payload_symbols[29:] + costas

bits = f"{bits174_int:03b}"
transmitted_payload_bits = "0"*(174-len(bits)) + bits 
print(f"{transmitted_payload_bits =                   }")
transmitted_payload_symbols_str = ''.join([str(s) for s in channel_payload_symbols])
print(f"{transmitted_payload_symbols_str=             }")

audio = create_ft8_wave(channel_symbols, f_base = f_base, added_noise = added_noise)
power, phase, df = spectrum(audio, max_freq = 3000)
f0_idx = int(f_base / df) 

dBgrid_main = 20*np.log10(power)
dBgrid_main = np.clip(dBgrid_main, np.max(dBgrid_main)-20, None)
show_spectrum(power, phase, f0_idx, f0_idx + 8*BPT)

llr = demap(power, 0, f0_idx, df)
llr_hard = demap_argmax(dBgrid_main, 0, f0_idx, df)
show_llr(transmitted_payload_bits, llr, llr_hard)


plt.show()



