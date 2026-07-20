import threading, os, pickle, json
from PyFT8.pskreporter import PSKR_MQTT_listener
from PyFT8.time_utils import time_utils


# call hash calculator for receiver ==============================================================

call_hashes, hashes_for_calls = {}, {}

def add_call_hashes(call):
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
        hashes.append((x, m))
        call_hashes[(x, m)] = call
    hashes_for_calls[call] = hashes


# Disk-synced dictionary class for History ======================================================

class DiskDict:
    def __init__(self, file, autosave_t0):
        self.lock = threading.Lock()
        self.file = file
        self.data = {}
        self.load()
        threading.Thread(target = self._autosave, args=(autosave_t0,),  daemon = True).start()

    def _autosave(self, autosave_t0, autosave_period = 15):
        time_utils.sleep(autosave_t0)
        while True:
            time_utils.sleep(autosave_period)
            self.save()

    def load(self):
        with self.lock:        
            if(os.path.exists(self.file)):
                with open(f"{self.file}","rb") as f:
                    try:
                        self.data = json.load(f)
                    except:
                        pass

    def save(self):
        if self.data != {}:
            with self.lock:
                with open(f"{self.file}_tmp", "w") as f:
                    try:
                        json.dump(self.data, f)
                    except:
                        return
            try:
                os.replace(f"{self.file}_tmp", self.file)
            except:
                return

# History class ==============================================================================================

