# Takes an example 91 bits message ('VK1ABC VK3JPK QF22', including crc),
# adds parity bits to make 174 bits, simulates 174 Log Likelyhood Ratios
# with added noise, and runs an LDPC decode algorithm and crc check to recover
# the original message. A graph shows how the LDPC decoder converges the LLRs
# onto the original noise-free version

import numpy as np
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

def ldpc_encode(msg_crc: int) -> int:
    generator_matrix_rows = ["8329ce11bf31eaf509f27fc",  "761c264e25c259335493132",  "dc265902fb277c6410a1bdc",  "1b3f417858cd2dd33ec7f62",  "09fda4fee04195fd034783a",  "077cccc11b8873ed5c3d48a",  "29b62afe3ca036f4fe1a9da",  "6054faf5f35d96d3b0c8c3e",  "e20798e4310eed27884ae90",  "775c9c08e80e26ddae56318",  "b0b811028c2bf997213487c",  "18a0c9231fc60adf5c5ea32",  "76471e8302a0721e01b12b8",  "ffbccb80ca8341fafb47b2e",  "66a72a158f9325a2bf67170",  "c4243689fe85b1c51363a18",  "0dff739414d1a1b34b1c270",  "15b48830636c8b99894972e",  "29a89c0d3de81d665489b0e",  "4f126f37fa51cbe61bd6b94",  "99c47239d0d97d3c84e0940",  "1919b75119765621bb4f1e8",  "09db12d731faee0b86df6b8",  "488fc33df43fbdeea4eafb4",  "827423ee40b675f756eb5fe",  "abe197c484cb74757144a9a",  "2b500e4bc0ec5a6d2bdbdd0",  "c474aa53d70218761669360",  "8eba1a13db3390bd6718cec",  "753844673a27782cc42012e",  "06ff83a145c37035a5c1268",  "3b37417858cc2dd33ec3f62",  "9a4a5a28ee17ca9c324842c",  "bc29f465309c977e89610a4",  "2663ae6ddf8b5ce2bb29488",  "46f231efe457034c1814418",  "3fb2ce85abe9b0c72e06fbe",  "de87481f282c153971a0a2e",  "fcd7ccf23c69fa99bba1412",  "f0261447e9490ca8e474cec",  "4410115818196f95cdd7012",  "088fc31df4bfbde2a4eafb4",  "b8fef1b6307729fb0a078c0",  "5afea7acccb77bbc9d99a90",  "49a7016ac653f65ecdc9076",  "1944d085be4e7da8d6cc7d0",  "251f62adc4032f0ee714002",  "56471f8702a0721e00b12b8",  "2b8e4923f2dd51e2d537fa0",  "6b550a40a66f4755de95c26",  "a18ad28d4e27fe92a4f6c84",  "10c2e586388cb82a3d80758",  "ef34a41817ee02133db2eb0",  "7e9c0c54325a9c15836e000",  "3693e572d1fde4cdf079e86",  "bfb2cec5abe1b0c72e07fbe",  "7ee18230c583cccc57d4b08",  "a066cb2fedafc9f52664126",  "bb23725abc47cc5f4cc4cd2",  "ded9dba3bee40c59b5609b4",  "d9a7016ac653e6decdc9036",  "9ad46aed5f707f280ab5fc4",  "e5921c77822587316d7d3c2",  "4f14da8242a8b86dca73352",  "8b8b507ad467d4441df770e",  "22831c9cf1169467ad04b68",  "213b838fe2ae54c38ee7180",  "5d926b6dd71f085181a4e12",  "66ab79d4b29ee6e69509e56",  "958148682d748a38dd68baa",  "b8ce020cf069c32a723ab14",  "f4331d6d461607e95752746",  "6da23ba424b9596133cf9c8",  "a636bcbc7b30c5fbeae67fe",  "5cb0d86a07df654a9089a20",  "f11f106848780fc9ecdd80a",  "1fbb5364fb8d2c9d730d5ba",  "fcb86bc70a50c9d02a5d034",  "a534433029eac15f322e34c",  "c989d9c7c3d3b8c55d75130",  "7bb38b2f0186d46643ae962",  "2644ebadeb44b9467d1f42c",  "608cc857594bfbb55d69600"]
    kGEN = np.array([int(row,16)>>1 for row in generator_matrix_rows])
    msg_crc = int(msg_crc)
    parity_bits = 0
    for row in map(int, kGEN):
        bit = bin(msg_crc & row).count("1") & 1
        parity_bits = (parity_bits << 1) | bit
    return (msg_crc << 83) | parity_bits


