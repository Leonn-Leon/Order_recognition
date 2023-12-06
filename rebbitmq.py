import xml.etree.ElementTree as ET
import re
import pika
import asyncio
import aio_pika
import base64
import json
from distance import Find_materials
from datetime import datetime
from functools import partial
import time

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

    async def consumer(self,
            msg: aio_pika.IncomingMessage,
            channel: aio_pika.RobustChannel,
    ):
        # используем контекстный менеджер для ack'а сообщения
        async with msg.process():
            self.write_logs('Получилось взять письмо из очереди', 1)
            print('Получилось взять письмо из очереди')
            content = self.get_message(msg.body)
            self.write_logs('content - ' + content, 1)
            print('content - ', content)
            # Отправляем распознанный текст(!) на поиск материалов
            results = str(self.find_mats.find_mats(content.split('\n')))
            self.write_logs('results - ' + results, 1)
            print('results = ', results)
            # self.send_result(results)

            # проверяем, требует ли сообщение ответа
            if msg.reply_to:
                # отправляем ответ в default exchange
                print('Отправляем результат')
                self.write_logs('Отправляем результат', 1)
                await channel.default_exchange.publish(
                    message=aio_pika.Message(
                        body=str.encode(results),
                        correlation_id=msg.correlation_id,
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
            "amqp://ai:XRKh02eFLTKjMJErcpoy@esb-dev-rmq01.spk.ru:5672/"
        )

        queue_name = "get_message"

        async with connection:
            channel = await connection.channel()
            queue = await channel.declare_queue(queue_name)
            # через partial прокидываем в наш обработчик сам канал
            await queue.consume(partial(self.consumer, channel=channel))
            print('Слушаем очередь')
            try:
                await asyncio.Future()
            except Exception:
                pass
    def start(self):
        asyncio.run(self.main())

if __name__ == '__main__':
    oreder_rec = Order_recognition()
    oreder_rec.start()