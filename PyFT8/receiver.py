import numpy as np
import time, pyaudio, threading
from PyFT8.udp_comms import UdpComms

HPS, BPT = 4, 2
TIME_WINDOW = [-1.5, 3.5]
SYM_RATE, SAMP_RATE = 6.25, 12000
MIN_SCORE = 0.5
MAX_CANDS = 400
MAX_LDPC = 25

#------------------------------
HPC = int(15 * SYM_RATE * HPS)
T_SEARCH =  TIME_WINDOW[1]+(36+7)/SYM_RATE
H0_RANGE = [int(SYM_RATE * HPS * t) for t in TIME_WINDOW]

# =============== Call hashing ========================================
call_hashes = {}
def add_call_hash(call):
    global call_hashes
    chars = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ/"
    call_padded = (call + "          ")[:11]
    hashes = []
    for m in [10,12,22]:
        x = 0
        for c in call_padded:
            x = 38*x + chars.find(c)
            x = x & ((int(1) << 64) - 1)
        x = x & ((1 << 64) - 1)
        x = x * 47055833459
        x = x & ((1 << 64) - 1)
        x = x >> (64 - m)
        hashes.append(x)
        call_hashes[(x,m)] = call

#=========== Unpacking functions ========================================
CALLSIGN_PREFIXES1 = "A,B,C,D,E,F,G,H,I,J,K,L,M,N,O,P,R,S,T,U,V,W,X,Y,Z"
CALLSIGN_PREFIXES2 = "2A,2B,2C,2D,2E,2F,2G,2H,2I,2J,2K,2L,2M,2N,2O,2P,2Q,2R,2S,2T,2U,2V,2W,2X,2Y,2Z,3A,3B,3C,3D,3D,3E,3F,3G,3H,3I,3J,3K,3L,3M,3N,3O,3P,3Q,3R,3S,3T,3U,3V,3W,3X,3Y,3Z,4A,4B,4C,4D,4E,4F,4G,4H,4I,4J,4K,4L,4M,4O,4P,4Q,4R,4S,4T,4U,4V,4W,4X,4Y,4Z,5A,5B,5C,5D,5E,5F,5G,5H,5I,5J,5K,5L,5M,5N,5O,5P,5Q,5R,5S,5T,5U,5V,5W,5X,5Y,5Z,6A,6B,6C,6D,6E,6F,6G,6H,6I,6J,6K,6L,6M,6N,6O,6P,6Q,6R,6S,6T,6U,6V,6W,6X,6Y,6Z,7A,7B,7C,7D,7E,7F,7G,7H,7I,7J,7K,7L,7M,7N,7O,7P,7Q,7R,7S,7T,7U,7V,7W,7X,7Y,7Z,8A,8B,8C,8D,8E,8F,8G,8H,8I,8J,8K,8L,8M,8N,8O,8P,8Q,8R,8S,8T,8U,8V,8W,8X,8Y,8Z,9A,9B,9C,9D,9E,9F,9G,9H,9I,9J,9K,9L,9M,9N,9O,9P,9Q,9R,9S,9T,9U,9V,9W,9X,9Y,9Z,A2,A3,A4,A5,A6,A7,A8,A9,AA,AB,AC,AD,AE,AF,AG,AH,AI,AJ,AK,AL,AM,AN,AO,AP,AQ,AR,AS,AT,AU,AV,AW,AX,AY,AZ,BA,BB,BC,BD,BE,BF,BG,BH,BI,BJ,BK,BL,BM,BN,BO,BP,BQ,BR,BS,BT,BU,BV,BW,BX,BY,BZ,C2,C3,C4,C5,C6,C7,C8,C9,CA,CB,CC,CD,CE,CF,CG,CH,CI,CJ,CK,CL,CM,CN,CO,CP,CQ,CR,CS,CT,CU,CV,CW,CX,CY,CZ,D2,D3,D4,D5,D6,D7,D8,D9,DA,DB,DC,DD,DE,DF,DG,DH,DI,DJ,DK,DL,DM,DN,DO,DP,DQ,DR,DS,DT,DU,DV,DW,DX,DY,DZ,E2,E3,E4,E5,E6,E7,EA,EB,EC,ED,EE,EF,EG,EH,EI,EJ,EK,EL,EM,EN,EO,EP,EQ,ER,ES,ET,EU,EV,EW,EX,EY,EZ,FA,FB,FC,FD,FE,FF,FG,FH,FI,FJ,FK,FL,FM,FN,FO,FP,FQ,FR,FS,FT,FU,FV,FW,FX,FY,FZ,GA,GB,GC,GD,GE,GF,GG,GH,GI,GJ,GK,GL,GM,GN,GO,GP,GQ,GR,GS,GT,GU,GV,GW,GX,GY,GZ,H2,H3,H4,H6,H7,H8,H9,HA,HB,HC,HD,HE,HF,HG,HH,HI,HJ,HK,HL,HM,HN,HO,HP,HQ,HR,HS,HT,HU,HV,HW,HX,HY,HZ,IA,IB,IC,ID,IE,IF,IG,IH,II,IJ,IK,IL,IM,IN,IO,IP,IQ,IR,IS,IT,IU,IV,IW,IX,IY,IZ,J2,J3,J4,J5,J6,J7,J8,JA,JB,JC,JD,JE,JF,JG,JH,JI,JJ,JK,JL,JM,JN,JO,JP,JQ,JR,JS,JT,JU,JV,JW,JX,JY,JZ,KA,KB,KC,KD,KE,KF,KG,KH,KI,KJ,KK,KL,KM,KN,KO,KP,KQ,KR,KS,KT,KU,KV,KW,KX,KY,KZ,L2,L3,L4,L5,L6,L7,L8,L9,LA,LB,LC,LD,LE,LF,LG,LH,LI,LJ,LK,LL,LM,LN,LO,LP,LQ,LR,LS,LT,LU,LV,LW,LX,LY,LZ,MA,MB,MC,MD,ME,MF,MG,MH,MI,MJ,MK,ML,MM,MN,MO,MP,MQ,MR,MS,MT,MU,MV,MW,MX,MY,MZ,NA,NB,NC,ND,NE,NF,NG,NH,NI,NJ,NK,NL,NM,NN,NO,NP,NQ,NR,NS,NT,NU,NV,NW,NX,NY,NZ,OA,OB,OC,OD,OE,OF,OG,OH,OI,OJ,OK,OL,OM,ON,OO,OP,OQ,OR,OS,OT,OU,OV,OW,OX,OY,OZ,P2,P3,P4,P5,P6,P7,P8,P9,PA,PB,PC,PD,PE,PF,PG,PH,PI,PJ,PJ,PJ,PK,PL,PM,PN,PO,PP,PQ,PR,PS,PT,PU,PV,PW,PX,PY,PZ,RA,RB,RC,RD,RE,RF,RG,RH,RI,RJ,RK,RL,RM,RN,RO,RP,RQ,RR,RS,RT,RU,RV,RW,RX,RY,RZ,S2,S3,S5,S6,S7,S8,S9,SA,SB,SC,SD,SE,SF,SG,SH,SI,SJ,SK,SL,SM,SN,SO,SP,SQ,SR,SS,SS,ST,SU,SV,SW,SX,SY,SZ,T2,T3,T4,T5,T6,T7,T8,TA,TB,TC,TD,TE,TF,TG,TH,TI,TJ,TK,TL,TM,TN,TO,TP,TQ,TR,TS,TT,TU,TV,TW,TX,TY,TZ,UA,UB,UC,UD,UE,UF,UG,UH,UI,UJ,UK,UL,UM,UN,UO,UP,UQ,UR,US,UT,UU,UV,UW,UX,UY,UZ,V2,V3,V4,V5,V6,V7,V8,VA,VB,VC,VD,VE,VF,VG,VH,VI,VJ,VK,VL,VM,VN,VO,VP,VQ,VR,VS,VT,VU,VV,VW,VX,VY,VZ,WA,WB,WC,WD,WE,WF,WG,WH,WI,WJ,WK,WL,WM,WN,WO,WP,WQ,WR,WS,WT,WU,WV,WW,WX,WY,WZ,XA,XB,XC,XD,XE,XF,XG,XH,XI,XJ,XK,XL,XM,XN,XO,XP,XQ,XR,XS,XT,XU,XV,XW,XX,XY,XZ,Y2,Y3,Y4,Y5,Y6,Y7,Y8,Y9,YA,YB,YC,YD,YE,YF,YG,YH,YI,YJ,YK,YL,YM,YN,YO,YP,YQ,YR,YS,YT,YU,YV,YW,YX,YY,Z2,Z3,Z8,ZA,ZB,ZC,ZD,ZE,ZF,ZG,ZH,ZI,ZJ,ZK,ZL,ZM,ZN,ZO,ZP,ZQ,ZR,ZS,ZT,ZU,ZV,ZW,ZX,ZY,ZZ"