kNCW = 3
kNM = 1+np.array([[3,30,58,90,91,95,152],[4,31,59,92,114,145,-1],[5,23,60,93,121,150,-1],[6,32,61,94,95,142,-1],[7,24,62,82,92,95,147],[5,31,63,96,125,137,-1],[4,33,64,77,97,106,153],[8,34,65,98,138,145,-1],[9,35,66,99,106,125,-1],[10,36,66,86,100,138,157],[11,37,67,101,104,154,-1],[12,38,68,102,148,161,-1],[7,39,69,81,103,113,144],[13,40,70,87,101,122,155],[14,41,58,105,122,158,-1],[-1,32,71,105,106,156,-1],[15,42,72,107,140,159,-1],[16,36,73,80,108,130,153],[10,43,74,109,120,165,-1],[44,54,63,110,129,160,172],[7,45,70,111,118,165,-1],[17,35,75,88,112,113,142],[18,37,76,103,115,162,-1],[19,46,69,91,137,164,-1],[1,47,73,112,127,159,-1],[20,44,77,82,116,120,150],[21,46,57,117,126,163,-1],[15,38,61,111,133,157,-1],[22,42,78,119,130,144,-1],[18,34,58,72,109,124,160],[19,35,62,93,135,160,-1],[13,30,78,97,131,163,-1],[2,43,79,123,126,168,-1],[18,45,80,116,134,166,-1],[6,48,57,89,99,104,167],[11,49,60,117,118,143,-1],[12,50,63,113,117,156,-1],[23,51,75,128,147,148,-1],[24,52,68,89,100,129,155],[19,45,64,79,119,139,169],[20,53,76,99,139,170,-1],[34,81,132,141,170,173,-1],[13,29,82,112,124,169,-1],[3,28,67,119,133,172,-1],[-1,3,51,56,85,135,151],[25,50,55,90,121,136,167],[51,83,109,114,144,167,-1],[6,49,80,98,131,172,-1],[22,54,66,94,171,173,-1],[25,40,76,108,140,147,-1],[1,26,40,60,61,114,132],[26,39,55,123,124,125,-1],[17,48,54,123,140,166,-1],[5,32,84,107,115,155,-1],[27,47,69,84,104,128,157],[8,53,62,130,146,154,-1],[21,52,67,108,120,173,-1],[2,12,47,77,94,122,-1],[30,68,132,149,154,168,-1],[11,42,65,88,96,134,158],[4,38,74,101,135,166,-1],[1,53,85,100,134,163,-1],[14,55,86,107,118,170,-1],[9,43,81,90,110,143,148],[22,33,70,93,126,152,-1],[10,48,87,91,141,156,-1],[28,33,86,96,146,161,-1],[29,49,59,85,136,141,161],[9,52,65,83,111,127,164],[21,56,84,92,139,158,-1],[27,31,71,102,131,165,-1],[27,28,83,87,116,142,149],[-1,25,44,79,127,146,-1],[16,26,88,102,115,152,-1],[50,56,97,162,164,171,-1],[20,36,72,137,151,168,-1],[15,46,75,129,136,153,-1],[2,23,29,71,103,138,-1],[8,39,89,105,133,150,-1],[14,57,59,73,110,149,162],[17,41,78,143,145,151,-1],[24,37,64,98,121,159,-1],[16,41,74,128,169,171,-1]], dtype=int)
kMN = 1+np.array([[15,44,72],[24,50,61],[32,57,77],[-1,43,44],[1,6,60],[2,5,53],[3,34,47],[4,12,20],[7,55,78],[8,63,68],[9,18,65],[10,35,59],[11,36,57],[13,31,42],[14,62,79],[16,27,76],[17,73,82],[21,52,80],[22,29,33],[23,30,39],[25,40,75],[26,56,69],[28,48,64],[2,37,77],[4,38,81],[45,49,72],[50,51,73],[54,70,71],[43,66,71],[42,67,77],[-1,31,58],[1,5,70],[3,15,53],[6,64,66],[7,29,41],[8,21,30],[9,17,75],[10,22,81],[11,27,60],[12,51,78],[13,49,50],[14,80,82],[16,28,59],[18,32,63],[19,25,72],[20,33,39],[23,26,76],[24,54,57],[34,52,65],[35,47,67],[36,45,74],[37,44,46],[38,56,68],[40,55,61],[19,48,52],[45,51,62],[44,69,74],[26,34,79],[-1,14,29],[1,67,79],[2,35,50],[3,27,50],[4,30,55],[5,19,36],[6,39,81],[7,59,68],[8,9,48],[10,43,56],[11,38,58],[12,23,54],[13,20,64],[15,70,77],[16,29,75],[17,24,79],[18,60,82],[21,37,76],[22,40,49],[6,25,57],[28,31,80],[32,39,72],[17,33,47],[12,41,63],[4,25,42],[46,68,71],[53,54,69],[44,61,67],[9,62,66],[13,65,71],[21,59,73],[34,38,78],[-1,45,63],[-1,23,65],[1,4,69],[2,30,64],[3,48,57],[-1,3,4],[5,59,66],[6,31,74],[7,47,81],[8,34,40],[9,38,61],[10,13,60],[11,70,73],[12,22,77],[10,34,54],[14,15,78],[6,8,15],[16,53,62],[17,49,56],[18,29,46],[19,63,79],[20,27,68],[21,24,42],[12,21,36],[1,46,50],[22,53,73],[25,33,71],[26,35,36],[20,35,62],[28,39,43],[18,25,56],[2,45,81],[13,14,57],[32,51,52],[29,42,51],[5,8,51],[26,32,64],[24,68,72],[37,54,82],[19,38,76],[17,28,55],[31,47,70],[41,50,58],[27,43,78],[33,59,61],[30,44,60],[45,67,76],[5,23,75],[7,9,77],[39,40,69],[16,49,52],[41,65,67],[3,21,71],[35,63,80],[12,28,46],[1,7,80],[55,66,72],[4,37,49],[11,37,63],[58,71,79],[2,25,78],[44,75,80],[-1,64,73],[6,17,76],[10,55,58],[13,38,53],[15,36,65],[9,27,54],[14,59,69],[16,24,81],[19,29,30],[11,66,67],[22,74,79],[26,31,61],[23,68,74],[18,20,70],[33,52,60],[34,45,46],[32,58,75],[39,42,82],[40,41,62],[48,74,82],[19,43,47],[41,48,56]], dtype=int)
kNRW = np.array([7, 6, 6, 6, 7, 6, 7, 6, 6, 7, 6, 6, 7, 7, 6, 6, 6, 7, 6, 7, 6, 7, 6, 6, 6, 7, 6, 6, 6, 7, 6, 6, 6, 6, 7, 6, 6, 6, 7, 7, 6, 6, 6, 6, 7, 7, 6, 6, 6, 6, 7, 6, 6, 6, 7, 6, 6, 6, 6, 7, 6, 6, 6, 7, 6, 6, 6, 7, 7, 6, 6, 7, 6, 6, 6, 6, 6, 6, 6, 7, 6, 6, 6], dtype=int)
kN = 174  # Number of variables (message length)
kM = 83   # Number of check nodes

