import time
import os
import ast

def wsjtx_tailer():
    cycle = ''
    def follow(path):
        with open(path, "r") as f:
            f.seek(0, 2)
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.2)
                    continue
                yield line.strip()

    for line in follow(r"C:\Users\drala\AppData\Local\WSJT-X\ALL.txt"):
        wsjtx_file = f"wsjtx.txt"
        with open(wsjtx_file, 'a') as f:
                f.write(f"{line}\n")
           
def wsjtx_compare():
    PyFT8_patterns, wsj_patterns = set(), set()
    matched_msgs, unmatched_msgs = [],[]
    wsjtx_file = "wsjtx.txt"
    PyFT8_file = "pyft8.txt"
        
    with open(wsjtx_file, 'r') as f:
        wsjt = f.readlines()
    for wsjtline in wsjt:
        l = wsjtline[48:]
        wsj_pattern = l.replace(' ','').replace('\n','')
        wsj_patterns.add(wsj_pattern)

    with open(PyFT8_file, 'r') as f:
        PyFT8lines = f.readlines()
    for PyFT8line in PyFT8lines:
        l = d = ast.literal_eval(PyFT8line)['msg']
        PyFT8_pattern = l.replace(' ','')
        if(PyFT8_pattern in wsj_patterns):
            matched_msgs.append(l)
        else:
            unmatched_msgs.append(l)
        PyFT8_patterns.add(PyFT8_pattern)

    matches = PyFT8_patterns.intersection(wsj_patterns)
    PyFT8_only = PyFT8_patterns.difference(wsj_patterns)
    PyFT8 = len(PyFT8_patterns)
    wsj = len(wsj_patterns)
    both = len(matches)
    PyFT8_only = len(PyFT8_only)
    pc = PyFT8/wsj if wsj>0 else 0
    print(f"wsjt: {wsj} PyFT8: {PyFT8} ({pc:.1%}) matched: {both} unmatched: {PyFT8_only}")

