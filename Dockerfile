FROM python:alpine

RUN apk --no-cache add ca-certificates

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY moj_analytics /usr/local/lib/python3.6/site-packages/moj_analytics
COPY resource /opt/resource
RUN chmod +x /opt/resource/check /opt/resource/in /opt/resource/out
