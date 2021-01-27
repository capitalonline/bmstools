# coding=utf-8
# import logging
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.path.insert(0, BASE_DIR)
from bmstools.utils import log, auth
from bmstools.pkg.server import server


def main():
    logger = log.setup()
    logger.info("start server")
    s = server.get_server()
    s.run()


if __name__ == '__main__':
    print "version 1.1.0"
    main()
