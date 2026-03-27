import socket
import struct
import time
import threading
import random

MAX_REPORTS = 90

class PSKR_upload:
    # https://pskreporter.info/pskdev.html
    # https://pskreporter.info/cgi-bin/psk-analysis.pl
    def __init__(self, mycall, mygrid, software, console_print):
        self.RxInfoRecDescriptor_CallLocSoft = b"\x00\x03\x00\x24\x99\x92\x00\x03\x00\x01\x80\x02\xFF\xFF\x00\x00\x76\x8F\x80\x04\xFF\xFF\x00\x00\x76\x8F\x80\x08\xFF\xFF\x00\x00\x76\x8F\x00\x00"
        self.SenderInfoRecDescriptor_SenderFreqSNRiMDModeSourceTime = b"\x00\x02\x00\x3C\x99\x93\x00\x07\x80\x01\xFF\xFF\x00\x00\x76\x8F\x80\x05\x00\x04\x00\x00\x76\x8F\x80\x06\x00\x01\x00\x00\x76\x8F\x80\x07\x00\x01\x00\x00\x76\x8F\x80\x0A\xFF\xFF\x00\x00\x76\x8F\x80\x0B\x00\x01\x00\x00\x76\x8F\x00\x96\x00\x04"
        self.last_descriptors_time = 0
        self.descriptors_sent_count = 0
        self.last_report_time = time.time() - 300 + 60
        self.addr = ("report.pskreporter.info", 4739)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        #HOST = socket.gethostbyname(socket.gethostname())
        #self.sock.bind((HOST, 1234))
        self.session_id = random.getrandbits(32)
        self.seq = 1
        self.reports = {}
        rx = self._enc_str(mycall) + self._enc_str(mygrid) + self._enc_str(software)
        self.rx_block =  self._block(b"\x99\x92", rx)
        self.console_print = console_print
        self.lock = threading.Lock()
        print(f"[PSKR_upload] Spots will upload to pskreporter")
        threading.Thread(target = self._check_for_send, daemon = True).start()

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
        with self.lock:
            self.reports[dxcall] = (dxcall, freq_hz, snr, mode, source, (tt // 15) * 15)

    def _check_for_send(self):
        while True:
            time.sleep(60)
            with self.lock:
                if len(self.reports) >= MAX_REPORTS or (time.time() - self.last_report_time) > 300:
                    if (time.time() - self.last_descriptors_time) > 3600:
                        self.descriptors_sent_count = 0
                        self.last_descriptors_time = time.time()
                    self._send(includeDescriptors = (self.descriptors_sent_count <4))
                    self.descriptors_sent_count +=1
           
    def _send(self, includeDescriptors = False):
        if not self.reports:
            return
        tt = int(time.time())
        ipfx_header = struct.pack("!H", 10) + b"\x00\x00" + struct.pack("!I", tt) + struct.pack("!I", self.seq) + struct.pack("!I", self.session_id)
        header = ipfx_header
        if includeDescriptors:
            print(f"[pskr_upload] Packing descriptors")
            header = header + self.RxInfoRecDescriptor_CallLocSoft + self.SenderInfoRecDescriptor_SenderFreqSNRiMDModeSourceTime
        senders = bytearray()
        for dxcall, freq_hz, snr, mode, source, tt in self.reports.values():
            print(f"[pskr_upload] Packing report {dxcall}, {freq_hz}, {snr}, {mode}, {source}, {tt}")
            sender = self._enc_str(dxcall) + struct.pack("!I", int(freq_hz)) + struct.pack("b", int(snr)) + struct.pack("b", 0) + self._enc_str(mode) + struct.pack("B", source) + struct.pack("!I", tt)
            senders += sender
        packet = bytearray(header + self.rx_block + self._block(b"\x99\x93", senders))
        struct.pack_into("!H", packet, 2, len(packet))
        self.seq += len(self.reports)
        try:
            self.sock.sendto(packet, self.addr)
            txt = f"[pskr_upload] Sent packet with {len(self.reports)} reports"
        except:
            txt = "[PSKR_UPLOAD] Connection error"
        print(txt)
        self.console_print(txt, color = 'red')
        self.reports = {}
        self.last_report_time = time.time()


#pskr = PSKR_upload('G1OJS', 'IO90ju', software = 'PyFT8', console_print = None)
#pskr.add_report('G1OJS', 14074000, -5, 'FT8', 2, int(time.time()))
#pskr._send(includeDescriptors = True)
