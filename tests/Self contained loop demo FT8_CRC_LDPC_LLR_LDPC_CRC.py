# Takes an example 91 bits message ('VK1ABC VK3JPK QF22', including crc),
# adds parity bits to make 174 bits, simulates 174 Log Likelyhood Ratios
# with added noise, and runs an LDPC decode algorithm and crc check to recover
# the original message. A graph shows how the LDPC decoder converges the LLRs
# onto the original noise-free version

import numpy as np
import sys
sys.path.append(r"C:\Users\drala\Documents\Projects\GitHub\PyFT8")
class FT8ref:
    def __init__(self):
        self.url = "https://pengowray.github.io/ft8play/"
        self.msg = "VK1ABC VK3JPK QF22"
        self.bits77 = 0b11100001111111000101001101010111000100000011110100001111000111001010001010001
        self.bits14 = 0b00111100110010
        self.bits83 = 0b01101010111110101110000011111111010100101110011011100110010000000000011100010000001
        self.bits91 = self.bits77 <<14 | self.bits14
        self.bits174 = self.bits91 <<83 | self.bits83

FT8ref = FT8ref()

kNCW = 3
kNRW = [7,6,6,6,7,6,7,6,6,7,6,6,7,7,6,6,6,7,6,7,6,7,6,6,6,7,6,6,6,7,6,6,6,6,7,6,6,6,7,7,6,6,6,6,7,7,6,6,6,6,7,6,6,6,7,6,6,6,6,7,6,6,6,7,6,6,6,7,7,6,6,7,6,6,6,6,6,6,6,7,6,6,6]
colorder = [0,1,2,3,28,4,5,6,7,8,9, 10, 11, 34, 12, 32, 13, 14, 15, 16, 17, 18, 36, 29, 43, 19, 20, 42, 21, 40, 30, 37, 22, 47, 61, 45, 44, 23, 41, 39, 49, 24, 46, 50, 48, 26, 31, 33, 51, 38, 52, 59, 55, 66, 57, 27, 60, 35, 54, 58, 25, 56, 62, 64, 67, 69, 63, 68, 70, 72, 65, 73, 75, 74, 71, 77, 78, 76, 79, 80,  53, 81, 83, 82, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99,100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,123,124,125,126,127,128,129,130,131,132,133,134,135,136,137,138,139,140,141,142,143,144,145,146,147,148,149,150,151,152,153,154,155,156,157,158,159,160,161,162,163,164,165,166,167,168,169,170,171,172,173]
kMN = np.array([
[16,25,33,1,2,3,4,5,8,9,10,11,12,14,15,17,18,22,23,24,26,27,29,3,5,46,51,55,44,43,1,2,4,7,8,9,10,11,12,13,14,15,17,19,20,21,24,25,35,36,37,38,39,41,20,46,45,27,1,2,3,4,5,6,7,8,9,11,12,13,14,16,17,18,19,22,23,7,29,33,18,13,5,47,54,45,10,14,22,35,1,1,2,3,4,1,6,7,8,9,10,11,12,13,11,15,7,17,18,19,20,21,22,13,2,23,26,27,21,29,19,3,14,33,30,6,27,25,38,20,18,32,42,28,34,31,46,6,8,40,17,42,4,36,13,2,56,5,12,59,3,45,1,7,11,14,16,10,15,17,20,12,23,27,24,19,34,35,33,40,41,49,20,42],
[45,51,58,44,7,6,35,13,56,64,19,36,37,32,63,28,74,53,30,31,41,57,49,38,39,50,52,71,67,68,32,6,16,65,30,22,18,23,28,52,50,81,29,33,26,34,27,55,53,48,46,45,57,56,49,52,70,35,15,68,36,28,31,20,40,60,10,44,39,24,21,71,30,25,61,38,41,26,32,40,34,42,26,69,55,62,63,66,60,39,46,24,5,31,49,4,60,32,48,35,39,14,71,23,35,16,9,54,50,30,64,28,25,22,47,54,34,36,36,40,26,46,15,52,43,9,33,69,55,39,29,48,51,44,60,45,68,24,10,41,50,66,22,64,29,8,67,38,38,72,26,76,65,18,56,39,37,28,60,25,30,67,75,32,69,21,53,46,59,43,42,75,44,49],
[73,62,78,45,61,54,48,21,79,69,66,60,58,43,80,77,83,81,34,40,76,70,65,78,82,73,74,72,72,78,59,71,54,67,42,31,76,82,61,79,51,83,60,64,73,40,77,58,66,68,75,47,69,62,53,63,75,80,30,80,51,51,56,37,82,69,49,57,59,55,65,78,76,80,83,77,50,58,81,73,48,64,43,72,70,68,67,72,74,79,64,66,70,65,58,5,67,75,82,41,62,61,74,78,55,79,16,63,57,47,80,69,43,37,51,74,72,37,63,44,57,82,58,53,52,52,65,73,83,77,56,71,59,79,62,61,77,76,78,70,53,68,72,81,47,81,73,50,64,80,79,81,74,77,59,54,66,55,70,82,31,68,80,62,75,71,61,47,76,83,63,83,48,57],
])
kNM = np.array([
[4,5,6,7,8,6,5,9,10,11,12,13,8,14,15,1,16,17,11,45,8,18,19,20,2,21,22,16,23,19,20,14,3,19,7,12,13,24,25,20,21,35,14,4,1,26,52,7,23,26,2,27,18,6,28,9,22,3,31,12,5,2,15,10,23,11,29,30,10,22,28,28,1,17,51,21,16,3,9,15,18,25,17],
[31,32,24,33,25,32,34,35,36,37,38,39,40,41,42,33,43,37,44,55,46,36,38,47,48,45,47,39,43,35,36,31,44,46,49,50,51,52,53,46,54,82,30,29,4,51,84,50,55,41,27,40,49,33,48,54,53,13,69,43,39,54,56,44,34,49,34,50,53,57,32,29,26,27,57,37,47,24,40,58,42,38,42],
[59,60,61,62,63,64,65,66,67,67,68,69,70,71,59,72,73,74,75,64,71,76,77,70,74,78,58,62,79,59,63,79,80,81,58,61,64,76,69,65,77,133,83,68,52,56,110,81,67,77,41,56,55,85,70,63,68,48,133,66,75,86,87,82,71,88,87,60,66,85,72,84,45,89,98,73,76,30,90,60,79,65,75],
[91,93,94,95,83,97,78,99,100,87,102,103,82,88,106,106,108,81,110,111,112,89,104,92,113,83,118,112,120,73,94,98,124,117,90,118,114,129,90,80,100,142,113,120,57,91,115,99,95,109,61,124,124,108,85,131,109,78,150,89,102,101,108,91,94,92,97,86,84,93,103,88,80,103,163,138,130,72,106,74,144,99,129],
[92,115,122,96,93,126,98,139,107,101,105,149,104,102,123,107,141,109,121,130,119,113,116,138,128,117,127,134,131,110,136,132,127,135,100,119,118,148,101,120,140,171,125,134,86,122,145,132,172,141,62,125,141,116,105,147,121,95,155,97,136,135,119,111,127,142,147,137,112,140,132,117,128,116,165,152,137,104,134,111,146,122,170],
[96,146,151,143,96,138,107,146,126,139,155,162,114,123,159,157,160,131,166,161,166,114,163,165,160,121,164,158,145,125,161,164,169,167,105,144,157,149,130,140,171,174,170,173,136,137,168,173,174,148,115,126,167,156,129,155,174,123,169,135,167,164,171,144,153,157,162,142,128,159,166,143,147,153,172,169,154,139,151,150,152,160,172],
[153,0,0,0,148,0,154,0,0,158,0,0,145,156,0,0,0,154,0,173,0,143,0,0,0,151,0,0,0,161,0,0,0,0,168,0,0,0,156,170,0,0,0,0,152,168,0,0,0,0,133,0,0,0,158,0,0,0,0,159,0,0,0,149,0,0,0,162,165,0,0,150,0,0,0,0,0,0,0,163,0,0,0],
])

