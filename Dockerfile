FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo-dev \
    libwebp-dev \
    zlib1g-dev \
    libtiff-dev \
    libfreetype-dev \
    liblcms2-dev \
    libopenjp2-7-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY converter/ converter/
COPY webapp/ webapp/
COPY static/ static/
COPY templates/ templates/
COPY run.py .
COPY PngToWebpScript.py .

EXPOSE 5000

CMD ["python", "run.py"]
