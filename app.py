import os
import sqlite3
import tornado.web
import io
from PyPDF2 import PdfFileWriter, PdfFileReader
from PIL import Image


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

        # Define subfolder name
        dirname = os.path.join(MEDIA_DIR, filename.split('.')[0])

        # Create subfolder for images converyed from PDF
        if not os.path.exists(dirname):
            os.mkdir(dirname)

        # Create new file on disk in subfolder with filename from request
        with open(os.path.join(dirname, filename), 'wb') as f:
            # Write byte-array from request to the file
            f.write(file)

            # Get username of current user from cookie
            username = tornado.escape.xhtml_escape(self.current_user)

            # Add entry with filename and uploader username to database
            self.application.db_cursor.execute('INSERT INTO files (id, filename, username) VALUES (NULL, "%s", "%s")' % (filename, username))
            self.application.db.commit()


        from wand.image import Image
        # Converting first page into JPG
        with Image(filename="/thumbnail.pdf[0]") as img:
            img.save(filename="/temp.jpg")
        # Resizing this image
        with Image(filename="/temp.jpg") as img:
            img.resize(200, 150)
            img.save(filename="/thumbnail_resize.jpg")

        """src_pdf = PdfFileReader(open(os.path.join(dirname, filename), "rb"))

        # Get the first page of the PDF #
        dst_pdf = PdfFileWriter()
        dst_pdf.addPage(src_pdf.getPage(0))
        
        pdf_bytes = io.BytesIO()
        dst_pdf.write(pdf_bytes)
        pdf_bytes.seek(0)

        file_name = os.path.join(dirname, filename.split('.')[0] + '.png')
        img = Image.open(pdf_bytes)
        img.save(file_name, 'PNG')
        pdf_bytes.flush()"""
        
        """
        number = 0
        
        src_pdf = PdfFileReader(open(os.path.join(dirname, filename), "rb"))  
        page = 0 
        xObject = src_pdf.getPage(page)

        xObject = xObject['/Resources']['/XObject'].getObject()

        for obj in xObject:

            if xObject[obj]['/Subtype'] == '/Image':
                size = (xObject[obj]['/Width'], xObject[obj]['/Height'])
                data = xObject[obj]._data
                if xObject[obj]['/ColorSpace'] == '/DeviceRGB':
                    mode = "RGB"
                else:
                    mode = "P"

                imagename = os.path.join(dirname, filename.split('.')[0])

                if xObject[obj]['/Filter'] == '/FlateDecode':
                    img = Image.frombytes(mode, size, data)
                    img.save(imagename + ".png")
                    number += 1
                elif xObject[obj]['/Filter'] == '/DCTDecode':
                    img = open(imagename + ".jpg", "wb")
                    img.write(data)
                    img.close()
                    number += 1
                elif xObject[obj]['/Filter'] == '/JPXDecode':
                    img = open(imagename + ".jp2", "wb")
                    img.write(data)
                    img.close()
                    number += 1"""
        

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

        # Define subfolder name
        dirname = os.path.join(MEDIA_DIR, filename.split('.')[0])

        try:
            # Remove file from disk
            os.remove(os.path.join(dirname, filename))
            os.rmdir(dirname)
        except:
            pass

        # Remove entry of file from database with ID from request
        self.application.db_cursor.execute('DELETE FROM files WHERE id=%d' % (int(id)))
        self.application.db.commit()

        # Reddirect to main page
        self.redirect('/')


class DownloadFileHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self, id):
        # Get entry of file from database with ID from request
        self.application.db_cursor.execute('SELECT filename FROM files WHERE id=%d' % (int(id)))
        file = self.application.db_cursor.fetchall()

        # Get filename from first column of first row
        filename = file[0][0]

        # Define subfolder name
        dirname = os.path.join(MEDIA_DIR, filename.split('.')[0])

        # Add headers to response
        self.set_header('Content-Type', 'application/force-download')
        self.set_header('Content-Disposition', 'attachment; filename=%s' % filename)

        # Open file from disk
        with open(os.path.join(dirname, filename), 'rb') as f:
            # Read file and write to response
            self.write(f.read())

            # Complete response
            self.finish()


if __name__ == '__main__':
    # Initialize HTTP server and run on 1337 port
    server = tornado.httpserver.HTTPServer(Application())
    server.listen(1337)
    tornado.ioloop.IOLoop.instance().start()
