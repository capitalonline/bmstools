# coding=utf-8
import logging
import threading
import socket
import struct
import binascii
from datetime import datetime
from functools import reduce
from time import sleep
import time
from psutil import net_if_addrs
from psutil import net_if_stats

from .packet import Frame, PacketType, Packet, PacketFrames

ETH_P_BMS = 0x7fff
ETH_P_VLAN = 0x8100
BuffSize = 65536
RETRY_SLEEP = [3, 6, 9, 15]

logger = logging.getLogger(__name__)


class MACSocket(threading.Thread):

    def __init__(self, *args, **kwargs):
        self.net_card = None
        self.receive_socket = socket.socket(socket.PF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_BMS))
        self.global_socket = None
        self.ETH_P_BMS_BY = self.format_mac_bytes(self.i2b_hex(ETH_P_BMS))
        self.ETH_P_VLAN_BY = self.format_mac_bytes(self.i2b_hex(ETH_P_VLAN))
        self.max_frame_length = 300
        self.receive_frame_caches = {}
        self.send_frame_caches = {}
        self.mac_list = self.get_all_mac()
        self.send_socket = {}
        super(MACSocket, self).__init__(*args, **kwargs)

    def run(self):
        """
        run thread to retry send frame cache
        """
        while True:
            try:
                self.retry_send_frame()
            except Exception as exc:
                logger.error("retry send frame error: %s", exc, exc_info=True)
            sleep(3)

    def retry_send_frame(self):
        """
        retry send cache frame
        """
        now = time.mktime(datetime.now().timetuple())
        if self.send_frame_caches:
            for src_key, frames in self.send_frame_caches.items():
                for frame_key, frame in frames.items():
                    if src_key in self.send_frame_caches and frame.send_time and \
                            now - frame.send_time >= RETRY_SLEEP[frame.retry_count]:
                        if frame_key in frames:
                            self.send_frame(frame)
                            if frame.retry_count > 3:
                                frames.pop(frame_key)

    def set_send_socket(self, dst_mac=''):
        if not self.net_card:
            self.net_card = self.get_send_net_card(dst_mac)
        else:
            if not self.bool_card(self.net_card):
                self.net_card = self.get_send_net_card(dst_mac)
        logger.info("send net card: %s" % self.net_card)
        raw_socket = socket.socket(socket.PF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_BMS))
        raw_socket.bind((self.net_card, socket.htons(ETH_P_BMS)))
        return raw_socket

    def clean_session(self, session_key):
        """
        清除session缓存
        """
        if session_key in self.receive_frame_caches:
            self.receive_frame_caches.pop(session_key)
        if session_key in self.send_frame_caches:
            self.send_frame_caches.pop(session_key)
        if session_key in self.send_socket:
            self.send_socket.pop(session_key)

    @classmethod
    def frame_cache_key(cls, frame):
        """
        每个session缓存的key
        """
        return '%s:%s:%s' % (frame.sequence, frame.count, frame.offset)

    def receive_frame(self):
        """
        二层接收帧数据包Frame，接收之后返回ACK
        """
        packet, packet_info = self.receive_socket.recvfrom(BuffSize)
        eth_hdr = struct.unpack("!6s6s2s", packet[0:14])
        dst_mac, src_mac, eth_type = binascii.hexlify(eth_hdr[0]), \
                                     binascii.hexlify(eth_hdr[1]), \
                                     eth_hdr[2]

        if dst_mac not in self.mac_list:
            return

        if eth_type != '\x7f\xff':
            logger.error("receive eth type %s is not bms type" % (eth_type,))
            return
        ver, ptype, src_key = struct.unpack('!BBH', packet[14: 18])
        dest_key, sequence, count, offset, vlan, length = struct.unpack('!HIHHIH', packet[18: 34])
        frame = Frame(src_mac=src_mac,
                      dest_mac=dst_mac,
                      src_key=src_key,
                      ptype=ptype,
                      dest_key=dest_key,
                      sequence=sequence,
                      count=count,
                      offset=offset,
                      vlan=vlan,
                      length=length)
        if ptype in (PacketType.Data, PacketType.Control):
            frame.data = packet[34: 34 + frame.length]

        logger.info("receive frame, src_key: %s, dest_key: %s, ptype: %s, src_mac: %s, dest_mac: %s, sequence: %s \
count: %s, offset: %s, vlan: %s, length: %s, data: %s" % (frame.src_key,
                                                          frame.dest_key,
                                                          frame.ptype,
                                                          frame.src_mac,
                                                          frame.dest_mac,
                                                          frame.sequence,
                                                          frame.count,
                                                          frame.offset,
                                                          frame.vlan,
                                                          frame.length,
                                                          frame.data))

        # if self.global_socket is None:
        #     if not self.net_card:
        #         self.net_card = self.get_send_net_card(dst_mac)
        #     self.global_socket = socket.socket(socket.PF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_BMS))
        #     self.global_socket.bind((self.net_card, socket.htons(ETH_P_BMS)))

        if frame.ptype != PacketType.Ack:
            # 返回Ack确认包
            b_src = self.format_mac_bytes(frame.dest_mac)
            b_dest = self.format_mac_bytes(frame.src_mac)
            ack_frame = Frame(src_mac=b_src,
                              dest_mac=b_dest,
                              src_key=frame.dest_key,
                              dest_key=frame.src_key,
                              ptype=PacketType.Ack,
                              sequence=frame.sequence,
                              count=frame.count,
                              offset=frame.offset,
                              vlan=vlan)
            self.send_frame(ack_frame)
        return frame

    def receive_data(self):
        """
        一个sequence中接收的数据，并排序重组，返回Packet
        """
        while True:
            frame = self.receive_frame()
            # logger.info("receive frame ptype: %s" % (frame.ptype,))
            if frame.ptype in (PacketType.OpenSession, PacketType.EndSession):
                # 开启一个新的session，直接返回packet包
                packet = Packet(src_mac=frame.src_mac,
                                dest_mac=frame.dest_mac,
                                src_key=frame.src_key,
                                dest_key=frame.dest_key,
                                ptype=frame.ptype,
                                sequence=frame.sequence,
                                vlan=frame.vlan)
                return packet
            if frame.ptype == PacketType.Ack:
                # 处理Ack，删除cache中的frame
                if frame.dest_key in self.send_frame_caches:
                    cache_key = self.frame_cache_key(frame)
                    if cache_key in self.send_frame_caches.get(frame.dest_key):
                        self.send_frame_caches[frame.dest_key].pop(cache_key)
            elif frame.ptype in (PacketType.Data, PacketType.Control):
                # 数据包或控制包，组合count所有的offset之后返回packet包
                if frame.dest_key not in self.receive_frame_caches:
                    packet_frames = PacketFrames(src_mac=frame.src_mac,
                                                 dest_mac=frame.dest_mac,
                                                 src_key=frame.src_key,
                                                 dest_key=frame.dest_key,
                                                 ptype=frame.ptype,
                                                 sequence=frame.sequence,
                                                 count=frame.count,
                                                 vlan=frame.vlan)
                    # 根据dest_key添加缓存组合offset
                    self.receive_frame_caches[frame.dest_key] = packet_frames
                packet_frames = self.receive_frame_caches.get(frame.dest_key)
                packet_frames.add_frame(frame)
                if packet_frames.has_receive_all():
                    # sequence已经接收到所有count
                    data = packet_frames.packet_data()
                    packet = Packet(src_mac=frame.src_mac,
                                    dest_mac=frame.dest_mac,
                                    src_key=frame.src_key,
                                    dest_key=frame.dest_key,
                                    ptype=frame.ptype,
                                    sequence=frame.sequence,
                                    vlan=frame.vlan,
                                    data=data)
                    # 删除offset缓存
                    self.receive_frame_caches.pop(frame.dest_key)
                    return packet

    def send_frame(self, frame):
        """
        二层发送帧数据包Frame，记录发送的数据，并超时重试
        """
        b_vlan = self.format_mac_bytes(self.i2b_hex(frame.vlan))
        version = 1
        send_frame = struct.pack("!6s6s2s2s2s",
                                 frame.dest_mac,
                                 frame.src_mac,
                                 self.ETH_P_VLAN_BY,
                                 b_vlan,
                                 self.ETH_P_BMS_BY)
        send_frame += struct.pack("!BBHH",
                                  version,
                                  int(frame.ptype),
                                  int(frame.src_key),
                                  int(frame.dest_key))
        send_frame += struct.pack("!IHH",
                                  frame.sequence,
                                  frame.count,
                                  frame.offset)
        send_frame += struct.pack("!I",
                                  frame.vlan)

        if frame.data:
            send_frame += struct.pack("!H", frame.length)
            send_frame += frame.data
        else:
            send_frame += struct.pack("!H", 0)
        logger.info("send frame, src_key: %s, dest_key: %s, ptype: %s, src_mac: %s, dest_mac: %s, sequence: %s \
count: %s, offset: %s, vlan: %s, length: %s, data: %s" % (frame.src_key,
                                                          frame.dest_key,
                                                          frame.ptype,
                                                          frame.src_mac,
                                                          frame.dest_mac,
                                                          frame.sequence,
                                                          frame.count,
                                                          frame.offset,
                                                          frame.vlan,
                                                          frame.length,
                                                          frame.data))

        if frame.src_key not in self.send_socket.keys():
            src_mac = binascii.hexlify(frame.src_mac)
            raw_socket = self.set_send_socket(src_mac)
            self.send_socket[frame.src_key] = raw_socket
        else:
            raw_socket = self.send_socket[frame.src_key]

        try:
            raw_socket.send(send_frame)
        except Exception as e:
            logger.error("send frame err : %s", e)
            src_mac = binascii.hexlify(frame.src_mac)
            raw_socket = self.set_send_socket(src_mac)
            self.send_socket[frame.src_key] = raw_socket
            raw_socket.send(send_frame)

        # raw_socket.send(send_frame)
        if frame.ptype != PacketType.Ack:
            if frame.src_key not in self.send_frame_caches:
                self.send_frame_caches[frame.src_key] = {}
            send_frame_caches = self.send_frame_caches.get(frame.src_key)
            cache_key = self.frame_cache_key(frame)
            # 设置发送时间戳
            frame.send_time = time.mktime(datetime.now().timetuple())
            frame.retry_count += 1
            send_frame_caches[cache_key] = frame

    def send_data(self, packet):
        """
        发送sequence数据Packet，并拆分为帧包，所有数据都收到ACK，才算发送完成
        """
        packet.src_mac = self.format_mac_bytes(self.format_mac(packet.src_mac))
        packet.dest_mac = self.format_mac_bytes(self.format_mac(packet.dest_mac))
        if packet.ptype in (PacketType.OpenSession, PacketType.EndSession):
            frame = Frame(src_mac=packet.src_mac,
                          dest_mac=packet.dest_mac,
                          src_key=packet.src_key,
                          dest_key=packet.dest_key,
                          ptype=packet.ptype,
                          sequence=packet.sequence,
                          vlan=packet.vlan,
                          count=1,
                          offset=0,
                          length=0)
            self.send_frame(frame)
        elif packet.ptype in (PacketType.Data, PacketType.Control):
            count, offset = 1, 0
            logger.info("send packet data: %s" % (packet.data,))
            if packet.data:
                count = int(len(packet.data) / self.max_frame_length)
                if len(packet.data) % self.max_frame_length:
                    count += 1
                for i in range(count):
                    if (i + 1) * self.max_frame_length > len(packet.data):
                        frame_data = packet.data[i * self.max_frame_length:]
                    else:
                        frame_data = packet.data[i * self.max_frame_length: (i + 1) * self.max_frame_length]
                    # if frame_data:
                    frame = Frame(src_mac=packet.src_mac,
                                  dest_mac=packet.dest_mac,
                                  src_key=packet.src_key,
                                  dest_key=packet.dest_key,
                                  ptype=packet.ptype,
                                  sequence=packet.sequence,
                                  vlan=packet.vlan,
                                  count=count,
                                  offset=i,
                                  length=len(frame_data),
                                  data=frame_data)
                    self.send_frame(frame)
            else:
                frame = Frame(src_mac=packet.src_mac,
                              dest_mac=packet.dest_mac,
                              src_key=packet.src_key,
                              dest_key=packet.dest_key,
                              ptype=packet.ptype,
                              sequence=packet.sequence,
                              vlan=packet.vlan,
                              count=count,
                              offset=offset,
                              length=0,
                              data='')
                self.send_frame(frame)

    @classmethod
    def format_mac(cls, mac_address):
        return mac_address.replace(":", "")

    @classmethod
    def format_mac_bytes(cls, msg):
        return reduce(lambda x, y: x + y, [binascii.unhexlify(msg[i:i + 2]) for i in range(0, len(msg), 2)])

    @classmethod
    def i2b_hex(cls, protocol):
        b_protocol = hex(int(protocol))[2:]
        return b_protocol if len(b_protocol) % 2 == 0 else '0{0}'.format(b_protocol).encode('utf8')

    @classmethod
    def get_send_net_card(cls, mac):
        for k, v in net_if_addrs().items():
            for item in v:
                if item.address.replace(":", "") == mac and "bond" in k and "." not in k and net_if_stats()[k].duplex == 2:
                    return k

        for k, v in net_if_addrs().items():
            for item in v:
                if item.address.replace(":", "") == mac and "bond" not in k and net_if_stats()[k].duplex == 2:
                    return k

    @classmethod
    def get_mac(cls, card):
        msg = net_if_addrs()
        for i in msg[card]:
            if i.family == 17:
                return i.address

    @classmethod
    def get_all_mac(cls):
        mac_list = []
        for k, v in net_if_addrs().items():
            for item in v:
                if item.family == 17:
                    mac_list.append(item[1].replace(":", ""))
        return mac_list

    @classmethod
    def bool_card(cls, card):
        if net_if_stats()[card].duplex == 2:
            return True