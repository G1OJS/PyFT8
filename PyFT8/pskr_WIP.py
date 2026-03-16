import socket
import struct
import time
import random

class PSKReporter:
    # https://pskreporter.info/pskdev.html
    # 

    def __init__(self, mycall, mygrid, software, tt):
        self.RxInfoRecDescriptor_CallLocSoft = b"\x00\x03\x00\x24\x99\x92\x00\x03\x00\x01\x80\x02\xFF\xFF\x00\x00\x76\x8F\x80\x04\xFF\xFF\x00\x00\x76\x8F\x80\x08\xFF\xFF\x00\x00\x76\x8F\x00\x00"
        self.SenderInfoRecDescriptor_CallFreqSourceStart = b"\x00\x02\x00\x2C\x99\x93\x00\x05\x80\x01\xFF\xFF\x00\x00\x76\x8F\x80\x05\x00\x04\x00\x00\x76\x8F\x80\x0A\xFF\xFF\x00\x00\x76\x8F\x80\x0B\x00\x01\x00\x00\x76\x8F\x00\x96\x00\x04"
        self.SenderInfoRecDescriptor_SenderFreqSNRiMDModeSourceTime = b"\x00\x02\x00\x3C\x99\x93\x00\x07\x80\x01\xFF\xFF\x00\x00\x76\x8F\x80\x05\x00\x04\x00\x00\x76\x8F\x80\x06\x00\x01\x00\x00\x76\x8F\x80\x07\x00\x01\x00\x00\x76\x8F\x80\x0A\xFF\xFF\x00\x00\x76\x8F\x80\x0B\x00\x01\x00\x00\x76\x8F\x00\x96\x00\x04"
        self.tt = tt
        self.addr = ("report.pskreporter.info", 14739)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.session_id = random.getrandbits(32)
        self.seq = 1
        self.reports = []
        rx =  self._enc_str(mycall) + self._enc_str(mygrid) + self._enc_str(software)
        self.rx_block =  self._block(b"\x99\x92", rx)

    def _enc_str(self, s):
        b = s.encode("ascii")
        return struct.pack("B", len(b)) + b

    def _block(self, block_type, payload):
        len_with_header = len(payload) + 4
        pad_len = (4 - (len_with_header % 4)) % 4
        len_with_pad = len_with_header + pad_len
        blk = block_type + struct.pack("!H", len_with_pad) + payload + b"\x00" * pad_len
        return blk 

    def add_report(self, dxcall, freq_hz, snr, mode, source, tt):
        self.reports.append((dxcall, freq_hz, snr, mode, source, (tt // 15) * 15))

    def send(self, includeDescriptors = False):
        if not self.reports:
            return
        ipfx_header = struct.pack("!H", 10) + b"\x00\x00" + struct.pack("!I", self.tt) + struct.pack("!I", self.seq) + struct.pack("!I", self.session_id)
        header = ipfx_header
        if includeDescriptors:
            header = header + self.RxInfoRecDescriptor_CallLocSoft + self.SenderInfoRecDescriptor_SenderFreqSNRiMDModeSourceTime
        senders = bytearray()
        for dxcall, freq_hz, snr, mode, source, tt in self.reports:
            sender = self._enc_str(dxcall) + struct.pack("!I", int(freq_hz)) + struct.pack("b", int(snr)) + struct.pack("b", 0) + self._enc_str(mode) + struct.pack("B", source) + struct.pack("!I", tt)
            senders += sender
        packet = bytearray(header + self.rx_block + self._block(b"\x99\x93", senders))
        struct.pack_into("!H", packet, 2, len(packet))
        self.seq += len(self.reports)
        self.reports.clear()
        #self.sock.sendto(packet, self.addr)
        print(' '.join([hex(b) for b in packet]))
        print(len(packet))

pskr = PSKReporter('N1DQ', 'FN42hn', software = 'Homebrew v5.6', tt = int(time.time()))
pskr.add_report('N1DQ', 14070567, -5, 'FT8', 1, int(time.time()))
pskr.add_report('KB1MBX', 14070987, -5, 'FT8', 1, int(time.time()))
pskr.send(includeDescriptors = True)
