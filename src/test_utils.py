import time

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
        if(cycle != line[7:13]):
            cycle = line[7:13]
            with open('last wsjtx output.txt', 'w') as f:
                f.write(f"{line}\n")
        else:
            with open('last wsjtx output.txt', 'a') as f:
                f.write(f"{line}\n")            


def wsjtx_compare(lines):
    loc_patterns, wsj_patterns = set(), set()
    matched_msgs, unmatched_msgs = [],[]
    with open('last wsjtx output.txt', 'r') as f:
        wsjt = f.readlines()
    for wsjtline in wsjt:
        l = wsjtline[48:]
        wsj_pattern = l.replace(' ','').replace('\n','')
        wsj_patterns.add(wsj_pattern)
    for myline in lines:
        l = myline['msg']
        loc_pattern = l.replace(' ','')
        if(loc_pattern in wsj_patterns):
            matched_msgs.append(l)
        else:
            unmatched_msgs.append(l)
        loc_patterns.add(loc_pattern)

    print("wsjt-x:")
    for l in wsjt:
        print(l.replace('\n',''))
    print("Matched with wsjt-x:")
    for l in matched_msgs:
        print(l)
    print("Not matched with wsjt-x:")
    for l in unmatched_msgs:
        print(l)

    matches = loc_patterns.intersection(wsj_patterns)
    loc_only = loc_patterns.difference(wsj_patterns)
    loc = len(loc_patterns)
    wsj = len(wsj_patterns)
    both = len(matches)
    loc_only = len(loc_only)
    pc = loc/wsj if wsj>0 else 0
    print(f"wsjt:{wsj} above: {loc} ({pc:.1%}) matched: {both} unmatched: {loc_only}")
