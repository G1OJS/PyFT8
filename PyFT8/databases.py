from PyFT8.pskreporter import PSKR_MQTT_listener
import threading, time, os, pickle

call_hashes = {}
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
        hashes.append(x)
        call_hashes[(x, m)] = call
    return hashes

def grid_to_latlong(grid, centre = True):
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
        
def grids_to_dist_brg(sq1, sq2, units):
    from numpy import sin, cos, asin, atan2, sqrt, radians, degrees
    ll1, ll2 = grid_to_latlong(sq1), grid_to_latlong(sq2)
    lats = [radians(ll1[0]), radians(ll2[0])]
    dlat, dlon = radians(ll2[0] - ll1[0]), radians(ll2[1] - ll1[1])
    s_lats, c_lats = sin(lats), cos(lats)
    a = sin(dlat/2)**2 + c_lats[0] * c_lats[1] * sin(dlon/2)**2
    r = 6371 * 2 * asin(sqrt(a))
    b = atan2(c_lats[1] * sin(dlon), c_lats[0] * s_lats[1] - s_lats[0] * c_lats[1] * cos(dlon))
    b *= (1.0 if 'km' in units else 0.621371)
    return (r, degrees(b) % 360)

class DiskDict:
    def __init__(self, file):
        self.lock = threading.Lock()
        self.file = file
        self.data = {}
        self.load()
        threading.Thread(target = self._autosave, daemon = True).start()

    def _autosave(self, autosave_period = 15):
        while True:
            time.sleep(autosave_period)
            self.save()

    def load(self):
        with self.lock:        
            if(os.path.exists(self.file)):
                with open(f"{self.file}","rb") as f:
                    self.data = pickle.load(f)

    def save(self):
        with self.lock:
            tmp_file = f"{self.file}.tmp"
            with open(tmp_file, "wb") as f:
                pickle.dump(self.data, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_file, self.file)