def get_bitfields(bits, lengths):
    fields = []
    for n in lengths:
        mask = (1 << n) - 1
        fields.append(bits & mask)
        bits >>= n
    return *fields, bits

def unpack(bits):
    if not bits:
        return None
    
    i3, bits74 = get_bitfields(bits,[3])
    if i3 == 0:
        n3, bits71 = get_bitfields(bits74,[3])
        if n3 <= 4:
            #return (['Free text', 'DXpedition', 'Field Day', 'Field Day', 'Telemetry'][n3], 'not', 'implemented')
            return None
        else:
            #return ('Unknown mode','not','implemented')
            return None
    elif i3 == 1 or i3 == 2: # 1 = Std Msg incl /R 2 = 'EU VHF' = Std Msg incl /P
        return unpack_std(bits74, i3)
    elif i3 == 3:
        #return ('RTTY RU','not','implemented')
        return None
    elif i3 == 4:
        cq, rrr, swp, c58, hsh, _ = get_bitfields(bits74, [1,2,1,58,12])
        if cq and rrr or (not cq and not rrr):
            return None
        ca = "CQ" if cq else f"<{call_hashes.get((hsh,12), '...')}>"
        cb = ""
        for i in range(12):
            cb = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ/"[c58 % 38] + cb
            c58 = c58 // 38
        cb =  cb.strip()
        add_call_hash(cb)
        (ca, cb) = (cb, ca) if swp else (ca, cb)
        return (ca, cb, ('', 'RRR', 'RR73', '73')[rrr])
    elif i3 == 5:
        #return ('EU VHF','not','implemented')
        return None

