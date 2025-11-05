import os

def create_adif(logfile):
    with open(logfile, 'w') as f:
        f.write("header <eoh>")

def append_qso(logfile, qso_dict):
    if(not os.path.exists(logfile)):
        create_adif(logfile)
    with open(logfile,'a') as f:
        f.write(f"\n")
        for k,v in qso_dict.items():
            v = str(v)
            if(v):
                f.write(f"<{k}:{len(v)}>{v} ")
        f.write(f"<eor>\n")


