FROM python:3.11.4

# ARG UID=1000
# ARG GID=1000

RUN apt-get update
RUN apt-get upgrade -y
RUN apt-get install ffmpeg libsm6 libxext6 -y
COPY requirements.txt requirements.txt
RUN /usr/local/bin/python3.11 -m pip install --upgrade pip
RUN pip3 install -r requirements.txt
RUN mkdir /app
WORKDIR /app

COPY distance.py distance.py
COPY example.py example.py
COPY rabbitmq.py rabbitmq.py
COPY logs logs

# RUN groupadd -g "${GID}" -r vitaly \
#     && useradd -d '/app' -g vitaly -l -r -u "${UID}" vitaly \
#     && chown vitaly:vitaly -R /app

RUN chmod -R g+rw /app
CMD ["python3.11", "rabbitmq.py"]

#USER vitaly