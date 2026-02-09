import time

class Ticker:
    def __init__(self, offset):
        self.previous_ticker_time = 0
        self.offset = offset

class Time_utils:
    def __init__(self):
        self.global_offset = 0

    def set_global_offset(self, global_offset):
        self.global_offset = global_offset

    def cyclestart_str(self, t, cycle_seconds = 15):
        cyclestart_time = cycle_seconds * int((t - self.global_offset) / cycle_seconds)
        return time.strftime("%y%m%d_%H%M%S", time.gmtime(cyclestart_time))

    def cycle_time(self, cycle_seconds = 15, offset = 0):
        return (time.time() - self.global_offset - offset) % cycle_seconds

    def tlog(self, txt, verbose = True):
        if(verbose):
            print(f"{self.cyclestart_str(time.time())} {self.cycle_time():5.2f} {txt}")

    def new_ticker(self, offset):
        return Ticker(offset)

    def check_ticker(self, ticker):
        ticker_time = self.cycle_time(offset = ticker.offset)
        ticked = ticker_time < ticker.previous_ticker_time
        ticker.previous_ticker_time = ticker_time
        return ticked

global_time_utils = Time_utils()

"""
test = global_time_utils.new_ticker(10)
while True:
    time.sleep(1)
    print(global_time_utils.cycle_time(), global_time_utils.check_ticker(test))
"""

