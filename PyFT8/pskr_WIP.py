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
        self.tt = tt
        self.addr = ("report.pskreporter.info", 14739)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.session_id = 0
        self.seq = 1
        self.reports = []
        rx =  self._enc_str(mycall) + self._enc_str(mygrid) + self._enc_str(software)
        self.rx_block =  self._block(b"\x99\x92", rx)

    def _enc_str(self, s):
        b = s.encode("ascii")
        return struct.pack("B", len(b)) + b

    def _block(self, block_type, payload):
        len_with_header = len(payload) + 4
        pad_len = 4 - (len_with_header %4)
        len_with_pad = len_with_header + pad_len
        blk = block_type + struct.pack("!H", len_with_pad) + payload + b"\x00" * pad_len
        return blk 

    def add_report(self, dxcall, freq_hz, snr, mode, tt):
        self.reports.append((dxcall, freq_hz, snr, mode, tt))

    def send(self, includeDescriptors = False):
        if not self.reports:
            return
        ipfx_header = struct.pack("!H", 10) + b"\x00\x00" + struct.pack("!I", self.tt) + struct.pack("!I", self.seq) + struct.pack("!I", self.session_id)
        header = ipfx_header
        if includeDescriptors:
            header = header + self.RxInfoRecDescriptor_CallLocSoft + self.SenderInfoRecDescriptor_CallFreqSourceStart
        senders = bytearray()
        for call, freq, mode, snr, t in self.reports:
            sender = self._enc_str(call) + struct.pack("!I", int(freq)) + struct.pack("b", int(snr)) + self._enc_str(mode) + struct.pack("!I", int(t))
            senders += sender
        packet = bytearray(header + self.rx_block + self._block(b"\x99\x93", senders))
        struct.pack_into("!H", packet, 2, len(packet))
        self.seq += len(self.reports)
        self.reports.clear()
        self.sock.sendto(packet, self.addr)

        
pskr = PSKReporter('N1DQ', 'FN42hn', software = 'Homebrew v5.6', tt = 1200960114)
pskr.reports = [('N1DQ', 14070567, 'PSK', 1, 1200960084), ('KB1MBX', 14070987, 'PSK', 1, 1200960104)]
pskr.send(includeDescriptors = True)
