# coding=utf-8
import os
import logging
import threading
from time import sleep

from bmstools.utils import auth
from .session import ServerSession
from ..core.macsocket import MACSocket

logger = logging.getLogger(__name__)

_bms_tools_server = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def get_server():
    """
    全局唯一server实例
    """
    global _bms_tools_server
    if not _bms_tools_server:
        _bms_tools_server = Server()
    return _bms_tools_server


class Server(threading.Thread):

    public_key_file = "/usr/lib/bmstools/auth/public.pem"
    private_key_file = "/usr/lib/bmstools/auth/private.pem"

    def __init__(self, *args, **kwargs):
        self.mac_socket = MACSocket()
        self.sessions = {}
        self.key_lock = threading.Lock()
        self.public_key = ''
        self.private_key = ''
        self.init_auth()
        self.mac_socket.start()
        super(Server, self).__init__(*args, **kwargs)

    def init_auth(self):
        if not os.path.exists(self.public_key_file) or not os.path.exists(self.private_key_file):
            self.private_key, self.public_key = auth.gen_key()
            with open(self.public_key_file, "w") as f:
                f.write(self.private_key)
            with open(self.private_key_file, "w") as f:
                f.write(self.public_key)
        else:
            with open(self.public_key_file) as f:
                self.public_key = f.read()
            with open(self.private_key_file) as f:
                self.public_key = f.read()

    def run(self):
        """
        从二层网卡接收数据，转发数据到对应已创建的session
        """
        logger.info("server start receive data")
        while True:
            try:
                packet = self.mac_socket.receive_data()
                if packet.is_new_session():
                    self.new_session(packet.src_key, packet.dest_mac, packet.src_mac, packet.vlan)
                else:
                    if packet.dest_key in self.sessions:
                        server_session = self.sessions.get(packet.dest_key)
                        server_session.handle_data(packet)
                    else:
                        logger.error("server not found session %s" % packet.src_key)
            except Exception as exc:
                logger.error("receive data error: %s" % exc, exc_info=True)
                sleep(3)

    def get_new_server_key(self):
        with self.key_lock:
            for i in range(1, 65536):
                if i not in self.sessions:
                    return i

    def new_session(self, dest_key, src_mac, dest_mac, vlan):
        """
        服务端创建一个新的session
        """
        src_key = self.get_new_server_key()
        logger.info("start new session, src_key: %s, dest_key: %s, src_mac: %s, dest_mac: %s, vlan: %s" % (
            src_key,
            dest_key,
            src_mac,
            dest_mac,
            vlan))
        ss = ServerSession(self,
                           mac_socket=self.mac_socket,
                           src_key=src_key,
                           dest_key=dest_key,
                           src_mac=src_mac,
                           dest_mac=dest_mac,
                           vlan=vlan)
        ss.ack_open_session()
        self.sessions[src_key] = ss

    def close_session(self, session):
        """
        关闭session
        """
        self.mac_socket.clean_session(session.src_key)
        self.mac_socket.global_socket = None
        self.sessions.pop(session.src_key)