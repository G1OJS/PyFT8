import time

class Time_utils:
    def __init__(self):
        self.cycle_seconds = 15

    def time(self):
        return time.time()

    def sleep(self, t):
        time.sleep(t)

    def set_cycle_length(self, dur):
        self.cycle_seconds = dur

    def cycle_time(self):
        return (self.time()) % self.cycle_seconds

    def grid_time(self):
        return (self.time()) % (2*self.cycle_seconds)

    def odd_even(self):
        return int( self.grid_time() / self.cycle_seconds)

    def cyclestart(self, t):
        cst = self.cycle_seconds * int(t / self.cycle_seconds)
        css = time.strftime("%y%m%d_%H%M%S", time.gmtime(cst))
        return {'time':cst, 'string':css}

    def tlog(self, txt, verbose = False):
        if(verbose):
            print(f"{self.cyclestart(self.time())['string']} {self.cycle_time():5.2f} {txt}")

    def format_duration(self, seconds):
        intervals = ( ('yr', 314496000), ('wk', 604800), ('day', 86400), ('hr', 3600), ('min', 60), ('sec', 1) )
        for name, count in intervals:
            value = int(seconds / count)
            if value:
                return f"{value:d} {name}{'s' if value > 1 else ''}"

time_utils = Time_utils()

"""
class Ticker:
    def __init__(self, trigger_time, cycle_length = time_utils.cycle_seconds, timing_function = time_utils.cycle_time):
        self.previous_ticker_time = 0
        self.timing_function = timing_function
        self.trigger_time = trigger_time
        self.cycle_length = cycle_length

    def ticked(self):
        ticker_time = (self.timing_function() - self.trigger_time) % self.cycle_length
        ticked = ticker_time < self.previous_ticker_time
        self.previous_ticker_time = ticker_time
        return ticked
"""
