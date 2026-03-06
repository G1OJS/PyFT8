import time

class Time_utils:
    def __init__(self):
        self.cycle_seconds = 15

    def set_cycle_length(self, dur):
        self.cycle_seconds = dur

    def cycle_time(self):
        return (time.time()) % self.cycle_seconds

    def cyclestart_time(self, t):
        return self.cycle_seconds * int(t / self.cycle_seconds)

    def cyclestart_str(self, t):
        return time.strftime("%y%m%d_%H%M%S", time.gmtime(self.cyclestart_time(t)))

    def tlog(self, txt, verbose = True):
        if(verbose):
            print(f"{self.cyclestart_str(time.time())} {self.cycle_time():5.2f} {txt}")

global_time_utils = Time_utils()

class Ticker:
    def __init__(self, trigger_time, cycle_length = global_time_utils.cycle_seconds, timing_function = global_time_utils.cycle_time):
        self.previous_ticker_time = 0
        self.timing_function = timing_function
        self.trigger_time = trigger_time
        self.cycle_length = cycle_length

    def ticked(self):
        ticker_time = (self.timing_function() - self.trigger_time) % self.cycle_length
        ticked = ticker_time < self.previous_ticker_time
        self.previous_ticker_time = ticker_time
        return ticked
