import os
import sqlite3
import tornado.web


DB_NAME = 'toz.db'


class Application(tornado.web.Application):

    def __init__(self):
        # Define handlers
        handlers = [
            (r'/login', LoginHandler),
            (r'/', IndexHandler),
        ]

        # Define options
        settings = {
            'cookie_secret': str(os.urandom(45)),
            'login_url': '/login',
        }

        # Initialize application
        super(Application, self).__init__(handlers, **settings)

        # Initialize connection to SQLite3 database
        self.db = sqlite3.connect(DB_NAME)
        self.db_cursor = self.db.cursor()

        # Create table for files
        try:
            self.db_cursor.execute('CREATE TABLE files (id INTEGER PRIMARY KEY, filename VARCHAR(255), username VARCHAR(255))')
        except sqlite3.OperationalError:
            pass


class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        # Get username of current user from cookie
        return self.get_secure_cookie('user')


class LoginHandler(BaseHandler):
    def get(self):
        # Render and return login page
        self.render('templates/login.html')

    def post(self):
        # Handle login form and set username of logged in user to cookie
        self.set_secure_cookie('user', self.get_argument('name'))

        # Redirect to main page
        self.redirect('/')


class IndexHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self):
        # Get list of files from database
        self.application.db_cursor.execute('SELECT * FROM files ORDER BY id')
        files = self.application.db_cursor.fetchall()

        # Render and return main page with list of files
        self.render('templates/index.html', files=files)


if __name__ == '__main__':
    # Initialize HTTP server and run on 1337 port
    server = tornado.httpserver.HTTPServer(Application())
    server.listen(1337)
    tornado.ioloop.IOLoop.instance().start()
