import numpy as np

def get_llr(pgrid_main, h0_idx, hps, freq_idxs, payload_symb_idxs, target_params = (3.3, 3.7)):
    hops = np.array([h0_idx + hps* s for s in payload_symb_idxs])
    praw = pgrid_main[np.ix_(hops, freq_idxs)]
    pclip = np.clip(praw, np.max(praw)/1e8, None)
    pgrid = np.log10(pclip)
    llra = np.max(pgrid[:, [4,5,6,7]], axis=1) - np.max(pgrid[:, [0,1,2,3]], axis=1)
    llrb = np.max(pgrid[:, [2,3,4,7]], axis=1) - np.max(pgrid[:, [0,1,5,6]], axis=1)
    llrc = np.max(pgrid[:, [1,2,6,7]], axis=1) - np.max(pgrid[:, [0,3,4,5]], axis=1)
    llr = np.column_stack((llra, llrb, llrc))
    snr = int(np.clip(10*np.max(pgrid) - 107, -24, 24))
    llr = llr.ravel()
    s, llr_quality = np.std(llr), 0
    if (s > 0.1):
        llr = target_params[0] * llr / s 
        llr = np.clip(llr, -target_params[1], target_params[1])
        llr_quality = np.sum(np.sign(llr) * llr)
    return (llr, llr_quality, pgrid, snr)

