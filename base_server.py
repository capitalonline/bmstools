# from bmstools.utils import auth
from bmstools.pkg.server import server
from bmstools.utils import daemon


class BaremetalDaemon(daemon.Daemon):

    def __init__(self, *args, **kwargs):
        self.server = server.get_server()
        super().__init__(*args, **kwargs)

    def run(self):
        self.server.run()
