import time

def wsjtx_tailer():
    wsjtx_lines = []
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
            with open('last wsjtx output.txt', 'a') as f:
                for l in wsjtx_lines:
                    f.write(f"{l}\n")
            wsjtx_lines=[]
        wsjtx_lines.append(line)

# sync issue - need wsjt-x previous cycle?

def wsjtx_compare(lines):
    with open('last wsjtx output.txt', 'r') as f:
        wsjt = f.readlines()

    tot, match = 0,0
    for wsjtline in wsjt:
        tot +=1
        for myline in lines:
            if(myline['msg'].replace(' ','') in wsjtline.replace(' ','')):
                match +=1
    print(f"{match} {tot}")
