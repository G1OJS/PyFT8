import pickle
def flat_list(worked_before_file = 'C:/Users/drala/Documents/Projects/GitHub/G1OJS/PyFT8_cfg/PyFT8_wb.pkl'):
    with open(f"{worked_before_file}","rb") as f:
        worked_before = pickle.load(f)
    worked_before['dummy']=0
    wb = sorted(worked_before.items(), key=lambda x: x[1])
    for c in wb:
        print(c)

flat_list()