kN = 174
kK = 91
kM = kN - kK

from PyFT8.FT8_crc import check_crc

def bitsLE_to_int(bits):
    """bits is MSB-first."""
    n = 0
    for b in bits:
        n = (n << 1) | (b & 1)
    return n

def safe_atanh(x, eps=1e-12):
    x = np.clip(x, -1 + eps, 1 - eps)
    return 0.5 * np.log((1 + x) / (1 - x))
  #  return np.arctanh(x)

def count_syndrome_checks(zn):
    ncheck = 0
    cw = (zn > 0).astype(int)
    for i in range(kM):
        ichk = kNM[0:kNRW[i],i] - 1
        ichk = ichk[(ichk >=0)]
        synd = sum(cw[ichk])
        if ((synd %2) != 0): ncheck += 1
    if ncheck == 0:
        decoded_bits174_LE_list = cw.tolist() 
        decoded_bits91_int = bitsLE_to_int(decoded_bits174_LE_list[0:91])
        if(not check_crc(decoded_bits91_int)):
            return -1, cw, []
        return 0, cw, decoded_bits174_LE_list
    return ncheck, cw, []

def decode174_91(llr, maxiterations = 50, alpha = 0.05, gamma = 0.03, nstall_max = 12, ncheck_max = 30):
    toc = np.zeros((7, kM), dtype=np.float32)       # message -> check messages
    tanhtoc = np.zeros((7, kM), dtype=np.float64)
    tov = np.zeros((kNCW, kN), dtype=np.float32)    # check -> message messages
    nclast, nstall = 0, 0                           # stall condition variables
    zn = np.copy(llr)                   # working copy of llrs
    rng = np.max(llr) - np.min(llr)     # indication of scale of llrs
    mult = rng * gamma          # empricical multiplier for tov, proportional to llr scale

    ncheck, cw, decoded_bits174_LE_list = count_syndrome_checks(zn)
    if(ncheck ==0): return decoded_bits174_LE_list, it

    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    
    for it in range(maxiterations + 1):
        ax.cla()
        ax.plot(zn)
        plt.pause(0.25)
        for i in range(kN):
            zn[i] += mult*sum(tov[:,i])
            
        ncheck, cw, decoded_bits174_LE_list = count_syndrome_checks(zn)
        if(ncheck <=0): return decoded_bits174_LE_list, it
        
        nstall = 0 if ncheck < nclast else nstall +1
        nclast = ncheck
        if(nstall > nstall_max or ncheck > ncheck_max):         # early exit condition
            return [], it
        
        # compute toc = messages from variable node -> check node
        # For each check node j, for each connected variable i subtract messages from checks (tov)
        # that correspond to other checks connected to variable ibj (connections specified by kMN[ibj, :])
        for j in range(kM):
            for i in range(kNRW[j]):    
                ibj = int(kNM[i, j] - 1)   
                toc[i, j] = zn[ibj]
                for kk in range(kNCW):
                    chknum = kMN[kk, ibj] - 1
                    if chknum == j:
                        continue
                    toc[i, j] -= tov[kk, ibj]

        for j in range(kM):
            tanhtoc[:kNRW[j], j] = np.tanh(-toc[:kNRW[j], j] / 2.0)

        # compute tov (check -> variable messages)
        # for each variable node j, it connects to kNCW checks (kMN[j, :])
        for variable_node in range(kN):
            for kk in range(kNCW):
                chknum = kMN[kk, variable_node] - 1
                if chknum == -1:
                    tov[kk, variable_node] = 0.0
                    continue
                ichk = int(chknum)
                # build mask over the neighbours of check ichk excluding current variable 'var'
                neigh_count = kNRW[ichk]
                neigh_vars = kNM[:neigh_count, ichk]  - 1
                mask = (neigh_vars != variable_node)
                if mask.sum() == 0:
                    Tmn = 0.0
                else:
                    tvals = tanhtoc[:neigh_count, ichk][mask]
                    Tmn = np.prod(tvals) if tvals.size > 0 else 0.0
                y = safe_atanh(-Tmn)
                new_val = 2.0 * safe_atanh(-Tmn)
                tov[kk, variable_node] = alpha * new_val + (1 - alpha) * tov[kk, variable_node]
    return [], it