def unpack_std(bits74, i3):
    g16, cb29, ca29, _ = get_bitfields(bits74,[16,29,29])
    g15 = g16 & 0x7FFF
    if g15 == 0:
        return None
    if g15 < 32400:
        a, nn = divmod(g15, 1800)
        b, nn = divmod(nn, 100)
        c, d = divmod(nn, 10)
        grid_rpt =  chr(65+a) + chr(65+b) + str(c) + str(d)
    elif g15 - 32400 <= 4:
        grid_rpt =  ('', '', 'RRR', 'RR73', '73')[g15 - 32400]
    else:
        prefix = 'R' if (g16 >> 15) else ''
        grid_rpt = prefix + f"{(g15 - 32435):+03d}"
    msg_tuple = (call_29(ca29, i3), call_29(cb29, i3), grid_rpt)
    if not ('' in msg_tuple) and not (None in msg_tuple) and not 'CQ' in msg_tuple[-1]:
        return msg_tuple

def call_29(call_int29, i3):    
    portable_rover = call_int29 & 1
    call_int28 = call_int29>>1
    if call_int28 < 3:
        return ['DE', 'QRZ', 'CQ'][call_int28]
    elif call_int28 < 1004:
        return f"CQ {call_int28 - 3:03d}"
    elif call_int28 < 21443:
        x, txt = call_int28 - 1003, ''
        for i in range(4):
            txt = " ABCDEFGHIJKLMNOPQRSTUVWXYZ"[int(x % 27)] + txt
            x //= 27
        return f"CQ {txt.strip()}"
    elif call_int28 < 2063592+4194303:
        return f"<{call_hashes.get((call_int28 - 2063592, 22), '...')}>"
    else:
        call = standard_call28(call_int28, i3)
        if call is not None:
            if portable_rover:
                call = call + ('/P' if i3 == 2 else '/R')
            if call.endswith("/R") and not call[0] in ['A','K','N','W']:
                return None
            add_call_hash(call)
            return call

def standard_call28(call_int28, i3):
    nn = call_int28 - (2063592 + 4194304)
    from string import ascii_uppercase as ltrs, digits as digs
    call_fields = [ (' ' + digs + ltrs, 36*10*27**3),   (digs + ltrs, 10*27**3), (digs + ' ' * 17, 27**3),
                    (' ' + ltrs, 27**2),           (' ' + ltrs,   27), (' ' + ltrs,   1) ]
    chars = []
    for alphabet, div in call_fields:
        idx, nn = divmod(nn, div)
        chars.append(alphabet[idx])
    call = ''.join(chars).strip()
    return simple_validate_call(call)

def simple_validate_call(call):
    if not ' ' in call and len(call)>=3:
        if call[0] in CALLSIGN_PREFIXES1 and call[1].isnumeric():
            if not (call[0] in "B,F,G,I,K,M,N,R,W" and call[2].isnumeric()):
                return call
        if call[:2] in CALLSIGN_PREFIXES2 and call[2].isnumeric():
            return call
        
def crc_unpack91(bits91_int):
    bits77_int = bits91_int >> 14
    msg = None
    if(bits77_int > 0):
        crc14_int = 0
        for i in range(96):
            inbit = ((bits77_int >> (76 - i)) & 1) if i < 77 else 0
            bit14 = (crc14_int >> (14 - 1)) & 1
            crc14_int = ((crc14_int << 1) & ((1 << 14) - 1)) | inbit
            if bit14:
                crc14_int ^= 0x2757
        if crc14_int == bits91_int & 0b11111111111111:
            msg = unpack(bits77_int) 
    return msg, bits77_int

#============== Early decode if message bits are sound ===============================================

def decode_raw91(p, i):
    def syms_to_int(syms):
        bint = 0
        for s in syms:
            bint = (bint << 3) | (s & 7)
        return bint
    ch_syms = np.argmax(p[:31, :], axis = 1)
    de_gray = [0,1,3,2,6,4,5,7]
    for j in range(2):
        if j == 1:
            ch_syms[:11] = 0
            ch_syms[8] = 1
        syms = [de_gray[s] for s in ch_syms]
        bits91_int = syms_to_int(syms) >> 2
        msg_tuple, bits77_int = crc_unpack91(bits91_int)
        if msg_tuple:
            return msg_tuple, f"GOOD91 t={i} {['','CQ'][j]}"
    return None, None

