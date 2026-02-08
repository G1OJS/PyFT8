import time

class Time_utils:
    def __init__(self):
        self.time_offset = 0

    def set_time_offset(self, time_offset):
        self.time_offset = time_offset

    def cyclestart_str(self, t, cycle_seconds = 15):
        cyclestart_time = cycle_seconds * int((t - self.time_offset) / cycle_seconds)
        return time.strftime("%y%m%d_%H%M%S", time.gmtime(cyclestart_time))

    def cycle_time(self, cycle_seconds = 15):
        return (time.time() - self.time_offset) % cycle_seconds

    def tlog(self, txt, verbose = True):
        if(verbose):
            print(f"{self.cyclestart_str(time.time())} {self.cycle_time():5.2f} {txt}")

global_time_utils = Time_utils()
