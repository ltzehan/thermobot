from gevent import monkey

monkey.patch_all()

from gevent.pywsgi import WSGIServer
from werkzeug.serving import run_with_reloader

from .app import create_app


@run_with_reloader
def runServer():

    server = WSGIServer(("127.0.0.1", 5000), create_app())
    server.serve_forever()


if __name__ == "__main__":

    runServer()