def bits_to_int(llr):
    bits_int = 0
    for bit in (llr > 0).astype(int).tolist():
        bits_int = (bits_int << 1) | bit
    return bits_int

#============== LDPC ===========================================================
CVidx_all = np.array([[4,31,59,91,92,96,153],[8,25,63,83,93,96,148],[5,34,65,78,98,107,154],[11,37,67,87,101,139,158],[8,40,70,82,104,114,145],[14,41,71,88,102,123,156],[17,37,74,81,109,131,154],[45,55,64,111,130,161,173],[18,36,76,89,113,114,143],[21,45,78,83,117,121,151],[19,35,59,73,110,125,161],[7,49,58,90,100,105,168],[25,53,69,90,101,130,156],[20,46,65,80,120,140,170],[1,4,52,57,86,136,152],[26,51,56,91,122,137,168],[2,27,41,61,62,115,133],[28,48,70,85,105,129,158],[12,43,66,89,97,135,159],[10,44,82,91,111,144,149],[30,50,60,86,137,142,162],[10,53,66,84,112,128,165],[28,29,84,88,117,143,150],[15,58,60,74,111,150,163],[5,32,60,93,115,146,0],[6,24,61,94,122,151,0],[7,33,62,95,96,143,0],[6,32,64,97,126,138,0],[9,35,66,99,139,146,0],[10,36,67,100,107,126,0],[12,38,68,102,105,155,0],[13,39,69,103,149,162,0],[15,42,59,106,123,159,0],[1,33,72,106,107,157,0],[16,43,73,108,141,160,0],[11,44,75,110,121,166,0],[8,46,71,112,119,166,0],[19,38,77,104,116,163,0],[20,47,70,92,138,165,0],[2,48,74,113,128,160,0],[22,47,58,118,127,164,0],[16,39,62,112,134,158,0],[23,43,79,120,131,145,0],[20,36,63,94,136,161,0],[14,31,79,98,132,164,0],[3,44,80,124,127,169,0],[19,46,81,117,135,167,0],[12,50,61,118,119,144,0],[13,51,64,114,118,157,0],[24,52,76,129,148,149,0],[21,54,77,100,140,171,0],[35,82,133,142,171,174,0],[14,30,83,113,125,170,0],[4,29,68,120,134,173,0],[52,84,110,115,145,168,0],[7,50,81,99,132,173,0],[23,55,67,95,172,174,0],[26,41,77,109,141,148,0],[27,40,56,124,125,126,0],[18,49,55,124,141,167,0],[6,33,85,108,116,156,0],[9,54,63,131,147,155,0],[22,53,68,109,121,174,0],[3,13,48,78,95,123,0],[31,69,133,150,155,169,0],[5,39,75,102,136,167,0],[2,54,86,101,135,164,0],[15,56,87,108,119,171,0],[23,34,71,94,127,153,0],[11,49,88,92,142,157,0],[29,34,87,97,147,162,0],[22,57,85,93,140,159,0],[28,32,72,103,132,166,0],[1,26,45,80,128,147,0],[17,27,89,103,116,153,0],[51,57,98,163,165,172,0],[21,37,73,138,152,169,0],[16,47,76,130,137,154,0],[3,24,30,72,104,139,0],[9,40,90,106,134,151,0],[18,42,79,144,146,152,0],[25,38,65,99,122,160,0],[17,42,75,129,170,172,0]], dtype = np.int16)
llr175 = np.zeros(175, dtype=np.float32)
mC2V_prev = np.zeros(CVidx_all.shape, dtype=np.float32)
import warnings
warnings.filterwarnings("error")
def decode(p, i):
    def atanh(x):
        a = 1.03
        y = -x / ((x-a)*(x+a))
        y[(x > a * 0.93)] = 7
        y[(x < -a * 0.93)] = -7
        return y
    global llr175, mC2V_prev
    llra = np.max(p[:, [4,5,6,7]], axis=1) - np.max(p[:, [0,1,2,3]], axis=1)
    llrb = np.max(p[:, [2,3,4,7]], axis=1) - np.max(p[:, [0,1,5,6]], axis=1)
    llrc = np.max(p[:, [1,2,6,7]], axis=1) - np.max(p[:, [0,3,4,5]], axis=1)
    llr = np.column_stack((llra, llrb, llrc))
    llr = llr.ravel()
    llr = 2.55 * llr / (np.std(llr) + 1e-12)
    llr175[1:] = llr
    llr_clip = 7
    llr175 = np.clip(llr175, -llr_clip, llr_clip)
    mC2V_prev[:, :] = 0
    ch_llr_saved = llr175[1:]
    llr_saved = None
    for ldpc_it in range(MAX_LDPC):
        mV2C = llr175[CVidx_all] - mC2V_prev
        tanh_mV2C = np.tanh(-mV2C / 2)
        tanh_mC2V = np.prod(tanh_mV2C, axis=1, keepdims=True)
        tanh_mC2V[24:,:6] = np.prod(tanh_mV2C[24:,:6], axis=1, keepdims=True)
        orig_err = np.geterr()
        np.seterr(all = 'ignore')
        tanh_mC2V = np.divide(tanh_mC2V, tanh_mV2C)
        mC2V_curr = 2 * atanh(-tanh_mC2V)
        np.seterr(**orig_err)
        np.add.at(llr175, CVidx_all, mC2V_curr - mC2V_prev)
        llr175[0]=0
        llr175 = np.clip(llr175, -llr_clip, llr_clip)
        mC2V_prev = mC2V_curr
        bits = llr175[CVidx_all] > 0
        parity = np.sum(bits, axis=1) & 1
        ncheck = int(np.sum(parity))
        if(ncheck == 0):
            bits91_int = bits_to_int(llr175[1:92])
            msg_tuple, bits77_int = crc_unpack91(bits91_int)
            return msg_tuple, f"LDPC   t={i} its={ldpc_it+1}", llr_saved, ch_llr_saved
        if ldpc_it == 5:
            llr_saved = llr175[1:]
    return None, '', llr_saved, ch_llr_saved

