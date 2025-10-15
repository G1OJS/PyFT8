import numpy

from ldpc_decode_constants import Mn, Nm

def ldpc_decode(codeword, ldpc_iters):
    # 174 codeword bits:
    #   91 systematic data bits
    #   83 parity checks

    mnx = numpy.array(Mn, dtype=numpy.int32)
    nmx = numpy.array(Nm, dtype=numpy.int32)
    m = numpy.zeros((83, 174))

    for i in range(0, 174):
        for j in range(0, 83):
            m[j][i] = codeword[i]

    for iter in range(0, 30):
        e = numpy.zeros((83, 174))
        for i in range(0, 7):
            a = numpy.ones(83)
            for ii in range(0, 7):
                if ii != i:
                    x1 = numpy.tanh(m[range(0, 83), nmx[:,ii]-1] / 2.0)
                    x2 = numpy.where(numpy.greater(nmx[:,ii], 0.0), x1, 1.0)
                    a = a * x2
            b = numpy.where(numpy.less(a, 0.99999), a, 0.99)
            c = numpy.log((b + 1.0) / (1.0 - b))
            d = numpy.where(numpy.equal(nmx[:,i], 0),
                            e[range(0,83), nmx[:,i]-1],
                            c)
            e[range(0,83), nmx[:,i]-1] = d
        e0 = e[mnx[:,0]-1, range(0,174)]
        e1 = e[mnx[:,1]-1, range(0,174)]
        e2 = e[mnx[:,2]-1, range(0,174)]
        ll = codeword + e0 + e1 + e2
        cw = numpy.select( [ ll < 0 ], [ numpy.ones(174, dtype=numpy.int32) ])

       # if ldpc_check(cw):
        print(codeword[0:91])
        print(cw[0:91])
        return cw[0:91]

    return False

def ldpc_check(codeword):
    for e in Nm:
        x = 0
        for i in e:
            if i != 0:
                x ^= codeword[i-1]
        if x != 0:
            return False
    return True
