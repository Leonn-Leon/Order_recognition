import xml.etree.ElementTree as ET
import re
import os
import asyncio
import aio_pika
import base64
import json
from order_recognition.core.distance import Find_materials
from functools import partial
from order_recognition.core.hash2text import text_from_hash
from order_recognition.confs import config as conf
from order_recognition.utils import logger
from order_recognition.core.yandexgpt import custom_yandex_gpt
from order_recognition.utils.data_text_processing import Data_text_processing
from thread import Thread
from order_recognition.utils.split_by_keys import Key_words


class Order_recognition():

    def __init__(self):
        self.dp = Data_text_processing()
        if not os.path.exists("order_recognition/data/logs"):
            os.makedirs("order_recognition/data/logs")
        self.find_mats = Find_materials()

    def consumer_test(self, hash:str=None, content:str=None):
        if content is None:
            content = text_from_hash(hash)
        print('Text - ', content.split('\n'), flush=True)
        # self.test_analize_email(content)
        ygpt = custom_yandex_gpt()
        
        my_thread = Thread(target=self.test_analize_email, args=[ygpt, content])
        my_thread.start()
        
        my_thread.join()

    def test_analize_email(self, ygpt: custom_yandex_gpt, content):
        clear_email = ygpt.big_mail(content)
        # Отправляем распознаннaй текст(!) на поиск материалов
        print('Очищенные позиции -', clear_email)
        results = str(self.find_mats.paralell_rows(clear_email))
        logger.write_logs('results - ' + results, 1)
        print('results = ', results)
        # self.send_result(results)

    def save_truth_test(self, content):
        if 'true_value' not in str(content):
            return
        logger.write_logs('Получилось взять ответы МЕТОД 2', 1)
        print('Получилось взять ответы МЕТОД 2', flush=True)
        body = json.loads(content)
        print("METHOD 2 - ", body, flush=True)
        logger.write_logs('METHOD 2 - ' + str(body), 1)
        req_Number = body['req_number']
        if req_Number in self.find_mats.saves.index:
            positions = json.loads(self.find_mats.saves.loc[req_Number]['positions'].replace("'", '"'))['positions']
            true_positions = body['positions']
            for ind, pos in enumerate(true_positions):
                if int(pos['true_material']) == int(positions[int(pos['position_id'])]['material1_id']):
                    continue
                request_text = positions[int(pos['position_id'])]['request_text']
                val_ei = positions[int(pos['position_id'])]['value']
                ei = positions[int(pos['position_id'])]['ei']
                request_text, _, _ = self.dp.new_mat_prep(request_text, val_ei, ei)
                request_text = request_text.strip()
                try:
                    true_mat = self.find_mats.all_materials[self.find_mats.all_materials['Материал']. \
                        str.contains(str(int(pos['true_material'])))]['Полное наименование материала'].values[0]
                    true_first = self.find_mats.all_materials[self.find_mats.all_materials['Материал']
                                                              == (str(int(pos['true_material'])))][
                        'Название иерархии-1'].values[0]
                    true_zero = self.find_mats.all_materials[self.find_mats.all_materials['Материал']
                                                              == (str(int(pos['true_material'])))][
                        'Название иерархии-0'].values[0]
                    # true_mat = str(int(pos['true_material']))

                except Exception as exc:
                    logger.write_logs('Не нашёл такого материала ' + str(pos['true_material']) + ' ' + str(exc), event=0)
                    continue
                try:
                    print(self.find_mats.all_materials[self.find_mats.all_materials['Материал']
                                                       == (str(int(pos['true_material'])))])
                    print('Отправляем обучать !', flush=True)
                    logger.write_logs('Отправляем обучать ! ' + request_text + '|' + true_first)
                    self.find_mats.models.fit(request_text, true_first, true_zero, 0, 1)
                except Exception as exc:
                    logger.write_logs('Не смог обучить модельки для ' + str(pos['true_material']) + ' ' + str(exc),
                                    event=0)
                    continue

                if 'spec_mat' in pos.keys():
                    this_client_only = True if pos['spec_mat'] == 'X' else False
                else:
                    this_client_only = False
                res = str({'num_mat': str(int(pos['true_material'])),
                           'name_mat': true_mat,
                           'true_ei': pos['true_ei'],
                           'true_value': pos['true_value'],
                           'spec_mat': str(this_client_only)})
                res = base64.b64encode(bytes(res, 'utf-8'))
                # self.find_mats.method2.loc[request_text] = res.decode('utf-8')
                # print(self.find_mats.method2.index)
                self.find_mats.method2.loc[len(self.find_mats.method2.index)] = [request_text, res.decode('utf-8')]
            self.find_mats.method2.to_csv('order_recognition/data/method2.csv', index=False)
        else:
            logger.write_logs('Не нашёл такого письма', event=0)
            print('Не нашёл такого письма', flush=True)
        print("Метод 2 всё", flush=True)

    async def save_truth(self,
            msg: aio_pika.IncomingMessage):
        # используем контекстный менеджер для ack'а сообщения
        async with msg.process():
            content = msg.body
            if 'true_value' not in str(content):
                return
            logger.write_logs('Получилось взять ответы МЕТОД 2', 1)
            print('Получилось взять ответы МЕТОД 2', flush=True)
            body = json.loads(content)
            print("METHOD 2 - ", body, flush=True)
            logger.write_logs('METHOD 2 - ' + str(body), 1)
            req_Number = body['req_number']
            if req_Number in self.find_mats.saves.index:
                positions = json.loads(self.find_mats.saves.loc[req_Number]['positions'].replace("'", '"'))['positions']
                true_positions = body['positions']
                for ind, pos in enumerate(true_positions):
                    if int(pos['true_material']) == int(positions[int(pos['position_id'])]['material1_id']):
                        continue

                    request_text = positions[int(pos['position_id'])]['request_text']
                    val_ei = positions[int(pos['position_id'])]['value']
                    ei = positions[int(pos['position_id'])]['ei']
                    request_text, _, _ = self.dp.new_mat_prep(request_text, val_ei, ei)
                    request_text = request_text.strip()
                    try:
                        fit_zero, fit_first = True, True
                        true_mat = self.find_mats.all_materials[self.find_mats.all_materials['Материал']. \
                            str.contains(str(int(pos['true_material'])))]['Полное наименование материала'].values[0]
                        true_first = self.find_mats.all_materials[self.find_mats.all_materials['Материал']
                                                                  == (str(int(pos['true_material'])))][
                            'Название иерархии-1'].values[0]
                        true_zero = self.find_mats.all_materials[self.find_mats.all_materials['Материал']
                                                                 == (str(int(pos['true_material'])))][
                            'Название иерархии-0'].values[0]
                        if self.find_mats.all_materials[self.find_mats.all_materials['Материал']
                                                == (str(int(positions[int(pos['position_id'])]['material1_id'])))][
                            'Название иерархии-0'].values[0] == true_zero:
                            fit_zero = False
                        if self.find_mats.all_materials[self.find_mats.all_materials['Материал']
                                                == (str(int(positions[int(pos['position_id'])]['material1_id'])))][
                            'Название иерархии-1'].values[0] == true_first:
                            fit_first = False
                        # true_mat = str(int(pos['true_material']))

                    except Exception as exc:
                        logger.write_logs('Не нашёл такого материала ' + str(pos['true_material']) + ' ' + str(exc),
                                        event=0)
                        continue
                    try:
                        print(self.find_mats.all_materials[self.find_mats.all_materials['Материал']
                                                           == (str(int(pos['true_material'])))])
                        print('Отправляем обучать !', flush=True)
                        logger.write_logs('Отправляем обучать ! ' + request_text + '|' + true_first)
                        self.find_mats.models.fit(request_text, true_first, true_zero, fit_zero, fit_first)
                    except Exception as exc:
                        logger.write_logs('Не смог обучить модельки для ' + str(pos['true_material']) + ' ' + str(exc),
                                        event=0)
                        continue

                    if 'spec_mat' in pos.keys():
                        this_client_only = True if pos['spec_mat'] == 'X' else False
                    else:
                        this_client_only = False
                    res = str({'num_mat': str(int(pos['true_material'])),
                               'name_mat': true_mat,
                               'true_ei': pos['true_ei'],
                               'true_value': pos['true_value'],
                               'spec_mat': str(this_client_only)})
                    res = base64.b64encode(bytes(res, 'utf-8'))
                    # self.find_mats.method2.loc[request_text] = res.decode('utf-8')
                    # print(self.find_mats.method2.index)
                    self.find_mats.method2.loc[len(self.find_mats.method2.index)] = [request_text, res.decode('utf-8')]
                self.find_mats.method2.to_csv('order_recognition/data/method2.csv', index=False)
            else:
                logger.write_logs('Не нашёл такого письма', event=0)
                print('Не нашёл такого письма', flush=True)
            print("Метод 2 всё", flush=True)

    def start_analize_email(self, content, msg, channel):
        """
        Метод для анализа письма и отправки результата

        Args:
            content (_type_): 
            msg (_type_): 
            channel (_type_): 
        """
        print('Начало потока!', flush=True)
        ygpt = custom_yandex_gpt()
        clear_email = ygpt.big_mail(content)
        # Отправляем распознанный текст(!) на поиск материалов
        print('Clear email - ', clear_email)
        results = str(self.find_mats.paralell_rows(clear_email))
        logger.write_logs('results - ' + results, 1)
        print('results = ', results)
        # self.send_result(results)
        # проверяем, требует ли сообщение ответа
        if msg.reply_to:
            # отправляем ответ в default exchange
            print('Отправляем результат', flush=True)
            logger.write_logs('Отправляем результaт', 1)
            asyncio.run(channel.default_exchange.publish(
                message=aio_pika.Message(
                    content_type='application/json',
                    body=str.encode(results.replace("'", '"')[1:-1]),
                    # body=b'{"a":"b"}',
                    correlation_id=msg.correlation_id
                ),
                routing_key=msg.reply_to,  # самое важное

            ))
        print('Конец!', flush=True)

    async def consumer(self,
            msg: aio_pika.IncomingMessage,
            channel: aio_pika.RobustChannel,
    ):
        """
        Обрабатываем сообщение из очереди rebbitmq

        Args:
            msg (aio_pika.IncomingMessage): сообщение из очереди rebbitmq
            channel (aio_pika.RobustChannel): контекстный менеджер для ack'а сообщения
        """
        # используем контекстный менеджер для ack'а сообщения
        async with msg.process():
            print('Что-то получил из очереди rebbitmq...', flush=True)
            content = msg.body
            if 'true_value' in str(content):
                return
            logger.write_logs('Получилось взять письмо из очереди', 1)
            print('Получилось взять письмо из очереди', flush=True)
            body = json.loads(content)
            logger.write_logs('Body - ' + str(body), 1)
            if len(body['email']) == 0:
                print('Письмо пустое!!!', flush=True)
                logger.write_logs('Письмо пустое!!!', 1)
            content = text_from_hash(body['email'])
            my_thread = Thread(target=self.start_analize_email, args=[content, msg, channel])
            my_thread.start()
            # my_thread.join()

    def get_message(self, body):
        """
        Получаем письмо из очереди и возвращаем его в виде строки
        """
        body = json.loads(body)
        print(body)

        try:
            content = base64.standard_b64decode(base64.standard_b64decode(body['email']))\
                .decode('utf-8')
            root = ET.fromstring(content)
            content = root[0][0][2].text
            content = re.sub(r'\<.*?\>', '', content).replace('&nbsp;', '')
        except Exception as exc:
            logger.write_logs('Письмо не читается,'+str(exc), 0)
            print('Error, письмо не читается,', exc)
            return 'Error while reading'
        return content

    async def main(self):
        """
        Подключаемся к брокеру, объявляем очередь,
        подписываемся на неё и ждем сообщений.
        
        """
        connection = await aio_pika.connect_robust(
            conf.connection_url
        )


        async with connection:
            channel = await connection.channel()
            queue = await channel.declare_queue(conf.first_queue, timeout=60000)
            await queue.bind(exchange=conf.exchange, routing_key=conf.routing_key, timeout=10000)
            # через partial прокидываем в наш обработчик сам канал
            await queue.consume(partial(self.consumer, channel=channel), timeout=60000)
            print('Слушаем очередь', flush=True)


            queue2 = await channel.declare_queue(conf.second_queue, timeout=10000)
            await queue2.bind(exchange=conf.exchange, routing_key=conf.routing_key2, timeout=10000)
            # через partial прокидываем в наш обработчик сам канал
            await queue2.consume(partial(self.save_truth), timeout=10000)
            print('Слушаем очередь 2', flush=True)
            
            # Эту очередь просто создаю и не слушаю
            queue3 = await channel.declare_queue(conf.third_queue, timeout=10000)
            await queue3.bind(exchange=conf.exchange, routing_key=conf.routing_key3, timeout=10000)
            
            try:
                await asyncio.Future()
            except Exception:
                pass

    def start(self):
        asyncio.run(self.main())

