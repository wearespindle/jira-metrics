FROM python:2-slim-stretch

LABEL maintainer="info@wearespindle.com"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENTRYPOINT ["/usr/local/bin/python2"]
CMD ["/app/main.py"]