def ldpc_encode(msg_crc: int) -> int:
    generator_matrix_rows = ["8329ce11bf31eaf509f27fc",  "761c264e25c259335493132",  "dc265902fb277c6410a1bdc",  "1b3f417858cd2dd33ec7f62",  "09fda4fee04195fd034783a",  "077cccc11b8873ed5c3d48a",  "29b62afe3ca036f4fe1a9da",  "6054faf5f35d96d3b0c8c3e",  "e20798e4310eed27884ae90",  "775c9c08e80e26ddae56318",  "b0b811028c2bf997213487c",  "18a0c9231fc60adf5c5ea32",  "76471e8302a0721e01b12b8",  "ffbccb80ca8341fafb47b2e",  "66a72a158f9325a2bf67170",  "c4243689fe85b1c51363a18",  "0dff739414d1a1b34b1c270",  "15b48830636c8b99894972e",  "29a89c0d3de81d665489b0e",  "4f126f37fa51cbe61bd6b94",  "99c47239d0d97d3c84e0940",  "1919b75119765621bb4f1e8",  "09db12d731faee0b86df6b8",  "488fc33df43fbdeea4eafb4",  "827423ee40b675f756eb5fe",  "abe197c484cb74757144a9a",  "2b500e4bc0ec5a6d2bdbdd0",  "c474aa53d70218761669360",  "8eba1a13db3390bd6718cec",  "753844673a27782cc42012e",  "06ff83a145c37035a5c1268",  "3b37417858cc2dd33ec3f62",  "9a4a5a28ee17ca9c324842c",  "bc29f465309c977e89610a4",  "2663ae6ddf8b5ce2bb29488",  "46f231efe457034c1814418",  "3fb2ce85abe9b0c72e06fbe",  "de87481f282c153971a0a2e",  "fcd7ccf23c69fa99bba1412",  "f0261447e9490ca8e474cec",  "4410115818196f95cdd7012",  "088fc31df4bfbde2a4eafb4",  "b8fef1b6307729fb0a078c0",  "5afea7acccb77bbc9d99a90",  "49a7016ac653f65ecdc9076",  "1944d085be4e7da8d6cc7d0",  "251f62adc4032f0ee714002",  "56471f8702a0721e00b12b8",  "2b8e4923f2dd51e2d537fa0",  "6b550a40a66f4755de95c26",  "a18ad28d4e27fe92a4f6c84",  "10c2e586388cb82a3d80758",  "ef34a41817ee02133db2eb0",  "7e9c0c54325a9c15836e000",  "3693e572d1fde4cdf079e86",  "bfb2cec5abe1b0c72e07fbe",  "7ee18230c583cccc57d4b08",  "a066cb2fedafc9f52664126",  "bb23725abc47cc5f4cc4cd2",  "ded9dba3bee40c59b5609b4",  "d9a7016ac653e6decdc9036",  "9ad46aed5f707f280ab5fc4",  "e5921c77822587316d7d3c2",  "4f14da8242a8b86dca73352",  "8b8b507ad467d4441df770e",  "22831c9cf1169467ad04b68",  "213b838fe2ae54c38ee7180",  "5d926b6dd71f085181a4e12",  "66ab79d4b29ee6e69509e56",  "958148682d748a38dd68baa",  "b8ce020cf069c32a723ab14",  "f4331d6d461607e95752746",  "6da23ba424b9596133cf9c8",  "a636bcbc7b30c5fbeae67fe",  "5cb0d86a07df654a9089a20",  "f11f106848780fc9ecdd80a",  "1fbb5364fb8d2c9d730d5ba",  "fcb86bc70a50c9d02a5d034",  "a534433029eac15f322e34c",  "c989d9c7c3d3b8c55d75130",  "7bb38b2f0186d46643ae962",  "2644ebadeb44b9467d1f42c",  "608cc857594bfbb55d69600"]
    kGEN = np.array([int(row,16)>>1 for row in generator_matrix_rows])
    msg_crc = int(msg_crc)
    parity_bits = 0
    for row in map(int, kGEN):
        bit = bin(msg_crc & row).count("1") & 1
        parity_bits = (parity_bits << 1) | bit
    return (msg_crc << 83) | parity_bits