#============== OSD ===========================================================
generator_matrix_rows = ["8329ce11bf31eaf509f27fc",  "761c264e25c259335493132",  "dc265902fb277c6410a1bdc",  "1b3f417858cd2dd33ec7f62",  "09fda4fee04195fd034783a",  "077cccc11b8873ed5c3d48a",  "29b62afe3ca036f4fe1a9da",  "6054faf5f35d96d3b0c8c3e",  "e20798e4310eed27884ae90",  "775c9c08e80e26ddae56318",  "b0b811028c2bf997213487c",  "18a0c9231fc60adf5c5ea32",  "76471e8302a0721e01b12b8",  "ffbccb80ca8341fafb47b2e",  "66a72a158f9325a2bf67170",  "c4243689fe85b1c51363a18",  "0dff739414d1a1b34b1c270",  "15b48830636c8b99894972e",  "29a89c0d3de81d665489b0e",  "4f126f37fa51cbe61bd6b94",  "99c47239d0d97d3c84e0940",  "1919b75119765621bb4f1e8",  "09db12d731faee0b86df6b8",  "488fc33df43fbdeea4eafb4",  "827423ee40b675f756eb5fe",  "abe197c484cb74757144a9a",  "2b500e4bc0ec5a6d2bdbdd0",  "c474aa53d70218761669360",  "8eba1a13db3390bd6718cec",  "753844673a27782cc42012e",  "06ff83a145c37035a5c1268",  "3b37417858cc2dd33ec3f62",  "9a4a5a28ee17ca9c324842c",  "bc29f465309c977e89610a4",  "2663ae6ddf8b5ce2bb29488",  "46f231efe457034c1814418",  "3fb2ce85abe9b0c72e06fbe",  "de87481f282c153971a0a2e",  "fcd7ccf23c69fa99bba1412",  "f0261447e9490ca8e474cec",  "4410115818196f95cdd7012",  "088fc31df4bfbde2a4eafb4",  "b8fef1b6307729fb0a078c0",  "5afea7acccb77bbc9d99a90",  "49a7016ac653f65ecdc9076",  "1944d085be4e7da8d6cc7d0",  "251f62adc4032f0ee714002",  "56471f8702a0721e00b12b8",  "2b8e4923f2dd51e2d537fa0",  "6b550a40a66f4755de95c26",  "a18ad28d4e27fe92a4f6c84",  "10c2e586388cb82a3d80758",  "ef34a41817ee02133db2eb0",  "7e9c0c54325a9c15836e000",  "3693e572d1fde4cdf079e86",  "bfb2cec5abe1b0c72e07fbe",  "7ee18230c583cccc57d4b08",  "a066cb2fedafc9f52664126",  "bb23725abc47cc5f4cc4cd2",  "ded9dba3bee40c59b5609b4",  "d9a7016ac653e6decdc9036",  "9ad46aed5f707f280ab5fc4",  "e5921c77822587316d7d3c2",  "4f14da8242a8b86dca73352",  "8b8b507ad467d4441df770e",  "22831c9cf1169467ad04b68",  "213b838fe2ae54c38ee7180",  "5d926b6dd71f085181a4e12",  "66ab79d4b29ee6e69509e56",  "958148682d748a38dd68baa",  "b8ce020cf069c32a723ab14",  "f4331d6d461607e95752746",  "6da23ba424b9596133cf9c8",  "a636bcbc7b30c5fbeae67fe",  "5cb0d86a07df654a9089a20",  "f11f106848780fc9ecdd80a",  "1fbb5364fb8d2c9d730d5ba",  "fcb86bc70a50c9d02a5d034",  "a534433029eac15f322e34c",  "c989d9c7c3d3b8c55d75130",  "7bb38b2f0186d46643ae962",  "2644ebadeb44b9467d1f42c",  "608cc857594bfbb55d69600"]
kGEN = np.array([int(row,16)>>1 for row in generator_matrix_rows])
A = np.zeros((83, 91), dtype=np.uint8)
for i, row in enumerate(kGEN):
    for j in range(91):
        A[i, 90 - j] = (row >> j) & 1
