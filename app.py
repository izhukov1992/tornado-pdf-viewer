import tornado.web
import conf
from handlers import LoginHandler, IndexHandler, UploadFileHandler, DeleteFileHandler, DownloadFileHandler, ReviewFileHandler
from db import DataBase, FileTableManager


class Application(tornado.web.Application):

    def __init__(self):
        # Define handlers
        handlers = [
            (r'/login', LoginHandler),
            (r'/', IndexHandler),
            (r'/upload', UploadFileHandler),
            (r'/delete/([^/]+)', DeleteFileHandler),
            (r'/download/([^/]+)', DownloadFileHandler),
            (r'/review/([^/]+)', ReviewFileHandler),
            (r'/uploads/(.*)', tornado.web.StaticFileHandler, {'path': 'uploads'}),
        ]

        # Define options
        settings = {
            'cookie_secret': conf.SECRET_KEY,
            'login_url': '/login',
        }

        # Initialize application
        super(Application, self).__init__(handlers, **settings)

        # Initialize SQLite3 database
        self._db = DataBase(conf.DB_NAME)

        # Initialize file table manager
        self.ftm = FileTableManager(self._db)

        # Store executer of background coroutines
        self.executor = tornado.concurrent.futures.ThreadPoolExecutor(8)


if __name__ == '__main__':
    # Initialize HTTP server and run on 1337 port
    server = tornado.httpserver.HTTPServer(Application())
    server.listen(1337)
    tornado.ioloop.IOLoop.instance().start()

