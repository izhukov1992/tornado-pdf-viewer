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


class FileEntry:

    def __init__(self, row):
        self.id = row[0]
        self.filename = row[1]
        self.username = row[2]
        self.pages = row[3]
        self.folder = row[4]


class FileList:

    def __init__(self, rows):
        self._files = []
        self._index = 0

        for row in rows:
            self._files.append(FileEntry(row))

    def __iter__(self):
        self._index = 0
        return self

    def __next__(self):
        self._index += 1
        if len(self._files) >= self._index:
            return self._files[self._index - 1]
        else:
            raise StopIteration

    def __getitem__(self, item):
        try:
            return self._files[item]
        except:
            return None

    def is_empty(self):
        if self._files == []:
            return True
        return False


class DataBase:

    def __init__(self):
        # Initialize connection to SQLite3 database and store cursor
        self._connection = sqlite3.connect(DB_NAME)
        self._cursor = self._connection.cursor()

    def select(self, query):
        self._cursor.execute(query)
        rows = self._cursor.fetchall()
        return rows

    def execute(self, query):
        self._cursor.execute(query)
        self._connection.commit()


class FileTableManager:

    def __init__(self, db):
        self._db = db

        # Create table for files
        try:
            self._db.execute('CREATE TABLE files (id INTEGER PRIMARY KEY, filename VARCHAR(255), username VARCHAR(255), pages INTEGER, folder VARCHAR(255))')
        except sqlite3.OperationalError:
            # Table already exists
            pass

    def select_all_files(self):
        # Get list of files from database
        rows = self._db.select('SELECT * FROM files ORDER BY id')
        files = FileList(rows)
        return files

    def select_file(self, id):
        # Get entry of file from database
        rows = self._db.select('SELECT * FROM files WHERE id=%d' % (int(id)))
        files = FileList(rows)
        return files[0]

    def insert_file(self, filename, username, pages, folder):
        # Add entry with filename, username, count of pages and folder to database
        self._db.execute('INSERT INTO files (id, filename, username, pages, folder) VALUES (NULL, "%s", "%s", %d, "%s")' % (filename, username, pages, folder))

    def delete_file(self, id):
        # Remove entry of file from database with ID from request
        self._db.execute('DELETE FROM files WHERE id=%d' % (int(id)))


class PDFManager:

    def convert(self, name, dirname, fullname):
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
                with Image(file=pdf_bytes, resolution=300, background=Color('#fff')) as img:
                    img.alpha_channel = False

                    # Save image with page number in name
                    img.save(filename = os.path.join(dirname, name + '-' + str(i) + '.png'))

    def get_pages_count(self, fullname):
        with open(fullname, 'rb') as f:
            src_pdf = PdfFileReader(f)
            pages = src_pdf.getNumPages()
        return pages


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
        self._db = DataBase()

        # Initialize file table manager
        self.ftm = FileTableManager(self._db)

        # Initialize PDF manager
        self.pdfm = PDFManager()

        # Store executer of background coroutines
        self.executor = tornado.concurrent.futures.ThreadPoolExecutor(8)


class BaseHandler(tornado.web.RequestHandler):

    def get_current_user(self):
        # Get username of current user from cookie
        return self.get_secure_cookie('user')

    def response_user_error(self, error):
        # Clear response, set status, and render template
        self.clear()
        self.set_status(400)
        self.render('templates/400.html', error=error)

    def response_not_found(self):
        # Clear response, set status, and render template
        self.clear()
        self.set_status(404)
        self.render('templates/404.html')


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
        files = self.application.ftm.select_all_files()

        # Render and return main page with list of files
        self.render('templates/index.html', files=files)


class UploadFileHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        # Get byte-array and filename of file from post request
        try:
            filename = self.request.files['file'][0]['filename']
            payload = self.request.files['file'][0]['body']
        except:
            # If file is not choosen, return 400 respone
            self.response_user_error("File is not choosen")
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
            f.write(payload)

        # Get pages count
        try:
            pages = self.application.pdfm.get_pages_count(fullname)
        except:
            # If file is not PDF, remove file's folder
            shutil.rmtree(dirname)

            # Return 400 respone
            self.response_user_error("File is not PDF")
            return

        # Get username of current user from cookie
        username = tornado.escape.xhtml_escape(self.current_user)

        # Add entry with filename and uploader username to database
        self.application.ftm.insert_file(filename, username, pages, name)

        # Convert PDF to images asynchronously
        self.application.executor.submit(self.application.pdfm.convert, name, dirname, fullname)

        # Reddirect to main page
        self.redirect('/')


class DeleteFileHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self, id):
        # Get entry of file from database with ID from request
        pdf = self.application.ftm.select_file(id)

        # Define subfolder name
        dirname = os.path.join(MEDIA_DIR, pdf.folder)

        # Remove files from disk
        try:
            shutil.rmtree(dirname)
        except:
            # Files have already been deleted
            pass

        # Remove entry from database and related files from disk
        self.application.ftm.delete_file(id)

        # Reddirect to main page
        self.redirect('/')


class DownloadFileHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self, id):
        # Get entry of file from database with ID from request
        pdf = self.application.ftm.select_file(id)

        # Define subfolder name
        dirname = os.path.join(MEDIA_DIR, pdf.folder)

        # Define full name of file
        fullname = os.path.join(dirname, pdf.filename)

        try:
            # Open file from disk
            with open(fullname, 'rb') as f:
                # Add headers to response
                self.set_header('Content-Type', 'application/force-download')
                self.set_header('Content-Disposition', 'attachment; filename=%s' % pdf.filename)

                # Read file and write to response
                self.write(f.read())

                # Complete response
                self.finish()

        except FileNotFoundError:
            # File was removed
            # Return 404 respone
            self.response_not_found()


class ReviewFileHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self, id):
        # Get entry of file from database with ID from request
        pdf = self.application.ftm.select_file(id)

        # Render and return main page with list of files
        self.render('templates/review.html', filename=pdf.filename, folder=pdf.folder, pages=range(1, pdf.pages+1))


if __name__ == '__main__':
    # Initialize HTTP server and run on 1337 port
    server = tornado.httpserver.HTTPServer(Application())
    server.listen(1337)
    tornado.ioloop.IOLoop.instance().start()

