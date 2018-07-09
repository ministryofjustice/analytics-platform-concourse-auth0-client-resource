FROM python:3.7-alpine AS base

RUN apk --no-cache add ca-certificates

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY moj_analytics /usr/local/lib/python3.7/site-packages/moj_analytics
COPY resource /opt/resource
RUN chmod +x /opt/resource/check /opt/resource/in /opt/resource/out


FROM base AS test

COPY test.requirements.txt ./
RUN pip install --no-cache-dir -r test.requirements.txt

COPY tests tests
RUN pytest


FROM base
