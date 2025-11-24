def tx_cycle_on_click(t_click):
    i = int(((t_click+7.5) % 30)/15)
    tx_cycle = ['even','odd'][i]
    return tx_cycle

def sec_to_begin_tx(t_click, tx_cycle):
    max_immediate = 15 - 12.6
    t_click += (15 if tx_cycle == 'odd' else 0)
    t_click = t_click %30
    twait = 30 - t_click
    if(twait > 30-max_immediate): twait=0
    return twait + t_click

for t_click in range(60):
    tx_cycle = tx_cycle_on_click(t_click)
    sec = sec_to_begin_tx(t_click, tx_cycle)
    sec_odd = sec_to_begin_tx(t_click, 'odd')
    sec_even = sec_to_begin_tx(t_click, 'even')
   # print(t_click, twait_even, twait_odd)
    print(t_click, tx_cycle, sec)
