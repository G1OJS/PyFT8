import time

def parse_adif(rec, field):
    p = rec.find(field)
    if p > 0:
        p1, p2 = rec.find(':',p), rec.find('>',p)
        n = int(rec[p1+1:p2])
        return rec[p2+1: p2+1+n]

class ADIFLogger:
    def __init__(self, logfile):
        self.adif_log_file = logfile
        self._write_header_if_new(self.adif_log_file, header = "header <eoh>\n")

    def _write_header_if_new(self, path, header = None):
        try:
            with open(path, "x") as f:
                if header is not None:
                    f.write(header)
        except FileExistsError:
            pass
        
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


