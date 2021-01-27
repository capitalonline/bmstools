import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, BASE_DIR)

import sys
import logging
import traceback
from bmstools.base_server import BaremetalDaemon
from bmstools.utils import log, shell

logger = logging.getLogger(__name__)


def main():
    pidfile = '/var/run/cdsstack/bmstools.pid'
    log.setup()
    shell.prepare_pid_dir(pidfile)
    try:
        agentdaemon = BaremetalDaemon(pidfile)
        logger.info('bmstools service starts')
        agentdaemon.start()
        sys.exit(0)
    except Exception:
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    main()
