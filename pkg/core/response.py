# coding=utf-8
import json
import logging


logger = logging.getLogger(__name__)


class Code(object):
    Success = "Success"

    ConnectionError = "ConnectionError"
    AnalyzeError = "AnalyzeError"
    AuthError = "AuthError"
    LogicError = "LogicError"
    ParameterError = "ParameterError"
    UnknownError = "UnknownError"


class Response(object):

    def __init__(self, code='', msg='', data=None):
        self.code = code
        self.msg = msg
        self.data = data

    def pack(self):
        r = {"code": self.code}
        if self.msg:
            r["msg"] = self.msg
        if self.data:
            r["data"] = self.data
        return json.dumps(r)

    @classmethod
    def unpack(cls, data):
        r = json.loads(data)
        return cls(r.get('code'), r.get('msg', ''), r.get('data'))

    def is_success(self):
        if self.code == Code.Success:
            return True
        return False

    def code_is_success(self):
        if self.data["code"] == 0:
            return True
        return False


class TException(Exception):

    def __init__(self, code, msg):
        self.code = code
        self.msg = msg
        super(TException, self).__init__('%s: %s' % (code, msg))
