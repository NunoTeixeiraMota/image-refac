FROM python:3.12-slim

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
