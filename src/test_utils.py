import time

def wsjtx_tailer():
    wsjtx_lines = []
    wsjtx_prevlines=[]
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
        if(cycle != line[7:13]):
            cycle = line[7:13]
            with open('last wsjtx output.txt', 'w') as f:
                for l in wsjtx_prevlines:
                    f.write(f"{l}\n")
            wsjtx_prevlines = wsjtx_lines
            wsjtx_lines=[]
        wsjtx_lines.append(line)

def wsjtx_compare(lines):
    loc_patterns, wsj_patterns = set(), set()
    
    for myline in lines:
        loc_patterns.add(myline['msg'].replace(' ',''))
        
    with open('last wsjtx output.txt', 'r') as f:
        wsjt = f.readlines()
    for wsjtline in wsjt:
        l = wsjtline[48:]
        wsj_pattern = l.replace(' ','').replace('\n','')
        wsj_patterns.add(wsj_pattern)
        if(wsj_pattern in loc_patterns):
            l += " ***"
     #   print(l.replace('\n',''))

    matches = loc_patterns.intersection(wsj_patterns)
    loc_only = loc_patterns.difference(wsj_patterns)
    A = len(loc_patterns)
    B = len(wsj_patterns)
    AB = len(matches)
    AnotB = len(loc_only)
    pc = AB/B if B>0 else 0
    print(f"wsjt:{A} matched: {AB} ({pc:.1%}) unmatched: {B}")
