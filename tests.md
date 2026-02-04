Investigate avg decodes per cycle and avg time per cycle 

Window, hops_persymb, bins_pertone, avg decodes, avg time

over wav files 1 to 28 inclusive

'MIN_LLR0_SD': 0.8,            # global minimum llr_sd
'LDPC_CONTROL': (35, 10),      # max ncheck0, max iterations
'OSD_CONTROL': (10, [30,20,5]) # max ncheck, L(order)

hanning 3 3 12.8 3.4
hanning 2 2 13.2, 2.0
hanning 2 3 11.1 2.8
hanning 3 2 13.8 2.5

hanning 4 2 14.0 3.0

hanning 5 2 14.0 3.4

kaiser15 3 3 14.0 3.3
kaiser20 3 3 14.0 3.3
kaiser30 3 3 13.7 3.4
kaiser20 2 2 13.1 2.0
kaiser6   2 2 13.1 2.0


'MIN_LLR0_SD': 0.5,            # global minimum llr_sd
'LDPC_CONTROL': (35, 10),      # max ncheck0, max iterations
'OSD_CONTROL': (10, [30,20,5]) # max ncheck, L(order)

hanning 4 2 14.2 3.0