def add_noise_to_llr(llr, snr_db):
    snr_linear = 10 ** (snr_db / 10)
    noise_std = np.std(llr) / np.sqrt(snr_linear)
    noise = np.random.normal(0, noise_std, size=llr.shape)
    llr_noisy = llr + noise
    return llr_noisy

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
    return bits91_int

def check_crc(bits91_int):
    """Return True if the 91-bit message (77 data + 14 CRC) passes WSJT-X CRC-14."""
    bits14_int = bits91_int & 0b11111111111111
    bits77_int = bits91_int >> 14
    return bits14_int == crc14(bits77_int)

def int_to_bitsLE(n, width):
    """Return [b(width-1), ..., b0], MSB-first."""
    return [ (n >> (width - 1 - i)) & 1 for i in range(width) ]

snr = 4

bits77_int = FT8ref.bits77
print(f"77 message bits for 'VK1ABC VK3JPK QF22':\n{bits77_int:b}")
bits91_int = append_crc(bits77_int)
print(f"Message plus crc (91 bits):\n{bits91_int:b}")
print(f"CRC loop test: check_crc(append_crc(bits77_int)) = { check_crc(append_crc(bits77_int))}")
print(f"Message plus crc reference from {FT8ref.url}\n{FT8ref.bits91:b}")
bits174_int = ldpc_encode(bits91_int)
print(f"With parity (174 bits):\n{bits174_int:b}")
print(f"Message plus crc and parity reference from {FT8ref.url}\n{FT8ref.bits174:b}")

