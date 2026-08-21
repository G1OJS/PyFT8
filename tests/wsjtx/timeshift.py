
with open('wsjtx.txt', 'r') as f:
    lines = f.readlines()
    times = [l.split()[2] for l in lines]

with open('wsjtxb.txt', 'w') as f:
    for i, l in enumerate(lines):
        newtime =f"{float(times[i])-15:8.2f}"
        f.write(f"{l.replace(times[i], newtime)}")
