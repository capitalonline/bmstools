# coding=utf-8
import hashlib
import logging
import threading
import types
from os.path import getsize

from bmstools.pkg.core.packet import Packet, PacketType, ControlPacket, ControlType, SessionState
from bmstools.pkg.core.response import Response, Code, TException
from bmstools.utils import auth

logger = logging.getLogger(__name__)


class ClientSession(object):

    def __init__(self, client, src_key=None, dest_key=0, mac_socket=None, src_mac=None, dest_mac=None, vlan=0,
                 private_key=''):
        self.client = client
        self.src_key = src_key
        self.dest_key = dest_key
        self.mac_socket = mac_socket
        self.src_mac = src_mac
        self.dest_mac = dest_mac
        self.vlan = vlan
        self.sequence = 0
        # self.send_socket = self.mac_socket.set_send_socket()
        self.state = SessionState.NEW
        self.private_key = private_key.strip()

        self.receive_condition = threading.Condition()
        self.receive_data = None
        self.receive_sequence_caches = []

        self.max_slice_length = 900000

    def __enter__(self):
        """
        打开session，认证过程
        """
        try:
            self.auth()
        except Exception as exc:
            logger.error("auth error: %s" % exc)
            self.exit_session()
            raise exc
        self.state = SessionState.OK
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        退出session
        """
        self.exit_session()

    def exit_session(self):
        """
        退出session
        """
        logger.info("start end session %s" % self.src_key)
        self.end_session()
        self.client.close_session(self)
        self.state = SessionState.END
        logger.info("end session %s success" % self.src_key)

    def open_session(self):
        """
        开启session，获取服务端session key
        """
        logger.info("send open session packet")
        resp_packet = self.request(PacketType.OpenSession, timeout=30)
        logger.info("receive server open session, server key: %s", resp_packet.src_key)
        if resp_packet is None:
            raise TException(Code.ConnectionError, "can not connect server with mac %s vlan %s" % (self.dest_mac,
                                                                                                   self.vlan))
        self.dest_key = resp_packet.src_key
        self.state = SessionState.CONNECT

    def auth(self):
        """
        客户端认证
        """
        # 开始请求认证
        logger.info("start session auth")
        auth_control = ControlPacket(ControlType.Auth)
        resp_packet = self.request(PacketType.Control, auth_control.pack())
        self.state = SessionState.AUTH
        # 私钥解密服务端随机数
        auth_random = ControlPacket.unpack(resp_packet.data)
        logger.info("server random number: %s" % auth_random.data)
        de_auth_random = auth.decrypt(self.private_key, auth_random.data)
        if isinstance(de_auth_random, types.MethodType):
            logger.error("decrypt auth random error")
            raise TException(Code.AuthError, "client decrypt auth random error")
        logger.info(de_auth_random)
        # md5加密随机数发送
        md5_random = hashlib.md5(de_auth_random.encode("utf-8")).hexdigest()
        logger.info("md5 random: %s" % md5_random)
        md5_packet = ControlPacket(ControlType.Auth, md5_random)
        resp_packet = self.request(PacketType.Control, md5_packet.pack())
        logger.info("md5 check res: %s" % resp_packet.data)
        check_resp = Response.unpack(resp_packet.data)
        if not check_resp.is_success():
            raise TException(check_resp.code, check_resp.msg)

    def end_session(self):
        logger.info("send end session packet")
        self.request(PacketType.EndSession, timeout=30)
        logger.info("receive server end session")

    def handle_data(self, packet):
        """
        接收到数据处理
        """
        if packet.sequence not in self.receive_sequence_caches:
            self.receive_sequence_caches.append(packet.sequence)
        else:
            return
        with self.receive_condition:
            self.receive_data = packet
            self.receive_condition.notify()

    def receive_response(self, timeout=300):
        """
        从macsocket获取接收数据或返回数据
        :rtype: Packet
        """
        self.receive_data = None
        with self.receive_condition:
            if not self.receive_data:
                self.receive_condition.wait(timeout)
        return self.receive_data

    def request(self, ptype, data='', timeout=300):
        """
        对服务端发送请求
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
        resp_packet = self.receive_response(timeout=timeout)
        return resp_packet

    def exec_cmd(self, cmd, timeout=300):
        cmd_packet = ControlPacket(ctype=ControlType.Exec, data=cmd)
        resp = self.request(PacketType.Control, cmd_packet.pack(), timeout)
        logger.info("exec cmd response: %s" % (resp.data,))
        return Response.unpack(resp.data)

    def send_file(self, file_path, dest_file_path):
        file_packet = ControlPacket(ctype=ControlType.File, data=dest_file_path)
        resp = self.request(PacketType.Control, file_packet.pack())
        logger.info("send file path response: %s" % (resp.data,))
        file_length = getsize(file_path)
        file_sequence = int(file_length / self.max_slice_length)
        if file_length % self.max_slice_length:
            file_sequence += 1
        f = open(file_path, "rb")
        for i in range(file_sequence):
            # self.mac_socket.send_data(dst_mac=self.dest_mac, sequence=i, dest_key=self.dest_key,
            #                           data=f.read(self.max_slice_length), src_key=self.src_key)
            resp = self.request(PacketType.Data, str(f.read(self.max_slice_length)))
            logger.info("send file response: %s" % (resp.data,))
            res = Response.unpack(resp.data)
            if not res.is_success():
                return res
        f.close()
        return Response(Code.Success)
