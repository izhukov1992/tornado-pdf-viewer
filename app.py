import os
import sqlite3
import tornado.web
import io
import shutil
import datetime
from PyPDF2 import PdfFileWriter, PdfFileReader
from wand.image import Image
from wand.color import Color


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
            (r'/download/([^/]+)', DownloadFileHandler),
            (r'/review/([^/]+)', ReviewFileHandler),
            (r'/uploads/(.*)', tornado.web.StaticFileHandler, {'path': 'uploads'}),
        ]

        # Define options
        settings = {
            'cookie_secret': str(os.urandom(45)),
            'login_url': '/login',
        }

        # Initialize application
        super(Application, self).__init__(handlers, **settings)

        # Initialize SQLite3 database
        self.db_init()

        self.executor = tornado.concurrent.futures.ThreadPoolExecutor(8)

    def db_init(self):
        # Initialize connection to SQLite3 database and store cursor
        self.db = sqlite3.connect(DB_NAME)
        self.db_cursor = self.db.cursor()

        # Create table for files
        try:
            self.db_cursor.execute('CREATE TABLE files (id INTEGER PRIMARY KEY, filename VARCHAR(255), username VARCHAR(255), pages INTEGER, folder VARCHAR(255))')
        except sqlite3.OperationalError:
            pass

    def get_files(self):
        # Get list of files from database
        self.db_cursor.execute('SELECT * FROM files ORDER BY id')
        files = self.db_cursor.fetchall()
        return files

    def get_file(self, id):
        # Get entry of file from database
        self.db_cursor.execute('SELECT * FROM files WHERE id=%d' % (int(id)))
        file = self.db_cursor.fetchall()[0]
        return file

    def add_file(self, filename, username, pages, folder):
        # Add entry with filename and uploader username to database
        self.db_cursor.execute('INSERT INTO files (id, filename, username, pages, folder) VALUES (NULL, "%s", "%s", %d, "%s")' % (filename, username, pages, folder))
        self.db.commit()

    def remove_files(self, id):
        # Get entry of file from database with ID from request
        file = self.get_file(id)

        # Get name of folder from the fifth column of row
        folder = file[4]

        # Define subfolder name
        dirname = os.path.join(MEDIA_DIR, folder)

        # Remove files from disk
        try:
            shutil.rmtree(dirname)
        except:
            # Files have already been deleted
            pass

        # Remove entry of file from database with ID from request
        self.db_cursor.execute('DELETE FROM files WHERE id=%d' % (int(id)))
        self.db.commit()

    def convert_file(self, name, dirname, fullname):
        # Read bytes of PDF file
        with open(fullname, 'rb') as f:
            try:
                src_pdf = PdfFileReader(f)
            except:
                return

            # Read each page and convert to image
            for i, page in enumerate(src_pdf.pages, 1):
                dst_pdf = PdfFileWriter()
                dst_pdf.addPage(page)

                # Read page to byte stream
                pdf_bytes = io.BytesIO()
                dst_pdf.write(pdf_bytes)
                pdf_bytes.seek(0)

                # Save PNG with white background without alpha channel from byte stream
                with Image(file = pdf_bytes, resolution = 300, background = Color('#fff')) as img:
                    img.alpha_channel = False

                    # Save image with page number in name
                    img.save(filename = os.path.join(dirname, name + '-' + str(i) + '.png'))


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
        files = self.application.get_files()

        # Render and return main page with list of files
        self.render('templates/index.html', files=files)


class UploadFileHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        # Get byte-array and filename of file from post request
        try:
            file = self.request.files['file'][0]['body']
            filename = self.request.files['file'][0]['filename']
        except:
            # If file is not choosen, return 400 respone
            self.clear()
            self.set_status(404)
            self.render('templates/400.html', error="File is not choosen")
            return

        # Create folder for uploads, if it doesn't exist
        if not os.path.exists(MEDIA_DIR):
            os.mkdir(MEDIA_DIR)

        # Split filename to name and extension
        try:
            name, extension = filename.split('.')
        except:
            name = filename
            extension = 'pdf'
            filename = '.'.join([name, extension])

        # Define subfolder name
        dirname = os.path.join(MEDIA_DIR, name)

        # Define full name of file
        fullname = os.path.join(dirname, filename)

        timestamp = None

        # Recompose folder name while it's not unique
        while os.path.exists(dirname):
            timestamp = int(datetime.datetime.now().timestamp())
            new_name = name + '-' + str(timestamp)

            dirname = os.path.join(MEDIA_DIR, new_name)
        else:
            # Create subfolder for images converted from PDF
            os.mkdir(dirname)

            # If folder with initial name exists, update related names
            if timestamp is not None:
                name = name + '-' + str(timestamp)
                filename = '.'.join([name, extension])
                fullname = os.path.join(dirname, filename)

        # Create new file on disk in subfolder with filename from request
        with open(fullname, 'wb') as f:
            # Write byte-array from request to the file
            f.write(file)

        # Get pages count
        with open(fullname, 'rb') as f:
            try:
                src_pdf = PdfFileReader(f)
                pages = src_pdf.getNumPages()
            except:
                # If file is not PDF, remove file's folder
                shutil.rmtree(dirname)

                # Return 400 respone
                self.clear()
                self.set_status(404)
                self.render('templates/400.html', error="File is not PDF")
                return

        # Get username of current user from cookie
        username = tornado.escape.xhtml_escape(self.current_user)

        # Add entry with filename and uploader username to database
        self.application.add_file(filename, username, pages, name)

        # Convert PDF to images asynchronously
        self.application.executor.submit(self.application.convert_file, name, dirname, fullname)

        # Reddirect to main page
        self.redirect('/')


class DeleteFileHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self, id):
        # Remove entry from database and related files from disk
        self.application.remove_files(id)

        # Reddirect to main page
        self.redirect('/')


class DownloadFileHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self, id):
        # Get entry of file from database with ID from request
        file = self.application.get_file(id)

        # Get filename from the second column of row
        filename = file[1]

        # Get name of folder from the fifth column of row
        folder = file[4]

        # Define subfolder name
        dirname = os.path.join(MEDIA_DIR, folder)

        # Define full name of file
        fullname = os.path.join(dirname, filename)

        try:
            # Open file from disk
            with open(fullname, 'rb') as f:
                # Add headers to response
                self.set_header('Content-Type', 'application/force-download')
                self.set_header('Content-Disposition', 'attachment; filename=%s' % filename)

                # Read file and write to response
                self.write(f.read())

                # Complete response
                self.finish()

        except FileNotFoundError:
            # File was removed
            # Remove entry from database and related files from disk
            self.application.remove_files(id)

            # Return 404 respone
            self.clear()
            self.set_status(404)
            self.render('templates/404.html')


class ReviewFileHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self, id):
        # Get entry of file from database with ID from request
        file = self.application.get_file(id)

        # Get filename from the second column of row
        filename = file[1]

        # Get number of pages
        pages = file[3]

        # Get name of folder from the fifth column of row
        folder = file[4]

        # Render and return main page with list of files
        self.render('templates/review.html', filename=filename, folder=folder, pages=range(1, pages+1))


if __name__ == '__main__':
    # Initialize HTTP server and run on 1337 port
    server = tornado.httpserver.HTTPServer(Application())
    server.listen(1337)
    tornado.ioloop.IOLoop.instance().start()