G0 = np.concatenate([np.eye(91, dtype=np.uint8), A.T],axis=1)

def osd(llr_pack):
    source, llr = llr_pack
    chbits174 = (llr>0).astype(np.uint8)
    chvals174 = np.abs(llr)

    rowperm = np.arange(91)
    colperm = np.argsort(-np.abs(llr))
    curr_row = 0
    G = G0.copy()
    for curr_col in range(174):
        ones_below = np.where(G[rowperm[curr_row:], colperm[curr_col]] == 1)[0]
        if ones_below.size > 0:
            swap_row = curr_row + ones_below[0]
            rowperm[[curr_row, swap_row]] = rowperm[[swap_row, curr_row]]
            r_curr = rowperm[curr_row]
            c_curr = colperm[curr_col]
            g_c_curr = G[:, c_curr].copy()
            g_c_curr[r_curr] = 0
            rows_to_xor = np.where(g_c_curr == 1)[0]
            G[rows_to_xor, :] ^= G[r_curr, :]
            colperm[[curr_row, curr_col]] = colperm[[curr_col, curr_row]]  
            curr_row += 1
            if curr_row > 90:
                break
          
    chbits91 = chbits174[colperm][:91]
    chbits91[rowperm] = chbits91

    base_cw = ((chbits91 @ G) & 1)
    """
    bits91_int = bits_to_int(base_cw)
    msg_tuple, bits77_int = crc_unpack91(bits91_int)
    if msg_tuple:
        return msg_tuple, f"OSD0{source}"
    """
    fliplist = rowperm[::-1]
    current_best_distance = 1e20
    cw_out91 = None
    for i in range(91):
        cw = base_cw ^ G[fliplist[i]] # Single flip
        if i: # Double flips with every j < i
            cw2 = base_cw ^ G[fliplist[i]] ^ G[fliplist[:i]]
            candidates = np.vstack((cw, cw2))
        else:
            candidates = cw[None, :]
        distances = np.sum(np.abs(llr)[None, :] * (candidates != chbits174), axis=1)
        best_idx = np.argmin(distances)
        if distances[best_idx] < current_best_distance:
            current_best_distance = distances[best_idx]
            cw_out91 = candidates[best_idx, :91].copy()
        if cw_out91 is not None:
            bits91_int = bits_to_int(cw_out91)
            msg_tuple, bits77_int = crc_unpack91(bits91_int)
            if msg_tuple:
                return msg_tuple, f"OSD2{source}"
    return None, ''

