FROM python:3.11-slim as builder
#FROM python:3.11.4

# ARG UID=1000
# ARG GID=1000

RUN apt update
RUN apt upgrade -y
RUN apt install ffmpeg libsm6 libxext6 -y
COPY requirements.txt requirements.txt
RUN /usr/local/bin/python -m pip install --upgrade pip
RUN pip install -r requirements.txt
RUN mkdir /app
WORKDIR /app

COPY distance.py distance.py
COPY example.py example.py
COPY rebbitmq.py rebbitmq.py
COPY logs logs

# RUN groupadd -g "${GID}" -r vitaly \
#     && useradd -d '/app' -g vitaly -l -r -u "${UID}" vitaly \
#     && chown vitaly:vitaly -R /app

RUN chmod -R g+rw /app

USER vitaly