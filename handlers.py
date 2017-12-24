import os
import tornado.web
import shutil
import datetime
from conf import MEDIA_DIR
from utils import PDFUtil


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
            pages = PDFUtil.get_pages_count(fullname)
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
        self.application.executor.submit(PDFUtil.convert, name, dirname, fullname)

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

