
def meth1(a):
    c = " ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    x =  a-1003
    ci1 = x // (27*27*27)
    x %= 27*27*27
    ci2 = x // (27*27)
    x %= 27*27
    ci3 = x // 27
    x %= 27
    ci4 = x
    aaaa = c[ci1] + c[ci2] + c[ci3] + c[ci4]
    return f"CQ {aaaa}"


import numpy


def meth2(a):
    c = " ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    x = int(a - 1003)
    print(x)
    txt = ''
    for i in range(4):
        txt = c[int(x % 27)] + txt
        x /= 27
    return f"CQ {txt}"

for a in [1004, 1029, 1031, 1731, 1760, 20685, 21443, 532443, 1135]:
    print(meth1(a), meth2(a))
