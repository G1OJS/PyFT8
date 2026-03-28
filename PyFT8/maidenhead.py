import numpy as np

def grid_to_latlong(grid, centre = True):
    lat, lon = -90, -180
    if centre:
        grid = grid + "LL44LL44LL44"[len(grid):]
    mults = [20, 2, 2/24, 0.2/24, 0.2/(24*24), 0.02/(24*24)]
    grid = grid[:2*len(mults)]
    pairs = [grid[i:i+2] for i in range(0,len(grid),2)]
    for i, p in enumerate(pairs):
        zero = [ord('A'),ord('0')][i % 2]
        lon += mults[i] * (ord(p[0]) - zero)
        lat += mults[i] * (ord(p[1]) - zero) / 2
    return (lat, lon)
        

def db(sq1, sq2):
    ll1, ll2 = grid_to_latlong(sq1), grid_to_latlong(sq2)
    lats = [np.radians(ll1[0]),np.radians(ll2[0])]
    dlat, dlon = np.radians(ll2[0] - ll1[0]), np.radians(ll2[1] - ll1[1])
    s_lats, c_lats = np.sin(lats), np.cos(lats)
    a = np.sin(dlat/2)**2 + c_lats[0] * c_lats[1] * np.sin(dlon/2)**2
    r = 6371 * 2 * np.asin(np.sqrt(a))
    b = np.atan2(c_lats[1] * np.sin(dlon), c_lats[0] * s_lats[1] - s_lats[0] * c_lats[1] * np.cos(dlon))
    return (r, np.degrees(b) % 360)

#grids = ['LL44LL44LL44', 'IO90', 'IO90JU', 'IO90JU44', 'IO90JU95LX', 'IO90JU96MA']
#for g in grids:
#    print(g, grid_to_latlong(g, centre = True))

#print(db('IO90','IO91'))
