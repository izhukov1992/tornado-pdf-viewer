import os
import io
from PyPDF2 import PdfFileWriter, PdfFileReader
from wand.image import Image
from wand.color import Color


class PDFUtil:

    @staticmethod
    def convert(name, dirname, fullname):
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

    @staticmethod
    def get_pages_count(fullname):
        with open(fullname, 'rb') as f:
            src_pdf = PdfFileReader(f)
            pages = src_pdf.getNumPages()
        return pages