#simulate LLRs
bits174_LE_list = int_to_bitsLE(bits174_int,174)
llr = 200000 * np.array(bits174_LE_list) - 100000  # LLRs for each bit (encoded message)
llr = add_noise_to_llr(llr, snr)
# use previously simulated LLRs
llr = [141976.7 ,99810.7 ,46130.2 ,-32773.0 ,-182578.0 ,-38903.1 ,-185318.1 ,102046.3 ,164321.4 ,79022.4 ,165541.2 ,71432.2 ,154712.0 ,226197.6 ,-90388.1 ,-167197.5 ,-163347.8 ,139632.0 ,-75639.7 ,188099.1 ,-169130.9 ,-54549.3 ,209751.3 ,-33450.8 ,-156923.1 ,68173.3 ,5055.5 ,103752.8 ,-149998.9 ,-15865.0 ,128111.0 ,83494.1 ,-158544.6 ,-165696.7 ,-92858.5 ,105922.2 ,-182352.6 ,-116112.7 ,-157327.8 ,-140389.8 ,-86814.3 ,-111650.0 ,66053.4 ,70492.5 ,93814.6 ,100755.2 ,-200206.3 ,-42840.7 ,-176575.4 ,-124039.3 ,-113832.9 ,-133771.0 ,29138.6 ,140545.2 ,71596.2 ,106426.6 ,-78241.7 ,-212689.4 ,-51502.5 ,159727.3 ,100858.6 ,191720.2 ,-184304.4 ,-253468.6 ,25457.0 ,-182373.0 ,92256.1 ,-184018.7 ,553.6 ,-34634.3 ,-6778.7 ,-146053.8 ,58642.6 ,-65822.6 ,-142835.2 ,-131131.4 ,138476.2 ,-62969.1 ,-71351.6 ,78123.5 ,-6955.2 ,118320.3 ,164493.9 ,-34249.4 ,-84165.1 ,112891.1 ,81640.6 ,-140672.4 ,2861.4 ,97824.0 ,-71994.8 ,-81978.3 ,103858.8 ,76631.6 ,-118140.3 ,58559.2 ,-121561.4 ,-3801.1 ,-140518.1 ,47009.1 ,-27047.5 ,127523.6 ,21395.8 ,112950.0 ,-147640.6 ,199710.6 ,-126112.9 ,65929.3 ,153657.4 ,52866.2 ,-13223.3 ,-107310.4 ,-233263.0 ,-183125.0 ,-30445.0 ,103095.2 ,64925.5 ,33344.3 ,166262.7 ,149886.0 ,225034.6 ,129772.7 ,88658.8 ,-119426.4 ,92968.1 ,-134749.9 ,127461.9 ,-145967.0 ,-47121.7 ,153197.8 ,-112978.0 ,76910.3 ,178922.2 ,73220.5 ,49810.2 ,-67119.4 ,47275.3 ,64471.7 ,-145152.6 ,198923.1 ,90308.4 ,19075.3 ,-79961.1 ,-58620.0 ,89845.0 ,65221.0 ,-163669.5 ,-138832.5 ,92203.9 ,-117974.3 ,-177335.2 ,-157065.0 ,-91328.2 ,-131490.9 ,-93551.1 ,-31726.7 ,-168738.9 ,-44757.9 ,-150817.9 ,-65517.4 ,128364.7 ,142862.7 ,138347.5 ,2876.3 ,-28032.6 ,-95690.2 ,64228.1 ,-131277.9 ,-13883.4 ,-89323.6 ,-60705.4 ,-60398.3 ,-174149.7 ,-51293.2 ]


print(f"LLRs with noise:\n"+','.join([f"{ll:.1f} " for ll in llr]))

# Decode the message using LDPC
decoded_bits174_LE_list, it = decode174_91(llr)
bits174_int = bitsLE_to_int(decoded_bits174_LE_list)
if(len(decoded_bits174_LE_list)>0):
    print(f"SNR = {snr}dB. Bits decoded after {it} iterations and passed CRC\n{bits174_int:b}")
else:
    print(f"SNR = {snr}dB. Bits decoded after {it} iterations but failed CRC\n{bits174_int:b}")




