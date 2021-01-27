# coding=utf-8
import logging
import logging.config


LOG_SETTINGS = {
    'version': 1,
    'formatters': {
        'detailed': {
            'format': '%(asctime)s %(levelname)s %(process)d %(name)s.%(lineno)d %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'detailed',
            'stream': 'ext://sys.stdout',
        },

    },
    'loggers': {
        'bmstools': {
            'level': 'DEBUG',
            'handlers': ['console']
        },
    }
}


def setup():
    logging.config.dictConfig(LOG_SETTINGS)
    logger = logging.getLogger('bmstools')
    return logger
