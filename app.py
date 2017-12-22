import os
import sqlite3
import tornado.web


DB_NAME = 'toz.db'
MEDIA_DIR = 'uploads'


class Application(tornado.web.Application):

    def __init__(self):
        # Define handlers
        handlers = [
            (r'/login', LoginHandler),
            (r'/', IndexHandler),
            (r'/upload', UploadFileHandler),
            (r'/delete/([^/]+)', DeleteFileHandler),
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


class UploadFileHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        # Get filename and byte-array of files from post request
        filename = self.request.files['file'][0]['filename']
        file = self.request.files['file'][0]['body']

        # Create folder for uploads, if it doesn't exist
        if not os.path.exists(MEDIA_DIR):
            os.mkdir(MEDIA_DIR)

        # Create new file on disk in upload folder with filename from request
        with open(os.path.join(MEDIA_DIR, filename), 'wb') as f:
            # Write byte-array from request to the file
            f.write(file)

            # Get username of current user from cookie
            username = tornado.escape.xhtml_escape(self.current_user)

            # Add entry with filename and uploader username to database
            self.application.db_cursor.execute('INSERT INTO files (id, filename, username) VALUES (NULL, "%s", "%s")' % (filename, username))
            self.application.db.commit()

        # Reddirect to main page
        self.redirect('/')


class DeleteFileHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self, id):
        # Get entry of file from database with ID from request
        self.application.db_cursor.execute('SELECT filename FROM files WHERE id=%d' % (int(id)))
        file = self.application.db_cursor.fetchall()

        # Get filename from first column of first row
        filename = file[0][0]

        try:
            # Remove file from disk
            os.remove(os.path.join(MEDIA_DIR, filename))
        except:
            pass

        # Remove entry of file from database with ID from request
        self.application.db_cursor.execute('DELETE FROM files WHERE id=%d' % (int(id)))
        self.application.db.commit()

        # Reddirect to main page
        self.redirect('/')


if __name__ == '__main__':
    # Initialize HTTP server and run on 1337 port
    server = tornado.httpserver.HTTPServer(Application())
    server.listen(1337)
    tornado.ioloop.IOLoop.instance().start()
