import xml.etree.ElementTree as ET
import re
import asyncio
import aio_pika
import base64
import json
from distance import Find_materials
from datetime import datetime
from functools import partial
from hash2text import text_from_hash
from split_by_keys import Key_words
import config as conf
# from config import connection_url, first_queue, second_queue

class Order_recognition():

    def __init__(self):
        self.find_mats = Find_materials()


    def write_logs(self, text, event=1):
        event = 'EVENT' if event == 1 else 'ERROR'
        date_time = datetime.now().astimezone()
        file_name = './logs/' + str(date_time.date()) + '.txt'
        log = open(file_name, 'a')
        log.write(str(date_time) + ' | ' + event + ' | ' + text + '\n')
        log.close()

    def consumer_test(self, hash:str=None, content:str=None):
        if content is None:
            content = text_from_hash(hash)
            print('Text - ', content, flush=True)
        kw = Key_words()
        clear_email = kw.find_key_words(content)
        # Отправляем распознаннaй текст(!) на поиск материалов
        print('Очищенное сообщение -', clear_email)
        results = str(self.find_mats.find_mats(clear_email))
        self.write_logs('results - ' + results, 1)
        print('results = ', results)
        # self.send_result(results)

    async def save_truth(self,
            msg: aio_pika.IncomingMessage):
        # используем контекстный менеджер для ack'а сообщения
        async with msg.process():
            content = msg.body
            if 'true_value' not in str(content):
                return
            self.write_logs('Получилось взять ответы МЕТОД 2', 1)
            print('Получилось взять ответы МЕТОД 2', flush=True)
            body = json.loads(content)
            print("METHOD 2 - ", body, flush=True)
            self.write_logs('METHOD 2 - ' + str(body), 1)
    async def consumer(self,
            msg: aio_pika.IncomingMessage,
            channel: aio_pika.RobustChannel,
    ):
        # используем контекстный менеджер для ack'а сообщения
        async with msg.process():
            print('Что-то получил из очереди rebbitmq...', flush=True)
            content = msg.body
            if 'true_value' in str(content):
                return
            self.write_logs('Получилось взять письмо из очереди', 1)
            print('Получилось взять письмо из очереди', flush=True)
            body = json.loads(content)
            self.write_logs('Body - ' + str(body), 1)
            content = text_from_hash(body['email'])
            # print('Text - ', content)
            kw = Key_words()
            clear_email = kw.find_key_words(content)
            # Отправляем распознанный текст(!) на поиск материалов
            print('Clear email - ', clear_email)
            results = str(self.find_mats.find_mats(clear_email))
            self.write_logs('results - ' + results, 1)
            print('results = ', results)
            # self.send_result(results)

            # проверяем, требует ли сообщение ответа
            if msg.reply_to:
                # отправляем ответ в default exchange
                print('Отправляем результат', flush=True)
                self.write_logs('Отправляем результaт', 1)
                await channel.default_exchange.publish(
                    message=aio_pika.Message(
                        content_type='application/json',
                        body=str.encode(results.replace("'", '"')[1:-1]),
                        # body=b'{"a":"b"}',
                        correlation_id=msg.correlation_id
                    ),
                    routing_key=msg.reply_to,  # самое важное

                )
    def get_message(self, body):
        body = json.loads(body)
        print(body)
        try:
            content = base64.standard_b64decode(base64.standard_b64decode(body['email']))\
                .decode('utf-8')
            root = ET.fromstring(content)
            content = root[0][0][2].text
            content = re.sub(r'\<.*?\>', '', content).replace('&nbsp;', '')
        except Exception as exc:
            self.write_logs('Письмо не читается,'+str(exc), 0)
            print('Error, письмо не читается,', exc)
            return 'Error while reading'
        return content

    async def main(self):
        connection = await aio_pika.connect_robust(
            conf.connection_url
        )


        async with connection:
            channel = await connection.channel()
            queue = await channel.declare_queue(conf.first_queue)
            # через partial прокидываем в наш обработчик сам канал
            await queue.consume(partial(self.consumer, channel=channel))
            print('Слушаем очередь', flush=True)


            queue2 = await channel.declare_queue(conf.second_queue)
            await queue2.bind(exchange=conf.exchange, routing_key=conf.routing_key)
            # через partial прокидываем в наш обработчик сам канал
            await queue2.consume(partial(self.save_truth))
            print('Слушаем очередь2', flush=True)
            try:
                await asyncio.Future()
            except Exception:
                pass

    def start(self):
        asyncio.run(self.main())

if __name__ == '__main__':
    order_rec = Order_recognition()
    order_rec.start()