class History:
    def __init__(self, config_folder, my_call, home_square = '', geo_units = 'km', pskr_refresh_mins = 20):
        self.pskr_refresh_mins = pskr_refresh_mins
        self.geo_units = geo_units
        self.log_cache = None
        self.my_call = my_call
        self.home_square = home_square
        self.home_square_lev4 = home_square[:4]
        self.freqs_to_bands = {}
        self.dist_brg_cache = {}
        self.hearing_me_new = {}
        self.heard_by_me_new = {}
        self.home_activity = {}
        self.home_most_remotes = {}
        self.lock = threading.Lock()
        self.all_file = f"{config_folder}/ALL.txt"
        self.hearing_me = DiskDict(f"{config_folder}/hearing_me.json", 3)       # all-time record of hearing me
        self.heard_by_me = DiskDict(f"{config_folder}/heard_by_me.json", 5)     # all-time record of heard by me
        self.call_to_grid = DiskDict(f"{config_folder}/call_to_grid.json", 7)   # all time cache call -> fine locator
        self.band_TxRx_homecall_recent_L4grid = DiskDict(f"{config_folder}/recent_l4grid.json", 9) # last 20 mins data -> per band tx/rx & current band detail

    
    # external query-type functions --------------------------------------------------------

    def is_in_new_alert(self, band, call, new_alert_data):
        result = False
        if band in new_alert_data:
            result = call in new_alert_data[band]
        return result

    def is_hearing_me(self, band, call, in_last_n_minutes):
        result = False
        if band in self.hearing_me.data:
            if call in self.hearing_me.data[band]:
                result = int(self.hearing_me.data[band][call]['t']) > (time_utils.time() - 60*in_last_n_minutes)
        return result        
      
    def get_spot_counts(self, band, call):
        tx_reports = self.band_TxRx_homecall_recent_L4grid.data.get(f"{band}_0_{call}", [])
        rx_reports = self.band_TxRx_homecall_recent_L4grid.data.get(f"{band}_1_{call}", [])
        n_spotting = len(tx_reports) if tx_reports else 0
        n_spotted = len(rx_reports) if rx_reports else 0
        return n_spotted, n_spotting

    def get_geo_text(self, call):
        geo_text = ''
        grid = self.call_to_grid.data.get(call, False)
        if grid:
            loc = grid if self.geo_units == 'grid' else self._get_dist_brg(grid, self.geo_units)
            units_str = '' if self.geo_units == 'grid' else ('km' if 'km' in self.geo_units else 'mi')
            geo_text = f"{int(loc[0]):5d}{units_str} {int(loc[1]):3d}°"
        return geo_text

    def get_worked_before_info(self, their_call, current_band):
        wb_time = self.log_cache.get(their_call,'') 
        return f"wb: {time_utils.format_duration(time_utils.time() - float(wb_time))}" if wb_time else ''

    # external storage-like functions -------------------------------------------------------------------

    def start_collect_new(self):
        mqtt = PSKR_MQTT_listener(self.home_square_lev4, self._add_mqtt_spot)
        threading.Thread(target = self._count_activity, daemon = True).start()

    def incorporate_log_data(self, log_cache):
        self.log_cache = log_cache
        for key in log_cache:
            key_parts = key.split('_')
            if len(key_parts) > 1:
                c, b, m = key_parts
                if m == 'FT8':
                    #print(f"Parsing adif log: Add hearing & heard by {c} on {b}")
                    self._add_myspots_record(self.hearing_me.data, None, b, c, 0, 0)
                    self._add_myspots_record(self.heard_by_me.data, None, b, c, 0, 0)
                else:
                    print(m)

    def load_hearing_heard_from_all_file(self, bands):
        recs = self._parse_all_txt()
        if not any(recs):
            return
        for b in bands:
            f = float(bands[b])
            self.freqs_to_bands[round(f,1)] = b
        for r in recs:
            if r['md'] == 'FT8':
                band = self.freqs_to_bands.get(round(r['fMHz'], 1), None)
                if band is not None:
                    TxRx = 'Tx' if (r['TxRx'] == 'Tx' or r['call_b'] == self.my_call) else 'Rx'
                    call = r['call_b'] if TxRx == 'Rx' else r['call_a']
                    if len(call) > 3:
                        data = self.heard_by_me.data if TxRx == 'Rx' else self.hearing_me.data
                        self._add_myspots_record(data, None, band, call, 0, 0)

    def process_message(self, message, band_info, myCall):
        m = message
        self._write_all_txt_row(m['cyclestart_string'], float(band_info['fMHz']), 'Rx', 'FT8',
                                m['their_snr'], m['dt'], m['fHz'], m['hail'], m['their_call'], m['grid_rpt'])
        self._add_myspots_record(self.heard_by_me.data, self.heard_by_me_new,
                                band_info['current_band'], m['their_call'], int(time_utils.time()), m['their_snr'])
        if m['hail'] == myCall: # They're calling me, so they're hearing me
            rpt = m['grid_rpt'][-3:]
            if rpt.isnumeric():
                self._add_myspots_record(self.hearing_me.data, self.hearing_me_new,
                                       band_info['current_band'], m['their_call'], int(time_utils.time()), int(rpt))


    # ----- internal storing / writing functions ----------------------------------------------------------

    def _write_all_txt_row(self, cyclestart_string, fMHz, TxRx, mode, snr_str, dt, fHz, hail, their_call, grid_rpt):
        filemode = 'w' if not os.path.exists(self.all_file) else 'a'
        row = f"{cyclestart_string} {fMHz:8.3f} {TxRx} {mode} {snr_str} {dt:4.1f} {fHz:4.0f} {hail} {their_call} {grid_rpt}"
        with open(self.all_file, filemode) as f:
            f.write(f"{row}\n")

    def _add_mqtt_spot(self, d):
        tnow = int(time_utils.time())
        sc, rc = (d['sc'], d['sl']), (d['rc'], d['rl'])
        for iTxRx, call_grid in enumerate([sc, rc]):
            call, grid = call_grid
            self._store_best_grid(call, grid)
            if self.home_square_lev4 in grid:
                self._add_homespots_record(f"{d['b']}_{iTxRx}_{call}", tnow)
        if d['sc'] == self.my_call:
            self._add_myspots_record(self.hearing_me.data, self.hearing_me_new, d['b'], d['rc'], tnow, d['rp'])
        if d['rc'] == self.my_call:
            self._add_myspots_record(self.heard_by_me.data, self.heard_by_me_new, d['b'], d['sc'], tnow, d['rp'])

    def _add_homespots_record(self, key, t):
        self.band_TxRx_homecall_recent_L4grid.data.setdefault(key, [])
        self.band_TxRx_homecall_recent_L4grid.data[key].append(int(t))

    def _store_best_grid(self, call, grid):
        if call.startswith('<'): return
        existing_grid = self.call_to_grid.data.get(call, '')
        if len(grid) > len(existing_grid):
            self.call_to_grid.data[call] = grid

    def _parse_all_txt(self):
        rows, recs = None, []
        if os.path.exists(self.all_file):
            with open(self.all_file, 'r') as f:
                rows = f.readlines()
        if rows is not None:
            for r in rows:
                fields = r.strip().split()
                if len(fields) > 8:
                    call_a_pos = 7 if fields[7] != '~' else 8
                    recs.append({'fMHz':float(fields[1]), 'TxRx':fields[2], 'md':fields[3],
                                 'call_a':fields[call_a_pos], 'call_b':fields[call_a_pos + 1]} )
        if not any(recs):
            print("Didn't find any records in an ALL.txt file in the config folder")
        return recs
    
    def _add_myspots_record(self, historic_data, new_alert_data, band, call, t, rp):
        self._update_new_alert_data(band, call, historic_data, new_alert_data)
        historic_data.setdefault(band, {})
        if call in historic_data[band]:
            if int(t) < int(historic_data[band][call]['t']):
                return
        historic_data[band][call] = {'t': int(t),'rp':int(rp)}

    def _update_new_alert_data(self, band, call, historic_data, new_alert_data):
        if new_alert_data is None:
            return
        new = band not in historic_data
        if not new:
            new = call not in historic_data[band]
        if new:
            new_alert_data.setdefault(band, [])
            new_alert_data[band].append(call)

    def _get_dist_brg(self, grid, units):
        self.dist_brg_cache.setdefault(grid, _grids_to_dist_brg(self.home_square, grid, units))
        return self.dist_brg_cache[grid]


    # ---- Internal analysis functions -------------------------------------------------------------

    def _count_activity(self):
        import numpy as np
        while True:
            time_utils.sleep(5)
            self.home_activity = {}
            self.home_most_remotes = {}
            with self.lock:
                # clear counters for each band
                for b in self.home_activity:
                    self.home_activity[b] = [0, 0]
                for b in self.home_most_remotes:
                    self.home_most_remotes[b] = [('Nobody',0), ('Nobody',0)]

                # keep only the remote spots that happened in the self.pskr_refresh_mins window
                for band_TxRx_homecall in self.band_TxRx_homecall_recent_L4grid.data:
                    band_TxRx_homecall_recent_L4grid = self.band_TxRx_homecall_recent_L4grid.data[band_TxRx_homecall]
                    band_TxRx_homecall_recent_L4grid = [t for t in band_TxRx_homecall_recent_L4grid if (time_utils.time() - t) < 60*self.pskr_refresh_mins]
                    self.band_TxRx_homecall_recent_L4grid.data[band_TxRx_homecall] = band_TxRx_homecall_recent_L4grid

                # count number of local Tx and Rx, and identify the local Tx and Rx with most remote spots
                for band_TxRx_homecall in self.band_TxRx_homecall_recent_L4grid.data:
                    band_TxRx_homecall_recent_L4grid = self.band_TxRx_homecall_recent_L4grid.data[band_TxRx_homecall]
                    if len(band_TxRx_homecall_recent_L4grid):
                        b, iTxRx, c = band_TxRx_homecall.split('_')
                        iTxRx = int(iTxRx)
                        self.home_activity.setdefault(b, [0, 0])
                        self.home_activity[b][iTxRx] +=1
                        self.home_most_remotes.setdefault(b, [('Nobody',0), ('Nobody',0)])
                        nremotes = len(band_TxRx_homecall_recent_L4grid)
                        current_winner = self.home_most_remotes[b][iTxRx]
                        if nremotes > current_winner[1]:
                            if c != self.my_call:
                                self.home_most_remotes[b][iTxRx] = (c, nremotes)
                                