def safe_atanh(x, eps=1e-12):
    x = np.clip(x, -1 + eps, 1 - eps)
    return 0.5 * np.log((1 + x) / (1 - x))
  #  return np.arctanh(x)

def count_syndrome_checks(zn):
    ncheck = 0
    cw = (zn > 0).astype(int)
    for i in range(1, kM+1):
        synd = sum(cw[kNM[i-1, 0:kNRW[i-1]]-1])
        if ((synd %2) != 0): ncheck += 1
    if ncheck == 0:
        decoded_bits174_LE_list = cw.tolist() 
        decoded_bits91_int = bitsLE_to_int(decoded_bits174_LE_list[0:91])
        if(not check_crc(decoded_bits91_int)):
            return -1, cw, []
        return 0, cw, decoded_bits174_LE_list
    return ncheck, cw, []

def decode174_91(llr, maxiterations = 50, alpha = 0.05, gamma = 0.03, nstall_max = 12, ncheck_max = 30):
    import matplotlib.pyplot as plt
    fig,ax = plt.subplots()

    toc = np.zeros((7, kM), dtype=np.float32)       # message -> check messages
    tanhtoc = np.zeros((7, kM), dtype=np.float64)
    tov = np.zeros((kNCW, kN), dtype=np.float32)    # check -> message messages
    nclast, nstall = 0, 0                           # stall condition variables
    zn = np.copy(llr)                   # working copy of llrs
    rng = np.max(llr) - np.min(llr)     # indication of scale of llrs
    mult = rng * gamma          # empricical multiplier for tov, proportional to llr scale

    ncheck, cw, decoded_bits174_LE_list = count_syndrome_checks(zn)
    if(ncheck ==0): return decoded_bits174_LE_list, it

    for it in range(maxiterations + 1):
        for i in range(kN):
            zn[i] += mult*sum(tov[:,i])
        ncheck, cw, decoded_bits174_LE_list = count_syndrome_checks(zn)
        ax.cla()
        ax.plot(zn)
        print(ncheck, bitsLE_to_int(cw.tolist()) ^ FT8ref.bits174)
        plt.pause(0.5)
        if(ncheck <=0): return decoded_bits174_LE_list, it

        nstall = 0 if ncheck < nclast else nstall +1
        nclast = ncheck
        if(nstall > nstall_max or ncheck > ncheck_max):         # early exit condition
            return [], it
        
        for j in range(kM):
            for i in range(kNRW[j]):    
                ibj = int(kNM[j, i])
                if (ibj == 0):
                    toc[i, j] = 0
                else:
                    toc[i, j] = zn[ibj-1]
                for kk in range(kNCW):
                    if(kMN[ibj-1,kk-1] == j+1):
                        toc[i, j] -= tov[kk, ibj-1]

        for i in range(kM):
            tanhtoc[:, i] = np.tanh(-toc[:, i] / 2.0)

        for j in range(kN):
            for i in range(kNCW):
                ichk=kMN[j,i]
                mask = (kNM[ichk-1, :kNRW[ichk-1]] != j+1)                            
                tvals = tanhtoc[:kNRW[ichk-1], ichk-1][mask]
                Tmn = np.prod(tvals)
                tov[i,j]= alpha * 2* safe_atanh(-Tmn) + (1-alpha)*tov[i,j]

    return [], it


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

def bitsLE_to_int(bits):
    """bits is MSB-first."""
    n = 0
    for b in bits:
        n = (n << 1) | (b & 1)
    return n

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




