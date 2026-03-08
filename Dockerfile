FROM python:3.14.3

RUN apt-get update && apt-get install poppler-utils -y

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY templates ./templates
COPY *.py .

CMD ["python", "/app/app.py"]
