# coding=utf-8
import logging
import struct

from bmstools.pkg.core.response import TException, Code

logger = logging.getLogger(__name__)


class PacketType(object):
    OpenSession = 0
    Data = 1
    Ack = 2
    Control = 3
    EndSession = 255


class Frame(object):
    """
    二层收发帧数据
    """

    def __init__(self, src_mac=None, dest_mac=None, src_key=None, dest_key=None, ptype=None, sequence=None,
                 count=None, offset=None, vlan=None, length=None, data=None):
        self.src_mac = src_mac
        self.dest_mac = dest_mac
        self.src_key = src_key
        self.dest_key = dest_key
        self.ptype = ptype
        self.sequence = sequence
        self.count = count
        self.offset = offset
        self.vlan = vlan
        self.length = length
        self.data = data
        self.send_time = None
        self.retry_count = 0


class PacketFrames(object):
    """

    """
    def __init__(self, src_mac=None, dest_mac=None, src_key=None, dest_key=None, ptype=None, sequence=None,
                 vlan=None, count=None):
        self.src_mac = src_mac
        self.dest_mac = dest_mac
        self.src_key = src_key
        self.dest_key = dest_key
        self.ptype = ptype
        self.sequence = sequence
        self.count = count
        self.vlan = vlan
        self.frames = {}
        self.receive_count = 0

    def add_frame(self, frame):
        if frame.offset not in self.frames:
            self.receive_count += 1
        self.frames[frame.offset] = frame.data
        logger.info("offset: %s, data: %s" % (frame.offset, frame.data))

    def has_receive_all(self):
        if self.receive_count == self.count:
            return True
        return False

    def packet_data(self):
        data = ''
        for i in range(self.count):
            data += self.frames[i]
        logger.info("data: %s" % data)
        logger.info("frames: %s" % self.frames)
        return data


class Packet(object):
    """
    sequence收发数据包结构
    """

    def __init__(self, src_mac=None, dest_mac=None, src_key=None, dest_key=None, ptype=None, sequence=None,
                 vlan=None, data=None):
        self.src_mac = src_mac
        self.dest_mac = dest_mac
        self.src_key = src_key
        self.dest_key = dest_key
        self.ptype = ptype
        self.sequence = sequence
        self.vlan = vlan
        self.data = data

    def is_new_session(self):
        if self.ptype == PacketType.OpenSession:
            return True
        return False


class ControlType(object):
    Noop = -1       # 空类型
    Auth = 0        # 认证控制
    Exec = 1        # 执行命令
    File = 2        # 传输文件


class ControlPacket(object):
    """
    控制包结构
    """

    def __init__(self, ctype=None, data=None):
        self.ctype = ctype
        self.data = data

    def pack(self):
        p = struct.pack("!B", self.ctype)
        if self.data:
            p += struct.pack("!I", len(self.data))
            p += self.data
        else:
            p += struct.pack("!I", 0)
        return p

    @classmethod
    def unpack(cls, data):
        ctype, length = struct.unpack("!BI", data[:5])
        if ctype not in (ControlType.Auth, ControlType.Exec, ControlType.File):
            raise TException(Code.AnalyzeError, "Control packet type %s is not correct" % (ctype,))
        if length > 0:
            var_data = data[5: 5 + length]
        else:
            var_data = ''
        logger.debug("ctype: %s, length: %s, data: %s" % (ctype, length, var_data))
        return cls(ctype=ctype, data=var_data)


class SessionState(object):
    NEW = "new"
    CONNECT = "connect"
    AUTH = "auth"
    OK = "ok"
    END = "end"
