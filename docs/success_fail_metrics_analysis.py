import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------


df = pd.read_csv('../success_fail_metrics.csv')
print(df)
df['decoded'] = df['decoded'].astype(int)
df['sync_score']   = df['sync_score'].astype(float)
df['llr_sd']  = df['llr_sd'].astype(float)
df['snr']     = df['snr'].astype(float)

decoded    = df['decoded'].values
sync_score      = df['sync_score'].values
llr_sd     = df['llr_sd'].values
snr        = df['snr'].values

# --------------------------------------------------
# SUCCESS vs Sycn sync_score and sd
# --------------------------------------------------
def success_vs_bins(values, decoded, nbins=25):
    bins = np.linspace(min(values), max(values), nbins)
    digitized = np.digitize(values, bins)
    success = []
    centres = []
    for i in range(1, len(bins)):
        in_bin = decoded[digitized == i]
        if len(in_bin) > 0:
            success.append(in_bin.mean())
            centres.append((bins[i] + bins[i-1]) / 2)
    return np.array(centres), np.array(success)

llr_x, llr_y = success_vs_bins(llr_sd, decoded)
sco_x, sco_y = success_vs_bins(sync_score, decoded)

plt.figure()
plt.plot(llr_x, llr_y, marker='o', label="llr_sd")
plt.plot(sco_x, sco_y, marker='o', label="sync sync_score")
plt.xlabel("Metric value")
plt.ylabel("Decode success rate")
plt.ylim(0, 1)
plt.grid(True)
plt.legend()
plt.show()

# --------------------------------------------------
# FUNNEL 
# --------------------------------------------------
def evaluate_thresholds(sync_thresh, sd_thresh):
    """Return funnel statistics for given thresholds."""
    passed_sync = df[df.sync_score > sync_thresh]
    passed_sd = passed_sync[passed_sync.llr_sd > sd_thresh]
    passed_ldpc = passed_sd.decoded.sum()  
    dec_success = passed_ldpc
    
    # Lost good early
    lost_at_sync = df[(df.sync_score <= sync_thresh) & (df.decoded == 1)].shape[0]
    lost_at_sd = passed_sync[
        (passed_sync.llr_sd <= sd_thresh) & (passed_sync.decoded == 1)
    ].shape[0]

    return {
        "survive_sync": len(passed_sync),
        "survive_sd": len(passed_sd),
        "decoded": dec_success,
        "lost_at_sync": lost_at_sync,
        "lost_at_sd": lost_at_sd
    }


# --------------------------------------------------
# PLOT LOST-GOOD-CANDIDATES vs THRESHOLDS
# --------------------------------------------------
sync_range = np.linspace(min(sync_score), max(sync_score), 40)
sd_range   = np.linspace(min(llr_sd), max(llr_sd), 40)

lost_sync_list = []
lost_sd_list = []
decode_list = []
sd_thresh = 1.5

for t in sync_range:
    res = evaluate_thresholds(sync_thresh=t, sd_thresh=sd_thresh)
    lost_sync_list.append(res["lost_at_sync"])
    lost_sd_list.append(res["lost_at_sd"])
    decode_list.append(res["decoded"])

plt.figure()
plt.plot(sync_range, lost_sync_list, label="good lost at sync thresh")
plt.plot(sync_range, lost_sd_list, label="good lost at sd thresh")
plt.plot(sync_range, decode_list, label="total decodes kept")
plt.xlabel("Sync sync_score threshold")
plt.ylabel("Count")
plt.title(f"Funnel vs sync thresh for sd thresh = {sd_thresh}")
plt.grid(True)
plt.legend()
plt.show()


# --------------------------------------------------
# 2D HEATMAP of DECODES vs (SYNC, SD)
# --------------------------------------------------
heat = np.zeros((len(sync_range), len(sd_range)))

for i, st in enumerate(sync_range):
    for j, sd in enumerate(sd_range):
        res = evaluate_thresholds(sync_thresh=st, sd_thresh=sd)
        heat[i, j] = res["decoded"]

plt.figure()
plt.imshow(
    heat,
    origin='lower',
    extent=[min(sd_range), max(sd_range), min(sync_range), max(sync_range)],
    aspect='auto'
)
plt.colorbar(label="Successful decodes")
plt.xlabel("SD threshold")
plt.ylabel("Sync score threshold")
plt.title("Decode heatmap vs thresholds")
plt.show()
