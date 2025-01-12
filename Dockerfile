FROM python:3.11.4

ENV http_proxy="http://vproxy2.spk.ru:3128"
ENV https_proxy="http://vproxy2.spk.ru:3128"

RUN apt-get update
RUN apt-get upgrade -y
RUN apt-get install ffmpeg libsm6 libxext6 -y
COPY requirements.txt requirements.txt
RUN /usr/local/bin/python3.11 -m pip install --upgrade pip
RUN pip3 install -r requirements.txt
RUN mkdir /app
WORKDIR /app


COPY pyproject.toml pyproject.toml
COPY poetry.lock poetry.lock
COPY confs ./
COPY utils/split_by_keys.py utils/split_by_keys.py

COPY core/ core

RUN mkdir data
RUN mkdir logs
COPY data/for_zero.csv data/for_zero.csv
COPY data/otgruzki.csv data/otgruzki.csv
COPY data/for_firsts.csv data/for_firsts.csv
COPY data/models data/models
COPY data/msgs_ei.csv data/msgs_ei.csv
COPY data/categories.csv data/categories.csv
COPY data/saves.csv data/saves.csv
COPY data/method2.csv data/method2.csv
COPY data/mats.csv data/mats.csv
COPY data/ygpt_keys.json data/ygpt_keys.json

RUN chmod -R g+rw /app
RUN poetry install --no-dev
CMD ["poetry", "python", "core/rabbitmq.py"]
