import pika
import base64
import json
from distance import Find_materials

class Order_recognition():

    def __init__(self):
        # Параметры подключения
        connection_params = pika.ConnectionParameters(
            host='esb-dev-rmq01.spk.ru',
            port=5672,
            virtual_host='/',
            credentials=pika.PlainCredentials(
                username='ai',
                password='XRKh02eFLTKjMJErcpoy'
            )
        )

        # Установка соединения
        connection = pika.BlockingConnection(connection_params)

        # Создание канала
        self.channel = connection.channel()

    def send_result(self, message='[{"req_Number": "5622e8f9-4c08-4659-87f4-a9679c6f70a8", "positions": [{"position_id": "0", "request_text": "уголок ст3 90 90 7 ", "ei": "шт", "value": "5.0", "material1_id": "9359", "material2_id": "9360", "material3_id": "81264", "material4_id": "9361", "material5_id": "76658"}, {"position_id": "1", "request_text": "швеллер гнутый 140 60 4 12 ", "ei": "шт", "value": "5.0", "material1_id": "84537", "material2_id": "6368", "material3_id": "107858", "material4_id": "98844", "material5_id": "106878"}, {"position_id": "2", "request_text": "швеллер гнутый 100 50 4 12 м ", "ei": "шт", "value": "5.0", "material1_id": "116489", "material2_id": "6613", "material3_id": "101959", "material4_id": "86777", "material5_id": "6331"}, {"position_id": "3", "request_text": "труба проф 60 60 2 ", "ei": "шт", "value": "5.0", "material1_id": "80823", "material2_id": "83288", "material3_id": "8200", "material4_id": "86689", "material5_id": "99431"}, {"position_id": "4", "request_text": "труба проф 60 40 2", "ei": "шт", "value": "5.0", "material1_id": "100075", "material2_id": "77463", "material3_id": "99130", "material4_id": "8187", "material5_id": "86504"}, {"position_id": "5", "request_text": "труба проф 60 40 3", "ei": "шт", "value": "5.0", "material1_id": "108078", "material2_id": "78975", "material3_id": "8191", "material4_id": "86727", "material5_id": "99430"}, {"position_id": "6", "request_text": "труба проф 40 40 2", "ei": "шт", "value": "5.0", "material1_id": "26242", "material2_id": "78910", "material3_id": "83433", "material4_id": "26243", "material5_id": "26244"}, {"position_id": "7", "request_text": "труба проф 40 20 2", "ei": "шт", "value": "5.0", "material1_id": "82902", "material2_id": "26238", "material3_id": "74728", "material4_id": "8120", "material5_id": "86889"}, {"position_id": "8", "request_text": "труба проф 40 20 20", "ei": "шт", "value": "5.0", "material1_id": "82902", "material2_id": "26238", "material3_id": "74728", "material4_id": "8120", "material5_id": "86889"}, {"position_id": "9", "request_text": "лист 3 1250 2500 ", "ei": "шт", "value": "5.0", "material1_id": "16642", "material2_id": "16644", "material3_id": "16769", "material4_id": "16770", "material5_id": "90872"}, {"position_id": "10", "request_text": "лист рифленый 4 чечевицa ", "ei": "шт", "value": "5.0", "material1_id": "105114", "material2_id": "25354", "material3_id": "105113", "material4_id": "97339", "material5_id": "96818"}, {"position_id": "11", "request_text": "труба вгп 32 3,2 ", "ei": "шт", "value": "3.0", "material1_id": "96547", "material2_id": "26227", "material3_id": "111892", "material4_id": "7250", "material5_id": "89126"}]}]'):
        self.channel.basic_publish(
            exchange='ai', routing_key='orderrecognition.find_request_result', body=message)
        print('Отправил результат')

    def get_message(self, ch, method, properties, body):
        print('Получилось взять письмо из очереди')
        order_data = body.decode('utf-8')
        body = json.loads(body)
        print(body)
        content = base64.standard_b64decode(base64.standard_b64decode(body['email'])).decode('utf-8')\
              .split('<fileContent>')[1]\
              .split('</fileContent>')[0]
        print(content)
        # results = self.find_mats.find_mats(content.split('\n'))
        results = self.find_mats.find_mats(content.split('&#xd;'))
        print('results = ', results)
        # self.send_result()
        self.send_result(results)

    def start(self):
        # channel.queue_declare(queue='Excchange')
        self.channel.exchange_declare(exchange='ai', exchange_type='topic', durable=True)
        self.channel.queue_declare(queue='get_message')
        self.channel.queue_bind(
                exchange='ai', queue='get_message', routing_key='orderrecognition.find_request')

        self.channel.basic_consume(
            queue='get_message', on_message_callback=self.get_message, auto_ack=True)
        self.find_mats = Find_materials()
        print('Подключение прошло успешно, слушаем очередь')
        self.channel.start_consuming()