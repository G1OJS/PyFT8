import os

def create_adif(logfile):
    with open(logfile, 'w') as f:
        f.write("<ADIF_VER:5>3.0.8\n<PROGRAMID:5>PyFT8\n<EOH>")

def append_qso(logfile, qso_dict):
    if(not os.path.exists(logfile)):
        create_adif(logfile)
    with open(logfile,'a') as f:
        f.write(f"\n")
        for k,v in qso_dict.items():
            f.write(f"<{k}:{len(v)}>{v} ")
        f.write(f"<eor>\n")

append_qso("test.adi",{
    'gridsquare':'KN34', 'mode':'FT8','operator':'G1OJS',
    'rst_sent':'-03', 'rst_rcvd':'-03',
    'qso_date':'20210408', 'time_on':'195415',
    'qso_date_off':'20210408', 'time_off':'195515',
    'band':'30m', 'freq':'10.137167',
    'station_callsign':'G1OJS', 'my_gridsquare':'IO90JU'})
