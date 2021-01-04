#
#   WSGI middleware for exposing the Cloud NDB context to all requests
#

from google.cloud import ndb


class NdbMiddleware:
    def __init__(self, app):
        self.app = app
        self.client = ndb.Client()

    def __call__(self, env, start_response):
        with self.client.context():
            return self.app(env, start_response)
