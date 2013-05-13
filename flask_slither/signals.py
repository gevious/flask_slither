# -*- coding: utf-8 -*-
from blinker import signal

request_authenticated = signal("request_authenticated")
perms_updated = signal("perms_updated")
