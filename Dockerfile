FROM python:3.8-slim-buster
MAINTAINER Sebastien Vermeille <sebastien.vermeille@gmail.com>
WORKDIR /app
COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt
RUN mkdir -p /app/temp
COPY . .

ARG PAPERLESS_SYNC_SCAN_VERSION=1.0.0
ENV SCANNER_URL='http://192.168.1.16'
ENV SCANNER_USERNAME='admin'
ENV SCANNER_PASSWORD='1234'

ENV PAPERLESS_URL='http://192.168.1.17:8000'
ENV PAPERLESS_LOGIN='paperlessadmin'
ENV PAPERLESS_PASSWORD='1234'

CMD [ "python3", "syncScanner.py"]