if __name__ == '__main__':
    # os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..', 'templates'))
    Key_words()
    order_rec = Order_recognition()
    print("RMQ_AI_URL:", conf.connection_url[:4])
    if conf.connection_url == "TEST" or conf.connection_url == "RMQ_AI_URL":
        # order_rec.save_truth_test('{"req_number": "0f604ddf-8e06-4ed1-9406-6ca769962250", "mail_code": "0061540478", "user": "SHARIPOVDI", "positions": [{"position_id": "0", "true_material": "000000000000005832", "true_ei": "", "true_value": "12.000", "spec_mat": ""}, {"position_id": "1", "true_material": "000000000000007927", "true_ei": "", "true_value": "12.000", "spec_mat": ""}, {"position_id": "2", "true_material": "000000000000007903", "true_ei": "", "true_value": "12.000", "spec_mat": ""}, {"position_id": "3", "true_material": "000000000000005793", "true_ei": "", "true_value": "12.000", "spec_mat": ""}, {"position_id": "4", "true_material": "000000000000005797", "true_ei": "", "true_value": "12.000", "spec_mat": ""}, {"position_id": "5", "true_material": "000000000000088877", "true_ei": "", "true_value": "12.000", "spec_mat": ""}, {"position_id": "6", "true_material": "000000000000069270", "true_ei": "", "true_value": "6.000", "spec_mat": ""}, {"position_id": "7", "true_material": "000000000000008362", "true_ei": "М", "true_value": "12.000", "spec_mat": ""}]}')
        hash = "ZXlKaWRXTnJaWFJPWVcxbElqb2lZM0p0TFdWdFlXbHNJaXdpYjJKcVpXTjBUbUZ0WlNJNkltMXpaMTgxWXpKak5UWTBORFF4TVdNd01EWXhOamt6TURFNVlXUTNaR1JsTW1VMVpTSXNJbVpwYkdWRGIyNTBaVzUwSWpvaTBKZlF0TkdBMExEUXN0R0IwWUxRc3RHRDBMblJndEMxTEZ4eVhHNWNjbHh1MEpyUXN0Q3cwTFRSZ05DdzBZSWdOakFnMFlIUmdqTWdOdENjSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ050QzhYSEpjYnRDYTBZRFJnOUN6SURFeUlOR0IwWUl1TVRBdE1qQWdJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnTnpMUXZGeHlYRzdRbXRHQTBZUFFzeUF5TUNEUmdkR0NNOUMvMFlFMUw5R0IwTDgxSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnSUNBek50QzhYSEpjYnRDYTBZRFJnOUN6SURJMUxkQ1NJTkdCMFlJejBML1JnVFV2MFlIUXZ6VWcwSlBRbnRDaDBLSWdNalU1TUMwNE9DQWdJQ0FnSUNBZ0lDQWdJQ0FnTVRMUXZGeHlYRzdRbXRHQTBZUFFzeUF6TmlEUmdkR0NNOUMvMFlFdjBZSFF2eUFnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnSUNBMjBMeGNjbHh1MEpyUmdOR0QwTE1nTmpBZzBZSFJnaTR5TUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0EyMEx4Y2NseHUwSnZRdU5HQjBZSWdNVEFnMFlIUmdqUFF2OUdCTlMvUmdkQy9OU0RSZ05DKzBMelFzU0RRa2kzUW1pRFFrOUNlMEtIUW9pQTROVFk0TFRjM0lDQWdJQ0FnSURFdU5kR0ZNeTQxMEx4Y2NseHUwSnZRdU5HQjBZSWdNVFFnMFlIUmdqUFF2OUdCTlMvUmdkQy9OU0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnTVM0MTBZVTJJREhSaU5HQ1hISmNidENiMExqUmdkR0NJRElnMFlIUmdpNHowTC9SZ1RVdjBZSFF2elVnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnSURFdU1qWFJoVEl1TlNBeTBZalJnbHh5WEc3UW05QzQwWUhSZ2lBMElOR0IwWUl6MEwvUmdUVXYwWUhRdnpVZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQXhMalhSaFRZZ005R0kwWUpjY2x4dTBLTFJnTkdEMExIUXNDQXhNRGpSaFRFd0lOR0IwWUl1TURuUWt6TFFvU0RRazlDZTBLSFFvaUF6TWpVeU9DMHlNREV6SUNBZ0lDQWdJQ0FnSURYUXZGeHlYRzVjY2x4dTBLTFJnTkdEMExIUXNDQXhNelBSaFRZZzBLSFJnaTR6MFlIUXZ6VWcwSlBRbnRDaDBLSWdPRGN6TWkwM09DQWdJQ0FnSUNBZ0lDQWdJQ0FnSURJdU5kQzhYSEpjYnRDaTBZRFJnOUN4MExBZ01UVTUwWVV4TWlEUW9kR0NMalBSZ2RDL05TRFFrOUNlMEtIUW9pQTROek15TFRjNElDQWdJQ0FnSUNBZ0lDQWdJQ0F6MEx4Y2NseHUwS0xSZ05HRDBMSFFzQ0F5TVRuUmhUZ2cwWUhSZ2k0d09kQ1RNdENoSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0F5Tk5DOFhISmNibHh5WEc3UW90R0EwWVBRc2RDd0lESTNNOUdGT0NEUmdkR0NMakl3SU5DVDBKN1FvZENpSURnM016SXROemdnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdNOUM4WEhKY2J0Q2kwWURSZzlDeDBMQWdNekkxMFlVeE1DRFJnZEdDTGpBNTBMTXkwWUVnMEpQUW50Q2gwS0lnT0Rjek1pMDNPQ0FnSUNBZ0lDQWdJQ0FnSURUUXZGeHlYRzdRb3RHQTBZUFFzZEN3SURjMjBZVTBMalVnMFlIUmdpNHlNQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0F5MEx4Y2NseHUwS0xSZ05HRDBMSFFzQ0E0TWpEUmhURXdJTkdCMFlJdU1EblFzekxSZ1NEUWs5Q2UwS0hRb2lBeE1EY3dOaTAzTmlBZ0lDQWdJQ0FnSUNBZ050QzhYSEpjYnRDaTBZRFJnOUN4MExBZ09EblJoVFVnMFlIUmdpNHlNQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnSURFeTBMeGNjbHh1MEtQUXM5QyswTHZRdnRDNklERXdNTkdGTVRBdzBZVXhNQ0RSZ2RHQ005Qy8wWUUxTDlHQjBMODFJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdNVGpRdkZ4eVhHN1FvOUN6MEw3UXU5QyswTG9nTWpEUmhUSXcwWVUwSU5HQjBZSXpJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJREV5MEx4Y2NseHUwS1BRczlDKzBMdlF2dEM2SURNdzBZVXpNTkdGTXlEUmdkR0NNOUMvMFlFeklOQ1QwSjdRb2RDaUlEZzFNRGt0T1RNZ0lDQWdJQ0FnSUNBZ0lDQTIwTHhjY2x4dTBLUFFzOUMrMEx2UXZ0QzZJRFExMFlVME5kR0ZNeURSZ2RHQ005Qy8wWUUxTDlHQjBMODFJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnTVRMUXZGeHlYRzdRbzlDejBMN1F1OUMrMExvZ05EWFJoVFExMFlVMElOR0IwWUl6MEwvUmdUVXYwWUhRdnpVZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQTIwTHhjY2x4dTBLUFFzOUMrMEx2UXZ0QzZJRFExMFlVME5kR0ZOU0RSZ2RHQ005Qy8wWUUxTDlHQjBMODFJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnTnRDOFhISmNidENqMExQUXZ0QzcwTDdRdWlBMU1OR0ZOVERSaFRNZzBZSFJnalBRdjlHQk5TL1JnZEMvTlNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lESTAwTHhjY2x4dTBLUFFzOUMrMEx2UXZ0QzZJRFV3MFlVMU1OR0ZOU0RSZ2RHQ005Qy8wWUUxTDlHQjBMODFJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnTWpUUXZGeHlYRzdRbzlDejBMN1F1OUMrMExvZ05qUFJoVFl6MFlVMUlOR0IwWUl6MEwvUmdUVXYwWUhRdnpVZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQXhNdEM4WEhKY2J0Q2owTFBRdnRDNzBMN1F1aUEzTU5HRk56RFJoVGNnMFlIUmdqUFF2OUdCTlMvUmdkQy9OU0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnSURVMDBMeGNjbHh1MEtQUXM5QyswTHZRdnRDNklEa3cwWVU1TU5HRk5pRFJnZEdDTTlDLzBZRTFMOUdCMEw4MUlDQWdJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdNVExRdkZ4eVhHN1FxTkN5MExYUXU5QzcwTFhSZ0NBeE1OQy9JTkdCMFlJejBML1JnVFV2MFlIUXZ6VWdJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnSUNBeE10QzhYSEpjYnRDbzBMTFF0ZEM3MEx2UXRkR0FJREV5MFlNZzBZSFJnalBRdjlHQk5TL1JnZEMvTlNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJREV5MEx4Y2NseHUwS2pRc3RDMTBMdlF1OUMxMFlBZ01UYlJneURSZ2RHQ005Qy8wWUUxTDlHQjBMODFJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQTUwWWpSZ2lEUXY5QytJREV5MEx4Y2NseHUwS2pRc3RDMTBMdlF1OUMxMFlBZ01qVFJneUF4TXRDOElOR0IwWUl6MEwvUmdUVXYwWUhRdnpVZ0lDQWdJQ0FnSUNBZ0lDQWdNOUdJMFlJZzBML1F2aUF4TXRDOFhISmNidENvMExMUXRkQzcwTHZRdGRHQUlETXcwWU1nMFlIUmdqUFF2OUdCTlMvUmdkQy9OU0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lERXkwTHhjY2x4dTBLalFzdEMxMEx2UXU5QzEwWUFnTmk0MTBMOGcwWUhSZ2pQUXY5R0JOUy9SZ2RDL05TQWdJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnTVRMUXZGeHlYRzdRcU5DeTBMWFF1OUM3MExYUmdDQTJMalhSZ3lEUmdkR0NNOUMvMFlFMUw5R0IwTDgxSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQXlOTkM4WEhKY2J0Q28wTFhSZ2RHQzBMalFzOUdBMExEUXZkQzkwTGpRdWlBeE55RFJnZEdDTGpFd0xUSXdJQ0FnSUNBZ0lDQWdJQ0FnSUNBZ0lDQWdJQ0FnSURJMDBMeGNjbHh1WEhKY2J0Q2hJTkdEMExMUXNOQzIwTFhRdmRDNDBMWFF2Q3hjY2x4dVhISmNidENhMEw3UmdOQyswWUxRdXRDKzBMSWcwSjNRdU5DNjBMN1F1OUN3MExrdVhISmNiajA5UFQwOVBUMDlQVDA5UFQwOVBUMDlQVDA5UFQwOVBUMDlQVDA5UFQwOVBUMDlYSEpjYnRDZTBKN1FuaUJjSXRDWTBMM1F0dEMxMEwzUXRkR0EwTDNRc05HUElOQ2EwTDdRdk5DLzBMRFF2ZEM0MFk4Z1hDTFFvOUM5MExqUXY5R0EwTDdRdkZ3aVhISmNiajA5UFQwOVBUMDlQVDA5UFQwOVBUMDlQVDA5UFQwOVBUMDlQVDA5UFQwOVBUMDlYSEpjYnRDYzBMN1FzUzRnMFlMUXRkQzdMaUFyTnpreE1qWXpNRGM1TVRKY2NseHVQVDA5UFQwOVBUMDlQVDA5UFQwOVBUMDlQVDA5UFQwOVBUMDlQVDA5UFQwOVBUMWNjbHh1VTJ0NWNHVWdjMnQ1YTI5eWIzUnJiM1pjY2x4dVBUMDlQVDA5UFQwOVBUMDlQVDA5UFQwOVBUMDlQVDA5UFQwOVBUMDlQVDA5UFQxY2NseHUwS0hRc05DNTBZSWdWVzVwY0hKdmJTNXdjbTljY2x4dVhISmNiaUo5"
        # while True:    
        order_rec.consumer_test(hash=hash) # Выполняется паралельно но поставил заглушку
        #     hash = input("Введи hash:\n")
    else:
        order_rec.start()