#============== AUDIO ========================================================
class AudioIn:
    def __init__(self, input_keywords, max_freq):
        samples_per_hop = int(SAMP_RATE / (SYM_RATE * HPS))
        self.samples_per_half_hop = int(samples_per_hop / 2)
        fft_len = int(BPT * SAMP_RATE // SYM_RATE)
        fft_out_len = fft_len // 2 + 1
        self.nFreqs = int(fft_out_len * 2 * max_freq / SAMP_RATE)
        self.audio_buffer = np.zeros(fft_len + self.samples_per_half_hop, dtype=np.float32)
        self.fft_in = np.zeros(fft_len, dtype=np.float32)
        self.fft_window = np.hanning(fft_len).astype(np.float32)
        self.tfgrid = np.ones((2, HPC, self.nFreqs), dtype = np.float32)
        self.indev = self.find_device(input_keywords)
        self.tfgrid_ptr = 0
        self.check_pointer()
        if self.indev:
            self.stream = pyaudio.PyAudio().open(
                format = pyaudio.paInt16, channels=1, rate = SAMP_RATE, input = True, input_device_index = self.indev,
                frames_per_buffer = samples_per_hop, stream_callback=self._callback,)
            self.stream.start_stream()

    def find_device(self, device_str_contains):
        pya = pyaudio.PyAudio()
        for dev_idx in range(pya.get_device_count()):
            name = pya.get_device_info_by_index(dev_idx)['name']
            match = True
            for pattern in device_str_contains.replace(' ','').split(','):
                if (not pattern in name): match = False
            if(match):
                return dev_idx

    def check_pointer(self):
        ptr = int((time.time() % 15) * SYM_RATE * HPS)
        if np.abs(self.tfgrid_ptr - ptr) > 3:
            self.tfgrid_ptr = ptr

    def _callback(self, in_data, frame_count, time_info, status_flags):
        samples = np.frombuffer(in_data, dtype=np.int16).astype(np.float32)
        ns = len(samples)
        self.audio_buffer[:-ns] = self.audio_buffer[ns:]
        self.audio_buffer[-ns:] = samples
        self.tfgrid_ptr = (self.tfgrid_ptr + 1) % HPC

        np.multiply(self.audio_buffer[self.samples_per_half_hop:], self.fft_window, out=self.fft_in)
        z = np.fft.rfft(self.fft_in)[:self.nFreqs]
        self.tfgrid[0, self.tfgrid_ptr, :] = 20*np.log10(np.abs(z))

        np.multiply(self.audio_buffer[:-self.samples_per_half_hop], self.fft_window, out=self.fft_in)
        z = np.fft.rfft(self.fft_in)[:self.nFreqs]
        self.tfgrid[1, self.tfgrid_ptr, :] = 20*np.log10(np.abs(z))
        
        return (None, pyaudio.paContinue)

class Receiver:
    def __init__(self, max_freq = 3000, output_type = 'udp', latest_decode = 2,
                 ports = None, input_keywords = None):
        self.latest_decode = latest_decode
        self.input_keywords = input_keywords
        self.max_freq = max_freq
        self.output_type = output_type
        self.candidates = []
        self.duplicate_filter = []
        payload_symb_idxs = list(range(7, 36)) + list(range(43, 72))
        self.base_payload_hops = np.array([HPS * s for s in payload_symb_idxs])
        self.hop_idxs_Costas =  np.arange(7) * HPS
        self.base_freq_idxs = np.array([BPT * t for t in range(8)])
        csync = np.full((7, 8*BPT), -1/(8 * BPT - 1), np.float32)
        for sym_idx, tone in enumerate([3,1,4,0,6,5,2]):
            csync[sym_idx, tone * BPT] =  1
        self.csync_flat =  csync.ravel()
        self.waterfall_max = 0
        self.running = True
        if self.output_type == 'udp':   
            self.udp_comms = UdpComms(ports = ports, rx_callback = self.udp_received)
        self.audio_in = AudioIn(input_keywords, self.max_freq)
        threading.Thread(target = self.manage_cycle, daemon=True ).start()
        threading.Thread(target = self.send_waterfall_rows, daemon=True ).start()
        if self.audio_in.indev:
            self.send_output({'mtype':'info', 'info':'Receiver starting'})
            self.send_output({'mtype':'STATUS', 'from':'receiver', 'value':'OK'})
        else:
            info = f"[Receiver] Couldn't find input device matching '{self.input_keywords}'"
            self.send_output({'mtype':'info', 'info':info})
            self.running = False

    def send_output(self, msg_dict, noprint = False):
        if self.output_type == 'print':
            if not noprint:
                print(msg_dict)
            return
        self.udp_comms.udp_send_dict(msg_dict)

    def udp_received(self, msg_dict):
        if msg_dict['mtype'] == 'shutdown':
            self.running = False
        
    def manage_cycle(self):
        cycle_searched = False
        t_cyc, t_cyc_prev = 0, 0
        while self.running:
            time.sleep(0.1)
            t_cyc = time.time() % 15
            if t_cyc < t_cyc_prev:
                self.audio_in.check_pointer()
                cycle_searched = False
            if t_cyc > T_SEARCH and not cycle_searched:
                cycle_searched = True
                self.search_and_decode()
            t_cyc_prev = t_cyc
        self.udp_comms.udp_send_dict({'mtype':'info', 'info':'Receiver is shut down'})

    def send_waterfall_rows(self):
        while self.running:
            time.sleep(0.25)
            row = self.audio_in.tfgrid[0,self.audio_in.tfgrid_ptr,:]
            self.waterfall_max = np.max([np.max(row), 0.999 * self.waterfall_max])
            dBrng = 35
            row = (dBrng + np.clip(row - self.waterfall_max, -dBrng, 0)) / dBrng
            row = ','.join([f"{r:.2f}"[-2:] for i, r in enumerate(row) if i % 3 == 0])
            self.send_output({'mtype':'waterfall', 'data':row}, noprint = True)

    def search_and_decode(self):
        t0_cyc = 15 * int(time.time() / 15)
        cycle_start_str = time.strftime("%y%m%d_%H%M%S", time.gmtime(t0_cyc))
        info = f"{cycle_start_str} ========================================"
        self.send_output({'mtype':'rollover', 'info':info})
        self.candidates = self.search(t0_cyc, cycle_start_str)
        self.duplicate_filter = []
        info = f"Search finished at {time.time() % 15:6.1f} with {len(self.candidates)} candidates"
        self.send_output({'mtype':'test_info', 'info':info})
        info = self.decode()
        self.send_output({'mtype':'test_info', 'info':info})

    def search(self, t0_cyc, cycle_start_str):
        candidates = []
        for f0_idx in range(int(100 / 3.125), self.audio_in.nFreqs - 8 * BPT, 1):
            time.sleep(0)
            freq_idxs = f0_idx + self.base_freq_idxs
            p = self.audio_in.tfgrid[1, :, f0_idx:f0_idx+8*BPT]
            new_origin = {'score':0}
            for h0_idx in range(H0_RANGE[0], H0_RANGE[1]):
                vals = p[h0_idx + self.hop_idxs_Costas + 36 * HPS, :].ravel()
                sync_score = np.dot(vals, self.csync_flat) / np.max(vals)
                test_origin = {'h0_idx':h0_idx, 'score':sync_score}
                if test_origin['score'] > new_origin['score']:
                    new_origin = test_origin
            if new_origin['score'] > MIN_SCORE:
                freq_idxs = f0_idx + self.base_freq_idxs
                hops = [(new_origin['h0_idx'] + h) % HPC for h in self.base_payload_hops]
                p_idx = np.ix_(hops, freq_idxs)
                tsec = new_origin['h0_idx'] / (SYM_RATE * HPS)
                dt = tsec - 0.5
                fHz = 3.125 * f0_idx
                abs_t0 = t0_cyc + tsec
                new_origin.update({'f0_idx': f0_idx, 'cs':cycle_start_str, 'p_idx':p_idx, 'fHz': fHz, 'dt': dt, 'abs_t0':abs_t0, 
                                   'decode_info': None, 'decode_result':None, 'saved_llrs':[]})
                candidates.append(new_origin)
        candidates.sort(key = lambda c: -c['score'])
        candidates = candidates[:MAX_CANDS]
        candidates.sort(key = lambda c: int(c['h0_idx']))
        return candidates

    def decode(self):
        n_cands = len(self.candidates)
        self.last_attempt_stop = 0
        
        def stop_decoding():
            return self.latest_decode < time.time() % 15 < T_SEARCH

        def wait_for_signal(cand, last_sym = 57):
            t = time.time()
            arriving = t < cand['abs_t0'] + self.base_payload_hops[last_sym] / (SYM_RATE * HPS)
            overwritten = t > cand['abs_t0'] + 15 + 0.16*7
            return arriving and not overwritten and not stop_decoding() and self.running

        # good91 after message symbols arrive
        for c in self.candidates:
            if not stop_decoding():
                while wait_for_signal(c, last_sym = 31):
                    time.sleep(0.05)
                for itime in range(2):
                    p = self.audio_in.tfgrid[itime,:,:][c['p_idx']]
                    c['decode_result'], c['decode_info'] = decode_raw91(p, itime)
                    self.check_and_send(c)

        # ldpc, saving input and output llrs ONLY if score < 1.25 (limits OSD load to typically-useful range)
        for c in self.candidates:
            if not stop_decoding():
                if not c['decode_result']:
                    while wait_for_signal(c, last_sym = 57):
                        time.sleep(0.05)
                    for itime in range(2):
                        p = self.audio_in.tfgrid[itime,:,:][c['p_idx']]
                        c['decode_result'], c['decode_info'], llr_out, ch_llr = decode(p, itime)
                        if c['score'] < 1.25:
                            c['saved_llrs'].append((f"ch t={itime}", ch_llr))
                            if llr_out is not None:
                                c['saved_llrs'].append((f"op t={itime}", llr_out))
                        self.check_and_send(c)

        # osd on all saved llrs
        self.candidates.sort(key = lambda c: -c['score'])
        for c in self.candidates:
            if not stop_decoding():
                if not c['decode_result']:
                    for llr in c['saved_llrs']:
                        c['decode_result'], c['decode_info'] = osd(llr)
                        self.check_and_send(c)
                if not c['decode_result']:
                    c['decode_result'] = 'stop'

        n_remaining_with_saved_llrs = len([c for c in self.candidates if any(c['saved_llrs']) and not c['decode_result']])
        return (f"Last decode attempt {self.last_attempt_stop % 15:6.1f},"
                 + f" remaining_with_saved_llrs: {n_remaining_with_saved_llrs}")
     
    def check_and_send(self, c):
        self.last_attempt_stop = time.time()
        if c['decode_result']:
            if not c['decode_result'] in self.duplicate_filter:
                p = self.audio_in.tfgrid[0,:,:][c['p_idx']]
                c['decode_info'] = f" s={c['score']:5.2f} {c['decode_info']}"
                their_snr = np.clip(int(np.max(p)-np.min(p)) - 58, -24, 24)
                self.duplicate_filter.append(c['decode_result'])
                self.send_output({'mtype':'decode', 'cyclestart_string': c['cs'], 't_decode':time.time(),
                                  'fHz':f"{c['fHz']:7.2f}", 'dt':f"{c['dt']:+04.2f}", 'decode_info':c['decode_info'],
                                  'their_snr':f"{their_snr:+03d}", 'msg_tuple':c['decode_result']})