class History:
    def __init__(self, config_folder, my_call, home_square, pskr_refresh_mins):
        self.pskr_refresh_mins = pskr_refresh_mins
        self.config_folder = config_folder
        self.my_call = my_call
        self.home_square = home_square
        self.home_square_lev4 = home_square[:4]
        self.dist_brg_cache = {}
        self.hearing_me = DiskDict(f"{self.config_folder}/hearing_me.pkl")   # all-time record of hearing me
        self.heard_by_me = DiskDict(f"{self.config_folder}/heard_by_me.pkl") # all-time record of heard by me
        self.hearing_me_new = {}
        self.heard_by_me_new = {}
        self.call_to_grid = DiskDict(f"{self.config_folder}/call_to_grid.pkl") # all time cache call -> fine locator
        self.band_TxRx_homecall_report_times = DiskDict(f"{self.config_folder}/report_times.pkl") # last 20 mins data -> per band tx/rx & current band detail
        self.home_activity = {}
        self.home_most_remotes = {}
        self.lock = threading.Lock()
        #self.load_all_file(f"{config_folder}/ALL.txt")
        mqtt = PSKR_MQTT_listener(self.home_square_lev4, self.add_mqtt_spot)
        threading.Thread(target = self.count_activity, daemon = True).start()

    def band_from_MHz(self, fMHz): # rewrite this to use the band button defs from ini file
        f = int(fMHz)
        freqs = [1,3,5,7,10,14,18,21,24,28,50,144,433]
        idx = freqs.index(f) if f in freqs else -1
        if idx > -1:
            return ['160m','80m','60m','30m','20m','17m','15m','12m','10m','6m','2m','70cm'][idx]

    def load_all_file(self, all_file):
        recs = self.parse_all_txt(all_file)
        if not any(recs): return
        for r in recs:
            if r['md'] == 'FT8':
                band = self.band_from_MHz(r['fMHz'])
                if band is not None:
                    call = r['call_b'] if r['TxRx'] == 'Rx' else r['call_a']
                    data = self.heard_by_me.data if r['TxRx'] == 'Rx' else self.hearing_me.data
                    self.add_myspots_record(data, None, band, call, 0, 0)

    def parse_all_txt(self, all_file):
        rows, recs = None, []
        if os.path.exists(all_file):
            with open(all_file, 'r') as f:
                rows = f.readlines()
        if rows is not None:
            for r in rows:
                fields = r.strip().split()
                if len(fields) > 8:
                    recs.append({'fMHz':float(fields[1]), 'TxRx':fields[2], 'md':fields[3], 'call_a':fields[7], 'call_b':fields[8]} )
        return recs

    def write_all_txt_row(self, cyclestart_string, fMHz, TxRx, mode, snr, dt, fHz, msg):
        all_file = f"{self.config_folder}/ALL.txt"
        filemode = 'w' if not os.path.exists(all_file) else 'a'
        row = f"{cyclestart_string} {fMHz:8.3f} {TxRx} {mode} {snr:+03d} {dt:4.1f} {fHz:4.0f} {msg}"
        with open(all_file, filemode) as f:
            f.write(f"{row}\n")

    def add_mqtt_spot(self, d):
        tnow = int(time.time())
        sc, rc = (d['sc'], d['sl']), (d['rc'], d['rl'])
        for iTxRx, call_grid in enumerate([sc, rc]):
            call, grid = call_grid
            self.store_best_grid(call, grid)
            if self.home_square_lev4 in grid:
                self.add_homespots_record((d['b'], iTxRx, call), tnow)
        if d['sc'] == self.my_call:
            self.add_myspots_record(self.hearing_me.data, self.hearing_me_new, d['b'], d['rc'], tnow, d['rp'])
        if d['rc'] == self.my_call:
            self.add_myspots_record(self.heard_by_me.data, self.heard_by_me_new, d['b'], d['sc'], tnow, d['rp'])

    def store_best_grid(self, call, grid):
        if call.startswith('<'): return
        existing_grid = self.call_to_grid.data.get(call, '')
        if len(grid) > len(existing_grid):
            self.call_to_grid.data[call] = grid
        
    def add_homespots_record(self, key, t):
        self.band_TxRx_homecall_report_times.data.setdefault(key, [])
        self.band_TxRx_homecall_report_times.data[key].append(int(t))

    def add_myspots_record(self, historic_data, new_alert_data, band, call, t, rp):
        self._update_new_alert(band, call, historic_data, new_alert_data)
        historic_data.setdefault(band, {})
        if call in historic_data[band]:
            if t < historic_data[band][call]['t']:
                return
        historic_data[band][call] = {'t': int(t),'rp':int(rp)}

    def _update_new_alert(self, band, call, historic_data, new_alert_data):
        if new_alert_data is None:
            return
        new = band not in historic_data
        if not new:
            new = call not in historic_data[band]
        if new:
            new_alert_data.setdefault(band, [])
            new_alert_data[band].append(call)

    def is_in_new_alert(self, band, call, new_alert_data):
        result = False
        if band in new_alert_data:
            result = call in new_alert_data[band]
        return result

    def is_hearing_me(self, band, call, since_seconds):
        result = False
        if band in self.hearing_me.data:
            if call in self.hearing_me.data[band]:
                result = int(self.hearing_me.data[band][call]['t']) > since_seconds
        return result        
      
    def count_activity(self):
        import numpy as np
        while True:
            time.sleep(5)
            self.home_activity = {}
            self.home_most_remotes = {}
            with self.lock:
                # clear counters for each band
                for b in self.home_activity:
                    self.home_activity[b] = [0, 0]
                for b in self.home_most_remotes:
                    self.home_most_remotes[b] = [('',0), ('',0)]

                # keep only the remote spots that happened in the self.pskr_refresh_mins window
                for band_TxRx_homecall in self.band_TxRx_homecall_report_times.data:
                    band_TxRx_homecall_report_times = self.band_TxRx_homecall_report_times.data[band_TxRx_homecall]
                    band_TxRx_homecall_report_times = [t for t in band_TxRx_homecall_report_times if (time.time() - t) < 60*self.pskr_refresh_mins]
                    self.band_TxRx_homecall_report_times.data[band_TxRx_homecall] = band_TxRx_homecall_report_times

                # count number of local Tx and Rx, and identify the local Tx and Rx with most remote spots
                for band_TxRx_homecall in self.band_TxRx_homecall_report_times.data:
                    band_TxRx_homecall_report_times = self.band_TxRx_homecall_report_times.data[band_TxRx_homecall]
                    if len(band_TxRx_homecall_report_times):
                        b, iTxRx, c = band_TxRx_homecall
                        self.home_activity.setdefault(b, [0, 0])
                        self.home_activity[b][iTxRx] +=1
                        self.home_most_remotes.setdefault(b, [('',0), ('',0)])
                        nremotes = len(band_TxRx_homecall_report_times)
                        current_winner = self.home_most_remotes[b][iTxRx]
                        if nremotes > current_winner[1]:
                            if c != self.my_call:
                                self.home_most_remotes[b][iTxRx] = (c, nremotes)

    def get_spot_counts(self, band, call):
        tx_reports = self.band_TxRx_homecall_report_times.data.get((band, 0, call), [])
        rx_reports = self.band_TxRx_homecall_report_times.data.get((band, 1, call), [])
        n_spotting = len(tx_reports) if tx_reports else 0
        n_spotted = len(rx_reports) if rx_reports else 0
        return n_spotted, n_spotting

    def get_dist_brg(self, grid, units):
        self.dist_brg_cache.setdefault(grid, grids_to_dist_brg(self.home_square, grid, units))
        return self.dist_brg_cache[grid]

    def get_geo_text(self, call, units):
        geo_text = ''
        grid = self.call_to_grid.data.get(call, False)
        if grid:
            loc = grid if units == 'grid' else self.get_dist_brg(grid, units)
            units_str = '' if units == 'grid' else ('km' if 'km' in units else 'mi')
            geo_text = f"{int(loc[0]):5d}{units_str} {int(loc[1]):3d}°"
        return geo_text
                
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
              
    def log(self, times, band_info, mStation, oStation, rpts):
        log_dict = {'call':oStation['c'], 'gridsquare':oStation['g'], 'mode':'FT8',
        'operator':mStation['c'], 'station_callsign':mStation['c'], 'my_gridsquare':mStation['g'], 
        'rst_sent':rpts['sent'], 'rst_rcvd':rpts['rcvd'], 
        'qso_date':time.strftime("%Y%m%d", times['time_on']), 'qso_date_off':time.strftime("%Y%m%d", times['time_off']),
        'time_on':time.strftime("%H%M%S", times['time_on']), 'time_off':time.strftime("%H%M%S", times['time_on']),
        'band':band_info['b'], 'freq':band_info['fMHz']}
        with open(self.adif_log_file,'a') as f:
            for k, v in log_dict.items():
                v = str(v)
                f.write(f"<{k}:{len(v)}>{v} ")
            f.write(f"<eor>\n")
        cbm = log_dict['call'] + "_" + log_dict['band'] + "_FT8"
        tm = time.time()
        self.cache[log_dict['call']] = tm
        self.cache[cbm] = tm

    def _build_cache(self):
        import calendar
        def parse(rec, field):
            p = rec.find(field)
            if p > 0:
                p1, p2 = rec.find(':',p), rec.find('>',p)
                n = int(rec[p1+1:p2])
                return rec[p2+1: p2+1+n]
        cache = {}
        with open(self.adif_log_file, 'r') as f:
            for l in f.readlines():
                if parse(l, 'mode') == "FT8":
                    c, b, d, t = parse(l, 'call'), parse(l, 'band'), parse(l, 'qso_date'), parse(l, 'time_on')
                    time_tuple = time.strptime(d+t, "%Y%m%d%H%M%S")
                    tm = calendar.timegm(time_tuple)
                    cache[c] = tm
                    cache[c + "_"+b+"_FT8"] = tm
        return cache
