FROM python:3.11.4

RUN apt-get update
RUN apt-get upgrade -y
RUN apt-get install ffmpeg libsm6 libxext6 -y
COPY requirements.txt requirements.txt
RUN /usr/local/bin/python3.11 -m pip install --upgrade pip
RUN pip3 install -r requirements.txt
RUN mkdir /app
WORKDIR /app

COPY distance.py distance.py
COPY config.py config.py
COPY rabbitmq.py rabbitmq.py
COPY hash2text.py hash2text.py
COPY find_ei.py find_ei.py
COPY split_by_keys.py split_by_keys.py
COPY yandexgpt.py yandexgpt.py
COPY logs logs
RUN mkdir data
COPY data/mats4.csv data/mats4.csv
COPY data/msgs.csv data/msgs.csv
COPY data/categories.csv data/categories.csv
COPY data/saves.csv data/saves.csv
COPY data/method2.csv data/method2.csv


RUN chmod -R g+rw /app
CMD ["python3.11", "rabbitmq.py"]
