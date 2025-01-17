FROM python:3.11.4

ENV http_proxy="http://vproxy2.spk.ru:3128"
ENV https_proxy="http://vproxy2.spk.ru:3128"

RUN apt-get update
RUN apt-get upgrade -y
RUN apt-get install ffmpeg libsm6 libxext6 -y
COPY requirements.txt requirements.txt
RUN /usr/local/bin/python3.11 -m pip install --upgrade pip
RUN pip3 install -r requirements.txt

# COPY pyproject.toml pyproject.toml
# COPY poetry.lock poetry.lock
# RUN poetry install --no-dev

# RUN mkdir /app
# WORKDIR /app

COPY order_recognition/ ./order_recognition/

RUN chmod -R g+rw /order_recognition
CMD ["poetry", "python", "order_recognition/core/rabbitmq.py"]
