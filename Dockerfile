#ver3
#builder stage
FROM python:3.11-slim as builder

RUN apt-get install -y gnupg
RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 6ED0E7B82643E131
RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-keys F8D2585B8783D481
RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 0E98404D386FA1D9 
RUN apt-get update && apt-get install -y libpq-dev gcc

#create the virtual env
RUN python -m venv /opt/venv
#activate virtual env
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install -r requirements.txt --proxy=http://vproxy2.spk.ru:3128 >&2

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev nano && rm -rf /var/lib/apt/lists/*

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