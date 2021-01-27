# coding=utf-8
import threading
import logging
from time import sleep

from bmstools.pkg.core.response import TException, Code
from ..core.macsocket import MACSocket
from .session import ClientSession

logger = logging.getLogger(__name__)


_bms_tools_client = None


def get_client():
    """
    全局唯一client实例
    """
    global _bms_tools_client
    if not _bms_tools_client:
        _bms_tools_client = Client()
    return _bms_tools_client


class Client(threading.Thread):

    def __init__(self, *args, **kwargs):
        self.mac_socket = MACSocket()
        self.mac_socket.net_card = "bond0"
        self.src_mac = self.mac_socket.get_mac(self.mac_socket.net_card)
        self.sessions = {}
        self.key_lock = threading.Lock()
        self.mac_socket.start()
        super(Client, self).__init__(*args, **kwargs)

    @classmethod
    def get_src_mac(cls):
        return ""

    def run(self):
        """
        从二层网卡接收数据，转发数据到对应已创建的session
        """
        logger.info("client start receive data")
        while True:
            try:
                packet = self.mac_socket.receive_data()
                if packet.dest_key:
                    if packet.dest_key in self.sessions:
                        client_session = self.sessions.get(packet.dest_key)
                        client_session.handle_data(packet)
                    else:
                        logger.error("client not found session %s" % packet.client_key)
                else:
                    logger.error("receive data not found client key")
            except Exception as exc:
                logger.error("receive data error: %s" % exc, exc_info=True)
                sleep(3)

    def get_new_client_key(self):
        with self.key_lock:
            for i in range(1, 65536):
                if i not in self.sessions:
                    self.sessions[i] = None
                    return i

    def new_session(self, dest_mac, vlan, private_key="", src_mac=None):
        """
        客户端创建一个新的session
        """
        src_key = self.get_new_client_key()
        if not src_mac:
            src_mac = self.src_mac
        cs = ClientSession(self,
                           src_key=src_key,
                           mac_socket=self.mac_socket,
                           src_mac=src_mac,
                           dest_mac=dest_mac,
                           vlan=vlan,
                           private_key=private_key)
        self.sessions[src_key] = cs
        return cs

    def new_sessions(self, dest_macs, vlan_ids, private_key="", src_mac=None):
        """
        客户端创建一个新的session
        """
        if dest_macs and vlan_ids:
            src_key = self.get_new_client_key()
            try:
                if not src_mac:
                    src_mac = self.src_mac
                for vlan in vlan_ids:
                    for dest_mac in dest_macs:
                        logger.info("new session with src_key: %s, dest_mac: %s, vlan: %s" % (src_key,
                                                                                              dest_mac,
                                                                                              vlan))
                        try:
                            cs = ClientSession(self,
                                               src_key=src_key,
                                               mac_socket=self.mac_socket,
                                               src_mac=src_mac,
                                               dest_mac=dest_mac,
                                               vlan=int(vlan),
                                               private_key=private_key)
                            self.sessions[src_key] = cs
                            cs.open_session()
                            logger.info("open server session success")
                            return cs
                        except Exception as exc:
                            logger.error("new client session error: %s" % exc, exc_info=True)
                raise TException(Code.ConnectionError, "new client session error, can not connect server")
            except Exception as exc:
                logger.error("new session error: %s" % exc, exc_info=True)
                self.sessions.pop(src_key)
                raise exc

    def close_session(self, session):
        """
        关闭session
        """
        self.mac_socket.clean_session(session.src_key)
        self.mac_socket.global_socket = None
        self.sessions.pop(session.src_key)
