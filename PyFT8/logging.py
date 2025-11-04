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

"""
        <gridsquare:4>KN34
        <mode:3>FT8
        <rst_sent:3>-05
        <rst_rcvd:3>-12
        <qso_date:8>20210408
        <time_on:6>195415
        <qso_date_off:8>20210408
        <time_off:6>195515
        <band:3>30m
        <freq:9>10.137167
        <station_callsign:5>G1OJS
        <my_gridsquare:6>IO90JU
        <tx_pwr:2>25
        <comment:21>Indoor 2.5m RG213 STL
        <operator:5>G1OJS <eor>
"""

append_qso("test.adi",{
    'gridsquare':'KN34', 'mode':'FT8','operator':'G1OJS',
    'rst_sent':'-03', 'rst_rcvd':'-03',
    'qso_date':'20210408', 'time_on':'195415',
    'qso_date_off':'20210408', 'time_off':'195515',
    'band':'30m', 'freq':'10.137167',
    'station_callsign':'G1OJS', 'my_gridsquare':'IO90JU'})
