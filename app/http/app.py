"""
@Time    : 2026/3/2 14:06
@AUthor  : jiachengjie
@File    : app.py
"""
import os

import dotenv
from flask_login import LoginManager
from flask_migrate import Migrate
from injector import Injector

from app.http.model import ExtensionModule
from config import Config
from internal.middleware import Middleware
from internal.router import Router
from internal.server import Http
from pkg.sqlalchemy import SQLAlchemy

# 将.evn加载到环境变量中
dotenv.load_dotenv()

# Windows专属兼容：eventlet池绿化的ssl与httpx2默认的truststore在TLS握手时互相递归
# (RecursionError)，指定certifi证书包可让httpx2改走标准ssl上下文。
# 仅Windows需要；Linux(epoll hub)无此问题，不设置，避免影响部署环境
import sys
if sys.platform == "win32" and not os.environ.get("SSL_CERT_FILE"):
    import certifi
    os.environ["SSL_CERT_FILE"] = certifi.where()

injector = Injector([ExtensionModule])

conf = Config()

app = Http(__name__,
           conf=conf,
           db=injector.get(SQLAlchemy),
           migrate=injector.get(Migrate),
           login_manager=injector.get(LoginManager),
           middleware=injector.get(Middleware),
           router=injector.get(Router))

celery = app.extensions["celery"]

if __name__ == '__main__':
    app.run(debug=True)
