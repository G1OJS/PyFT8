import json
def get_rxFreqMessages(from_call = None):
    with open("rxFreq_data.json", "r") as f:
        s = f.readline()
        if(s):
            if(not from_call): return eval(s)[0]['grid_rpt']
            decode = next((item for item in eval(s) if item["call_b"] == from_call), None)
            if(decode): return decode['grid_rpt']   


print(get_rxFreqMessage(from_call= 'UW8SM'))
