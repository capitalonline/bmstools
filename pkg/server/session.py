# coding=utf-8
import hashlib
import logging
import random
import string

from ..core.response import Response, Code
from bmstools.utils import shell, auth, command
from ..core.packet import Packet, PacketType, ControlType, ControlPacket, SessionState

logger = logging.getLogger(__name__)


class ServerSession(object):

    def __init__(self, server, mac_socket=None, src_key=None, dest_key=None, src_mac=None, dest_mac=None, vlan=None):
        self.server = server
        self.mac_socket = mac_socket
        self.src_key = src_key
        self.dest_key = dest_key
        self.src_mac = src_mac
        self.dest_mac = dest_mac
        self.sequence = 0
        self.vlan = vlan
        # self.send_socket = self.mac_socket.set_send_socket()
        self.state = SessionState.NEW
        self.random_auth = ''

        self.ctype = ControlType.Noop
        self.save_file_path = ""
        self.script_format = "__cds_bms_tools"
        self.receive_sequence_caches = []

    def response(self, ptype, data=''):
        """
        服务端对客户端响应
        """
        packet = Packet(src_mac=self.src_mac,
                        dest_mac=self.dest_mac,
                        src_key=self.src_key,
                        dest_key=self.dest_key,
                        ptype=ptype,
                        sequence=self.sequence,
                        vlan=self.vlan,
                        data=data)
        self.mac_socket.send_data(packet)
        self.sequence += 1

    def ack_open_session(self):
        logger.info("send ack open session")
        self.response(PacketType.OpenSession)

    def ack_end_session(self):
        logger.info("send ack end session")
        self.response(PacketType.EndSession)

    def _handle_data(self, packet):
        if packet.ptype == PacketType.Control:
            control = ControlPacket.unpack(packet.data)
            self.ctype = control.ctype
            if self.ctype == ControlType.File:
                # 传输文件，data为文件路径名
                self.save_file_path = control.data
                if not self.save_file_path:
                    return Response(Code.ParameterError, "Save file path is empty")
                if command.file_exists(self.save_file_path) and self.script_format not in self.save_file_path:
                    return Response(Code.ParameterError, "Dest file path exists")
                return Response(Code.Success)
            elif self.ctype == ControlType.Exec:
                # 执行命令
                return self.exec_cmd(control.data)
        elif packet.ptype == PacketType.Data:
            # 数据包，当前只有传输文件时会使用
            if self.ctype == ControlType.File:
                if self.save_file_path:
                    return self.save_file(packet.data)
                else:
                    return Response(Code.LogicError, "Session save file path is empty")
            else:
                Response(Code.LogicError, "Session receive data but is not file")
        else:
            Response(Code.LogicError, "Session can not process packet type %s" % (packet.ptype,))

    def handle_data(self, packet):
        """
        接收到数据处理
        """
        res = None
        if packet.sequence not in self.receive_sequence_caches:
            self.receive_sequence_caches.append(packet.sequence)
        else:
            return
        if packet.ptype == PacketType.EndSession:
            logger.info("start end session %s" % self.src_key)
            self.ack_end_session()
            if self.script_format in self.save_file_path:
                res = command.remove_tree(self.save_file_path)
            if res:
                logger.error("remove file error: %s" % res)
            self.server.close_session(self)
            logger.info("end session %s success" % self.src_key)
            return
        else:
            if packet.ptype == PacketType.Control:
                control = ControlPacket.unpack(packet.data)
                if control.ctype == ControlType.Auth:
                    # session认证
                    if self.state == SessionState.NEW:
                        logger.info("start auth session")
                        random_auth = ''.join(random.sample(string.ascii_letters + string.digits, 8))
                        logger.info("auth random: %s" % random_auth)
                        en_random_auth = auth.encrypt(self.server.public_key, random_auth)
                        logger.info("encrypt auth random: %s" % en_random_auth)
                        random_control = ControlPacket(ControlType.Auth, en_random_auth)
                        self.response(PacketType.Control, random_control.pack())
                        self.state = SessionState.AUTH
                        self.random_auth = random_auth
                    else:
                        logger.info("start auth md5 random")
                        src_md5_random = control.data
                        md5_random = hashlib.md5(self.random_auth.encode('utf-8')).hexdigest()
                        logger.info("src_md5_random: %s, md5_random: %s" % (src_md5_random, md5_random))
                        if md5_random == src_md5_random:
                            self.response(PacketType.Data, Response(Code.Success).pack())
                            self.state = SessionState.OK
                        else:
                            self.response(PacketType.Data,
                                          Response(Code.AuthError, "auth random md5 is not match").pack())
                    return
            if self.state != SessionState.OK:
                self.response(PacketType.Data, Response(Code.AuthError, "current session is not ok state").pack())
                return
            logger.info("receive packet data: %s" % (packet.data,))
            resp = self._handle_data(packet)
            self.response(PacketType.Data, resp.pack())

    def exec_cmd(self, cmd):
        s = shell.call(cmd)
        resp = {
            "code": s.return_code,
            "stdout": s.stdout,
            "stderr": s.stderr
        }
        return Response(Code.Success, data=resp)

    def save_file(self, data):
        logger.info("save data: %s" % data)
        with open(self.save_file_path, "ab") as f:
            f.write(data)
        return Response(Code.Success, msg="save file %s success" % (self.save_file_path,))
