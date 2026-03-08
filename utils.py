import os
import pdf2image
import email.message

from PyPDF2 import PdfReader


class PDFUtil:

    @staticmethod
    def convert_to_images(name, dirname, fullname):
        for i, page in enumerate(pdf2image.convert_from_path(fullname, 300)):
            page.save(os.path.join(dirname, f"{name}-{i}.png"), "PNG")

    @staticmethod
    def convert_to_text(dirname, fullname):
        with open(f"{dirname}/text.txt", "w+") as f:
            for page in PdfReader(fullname).pages:
                f.write(page.extract_text() or "")

    @staticmethod
    def get_pages_count(fullname):
        return len(PdfReader(fullname).pages)


class WEBUtil:

    @staticmethod
    def build_content_disposition(filename, disposition="attachment"):
        msg = email.message.Message()
        msg.add_header("Content-Disposition", disposition, filename=filename)
        return msg["Content-Disposition"]