# Geo Helpers =================================================================

def _grids_to_dist_brg(sq1, sq2, units):
    from numpy import sin, cos, asin, atan2, sqrt, radians, degrees
    ll1, ll2 = _grid_to_latlong(sq1), _grid_to_latlong(sq2)
    lats = [radians(ll1[0]), radians(ll2[0])]
    dlat, dlon = radians(ll2[0] - ll1[0]), radians(ll2[1] - ll1[1])
    s_lats, c_lats = sin(lats), cos(lats)
    a = sin(dlat/2)**2 + c_lats[0] * c_lats[1] * sin(dlon/2)**2
    r = 6371 * 2 * asin(sqrt(a))
    b = atan2(c_lats[1] * sin(dlon), c_lats[0] * s_lats[1] - s_lats[0] * c_lats[1] * cos(dlon))
    b *= (1.0 if 'km' in units else 0.621371)
    return (r, degrees(b) % 360)  


def _grid_to_latlong(grid, centre = True):
    lat, lon = -90, -180
    grid = grid.upper()
    if centre:
        grid = grid + "LL44LL44LL44"[len(grid):]
    mults = [20, 2, 2/24, 0.2/24, 0.2/(24*24), 0.02/(24*24)]
    grid = grid[:2*len(mults)]
    pairs = [grid[i:i+2] for i in range(0,len(grid),2)]
    for i, p in enumerate(pairs):
        zero = [ord('A'),ord('0')][i % 2]
        lon += mults[i] * (ord(p[0]) - zero)
        lat += mults[i] * (ord(p[1]) - zero) / 2
    return (lat, lon)
        

# ==================ADIF LOGGING=========================================================================
                
def ensure_file_exists(path, header = None):
    try:
        with open(path, "x") as f:
            if header is not None:
                f.write(header)
    except FileExistsError:
        pass
      
class ADIF:
    def __init__(self, logfile):
        self.adif_log_file = logfile
        ensure_file_exists(self.adif_log_file, header = "header <eoh>\n")
        self.cache = self._build_cache()
              
    def log(self, log_dict):
        with open(self.adif_log_file,'a') as f:
            for k, v in log_dict.items():
                v = str(v)
                f.write(f"<{k}:{len(v)}>{v} ")
            f.write(f"<eor>\n")
        cbm = log_dict['call'] + "_" + log_dict['band'] + "_FT8"
        tm = time_utils.time()
        self.cache[log_dict['call']] = tm
        self.cache[cbm] = tm

    def _build_cache(self):
        import calendar, time
        def parse(rec, field):
            p = rec.find(field)
            if p<0:
                p = rec.find(field.upper())
            if p<0:
                p = rec.find(field.lower())
            if p > 0:
                p1, p2 = rec.find(':',p), rec.find('>',p)
                n = int(rec[p1+1:p2])
                return rec[p2+1: p2+1+n]
        cache = {}
        with open(self.adif_log_file, 'r') as f:
            for l in f.readlines():
                if parse(l, 'mode') == "FT8":
                    c, b, d, t = parse(l, 'call:'), parse(l, 'band'), parse(l, 'qso_date'), parse(l, 'time_on')
                    if c and b and d and t:
                        time_tuple = time.strptime(d+t, "%Y%m%d%H%M%S")
                        tm = calendar.timegm(time_tuple)
                        cache[c] = tm
                        cache[c + "_"+b+"_FT8"] = tm
        return cache
