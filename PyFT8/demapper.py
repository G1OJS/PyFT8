import numpy as np

def get_llr(pgrid_main, h0_idx, hps, freq_idxs, payload_symb_idxs, target_params = (3.3, 3.7)):
    hops = np.array([h0_idx + hps* s for s in payload_symb_idxs])
    praw = pgrid_main[np.ix_(hops, freq_idxs)]
    pclip = np.clip(praw, np.max(praw)/1e8, None)
    pgrid = np.log10(pclip)
    llra = np.max(pgrid[:, [4,5,6,7]], axis=1) - np.max(pgrid[:, [0,1,2,3]], axis=1)
    llrb = np.max(pgrid[:, [2,3,4,7]], axis=1) - np.max(pgrid[:, [0,1,5,6]], axis=1)
    llrc = np.max(pgrid[:, [1,2,6,7]], axis=1) - np.max(pgrid[:, [0,3,4,5]], axis=1)
    llr0 = np.column_stack((llra, llrb, llrc))
    llr0 = llr0.ravel()
    llr0_sd = np.std(llr0)
    snr = int(np.clip(10*np.max(pgrid) - 107, -24, 24))
    if (llr0_sd > 0.001):
        llr0 = target_params[0] * llr0 / llr0_sd
        llr0 = np.clip(llr0, -target_params[1], target_params[1])
        llr0_quality = np.sum(np.abs(llr0))
    return (llr0, llr0_sd, llr0_quality, pgrid, snr)

