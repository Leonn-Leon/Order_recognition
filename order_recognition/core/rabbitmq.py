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
from order_recognition.utils import data_text_processing as dp
from thread import Thread
from order_recognition.utils.split_by_keys import Key_words


class Order_recognition():

    def __init__(self):
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
                request_text, _, _ = dp.new_mat_prep(request_text, val_ei, ei)
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
                    request_text, _, _ = dp.new_mat_prep(request_text, val_ei, ei)
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
        hash = "ZXlKaWRXTnJaWFJPWVcxbElqb2lZM0p0TFdWdFlXbHNJaXdpYjJKcVpXTjBUbUZ0WlNJNkltMXpaMTh5TlRNNE1ERmxZVE5pWTJFeE1EVTVNREpsT0dJMU1XWTRNakpsWWpWbVlTSXNJbVpwYkdWRGIyNTBaVzUwSWpvaVhHNDhTRlJOVEQ0OFFrOUVXVDQ4WkdsMlB0Q1UwTDdRc2RHQTBZdlF1U0RRdE5DMTBMM1JqQ0U4WEM5a2FYWStQR1JwZGo0OFpHbDJJSE4wZVd4bFBWd2lMWGRsWW10cGRDMW1iMjUwTFhOdGIyOTBhR2x1WnpwaGJuUnBZV3hwWVhObFpEc2dMWGRsWW10cGRDMTBaWGgwTFhOMGNtOXJaUzEzYVdSMGFEb3djSGc3SUdKaFkydG5jbTkxYm1RdFkyOXNiM0k2STJZMVpqVm1OVHNnWW05eVpHVnlPakJ3ZURzZ1kyOXNiM0k2SXpNMk0ySTBORHNnWm05dWRDMW1ZVzFwYkhrNkpuRjFiM1E3VUZRZ1UyRnVjeVp4ZFc5ME95eEJjbWxoYkN4ellXNXpMWE5sY21sbU95Qm1iMjUwTFdabFlYUjFjbVV0YzJWMGRHbHVaM002YVc1b1pYSnBkRHNnWm05dWRDMXJaWEp1YVc1bk9tbHVhR1Z5YVhRN0lHWnZiblF0YjNCMGFXTmhiQzF6YVhwcGJtYzZhVzVvWlhKcGREc2dabTl1ZEMxemFYcGxMV0ZrYW5WemREcHBibWhsY21sME95Qm1iMjUwTFhOcGVtVTZNVFZ3ZURzZ1ptOXVkQzF6ZEhKbGRHTm9PbWx1YUdWeWFYUTdJR1p2Ym5RdGMzUjViR1U2Ym05eWJXRnNPeUJtYjI1MExYWmhjbWxoYm5RdFlXeDBaWEp1WVhSbGN6cHBibWhsY21sME95Qm1iMjUwTFhaaGNtbGhiblF0WTJGd2N6cHViM0p0WVd3N0lHWnZiblF0ZG1GeWFXRnVkQzFsWVhOMExXRnphV0Z1T21sdWFHVnlhWFE3SUdadmJuUXRkbUZ5YVdGdWRDMWxiVzlxYVRwcGJtaGxjbWwwT3lCbWIyNTBMWFpoY21saGJuUXRiR2xuWVhSMWNtVnpPbTV2Y20xaGJEc2dabTl1ZEMxMllYSnBZVzUwTFc1MWJXVnlhV002YVc1b1pYSnBkRHNnWm05dWRDMTJZWEpwWVc1MExYQnZjMmwwYVc5dU9tbHVhR1Z5YVhRN0lHWnZiblF0ZG1GeWFXRjBhVzl1TFhObGRIUnBibWR6T21sdWFHVnlhWFE3SUdadmJuUXRkMlZwWjJoME9qUXdNRHNnYkdWMGRHVnlMWE53WVdOcGJtYzZibTl5YldGc095QnNhVzVsTFdobGFXZG9kRG95TUhCNE95QnRZWEpuYVc0dFltOTBkRzl0T2pBN0lHMWhjbWRwYmkxc1pXWjBPakE3SUcxaGNtZHBiaTF5YVdkb2REb3dPeUJ0WVhKbmFXNHRkRzl3T2pBN0lHOXljR2hoYm5NNk1qc2diM1YwYkdsdVpUcHViMjVsT3lCdmRtVnlabXh2ZHkxM2NtRndPbUp5WldGckxYZHZjbVE3SUhCaFpHUnBibWM2TUhCNE95QjBaWGgwTFdGc2FXZHVPbk4wWVhKME95QjBaWGgwTFdSbFkyOXlZWFJwYjI0dFkyOXNiM0k2YVc1cGRHbGhiRHNnZEdWNGRDMWtaV052Y21GMGFXOXVMWE4wZVd4bE9tbHVhWFJwWVd3N0lIUmxlSFF0WkdWamIzSmhkR2x2YmkxMGFHbGphMjVsYzNNNmFXNXBkR2xoYkRzZ2RHVjRkQzFwYm1SbGJuUTZNSEI0T3lCMFpYaDBMWEpsYm1SbGNtbHVaenBuWlc5dFpYUnlhV053Y21WamFYTnBiMjQ3SUhSbGVIUXRkSEpoYm5ObWIzSnRPbTV2Ym1VN0lIWmxjblJwWTJGc0xXRnNhV2R1T21KaGMyVnNhVzVsT3lCM2FHbDBaUzF6Y0dGalpUcHViM0p0WVd3N0lIZHBaRzkzY3pveU95QjNiM0prTFdKeVpXRnJPbUp5WldGckxYZHZjbVE3SUhkdmNtUXRjM0JoWTJsdVp6b3djSGhjSWo0eExpRFFxTkN5MExYUXU5QzcwTFhSZ0NBeE1pMHhPQ0RSaU5HQ0xURXlJTkM4UEZ3dlpHbDJQanhrYVhZZ2MzUjViR1U5WENJdGQyVmlhMmwwTFdadmJuUXRjMjF2YjNSb2FXNW5PbUZ1ZEdsaGJHbGhjMlZrT3lBdGQyVmlhMmwwTFhSbGVIUXRjM1J5YjJ0bExYZHBaSFJvT2pCd2VEc2dZbUZqYTJkeWIzVnVaQzFqYjJ4dmNqb2paalZtTldZMU95QmliM0prWlhJNk1IQjRPeUJqYjJ4dmNqb2pNell6WWpRME95Qm1iMjUwTFdaaGJXbHNlVG9tY1hWdmREdFFWQ0JUWVc1ekpuRjFiM1E3TEVGeWFXRnNMSE5oYm5NdGMyVnlhV1k3SUdadmJuUXRabVZoZEhWeVpTMXpaWFIwYVc1bmN6cHBibWhsY21sME95Qm1iMjUwTFd0bGNtNXBibWM2YVc1b1pYSnBkRHNnWm05dWRDMXZjSFJwWTJGc0xYTnBlbWx1WnpwcGJtaGxjbWwwT3lCbWIyNTBMWE5wZW1VdFlXUnFkWE4wT21sdWFHVnlhWFE3SUdadmJuUXRjMmw2WlRveE5YQjRPeUJtYjI1MExYTjBjbVYwWTJnNmFXNW9aWEpwZERzZ1ptOXVkQzF6ZEhsc1pUcHViM0p0WVd3N0lHWnZiblF0ZG1GeWFXRnVkQzFoYkhSbGNtNWhkR1Z6T21sdWFHVnlhWFE3SUdadmJuUXRkbUZ5YVdGdWRDMWpZWEJ6T201dmNtMWhiRHNnWm05dWRDMTJZWEpwWVc1MExXVmhjM1F0WVhOcFlXNDZhVzVvWlhKcGREc2dabTl1ZEMxMllYSnBZVzUwTFdWdGIycHBPbWx1YUdWeWFYUTdJR1p2Ym5RdGRtRnlhV0Z1ZEMxc2FXZGhkSFZ5WlhNNmJtOXliV0ZzT3lCbWIyNTBMWFpoY21saGJuUXRiblZ0WlhKcFl6cHBibWhsY21sME95Qm1iMjUwTFhaaGNtbGhiblF0Y0c5emFYUnBiMjQ2YVc1b1pYSnBkRHNnWm05dWRDMTJZWEpwWVhScGIyNHRjMlYwZEdsdVozTTZhVzVvWlhKcGREc2dabTl1ZEMxM1pXbG5hSFE2TkRBd095QnNaWFIwWlhJdGMzQmhZMmx1WnpwdWIzSnRZV3c3SUd4cGJtVXRhR1ZwWjJoME9qSXdjSGc3SUcxaGNtZHBiaTFpYjNSMGIyMDZNRHNnYldGeVoybHVMV3hsWm5RNk1Ec2diV0Z5WjJsdUxYSnBaMmgwT2pBN0lHMWhjbWRwYmkxMGIzQTZNRHNnYjNKd2FHRnVjem95T3lCdmRYUnNhVzVsT201dmJtVTdJRzkyWlhKbWJHOTNMWGR5WVhBNlluSmxZV3N0ZDI5eVpEc2djR0ZrWkdsdVp6b3djSGc3SUhSbGVIUXRZV3hwWjI0NmMzUmhjblE3SUhSbGVIUXRaR1ZqYjNKaGRHbHZiaTFqYjJ4dmNqcHBibWwwYVdGc095QjBaWGgwTFdSbFkyOXlZWFJwYjI0dGMzUjViR1U2YVc1cGRHbGhiRHNnZEdWNGRDMWtaV052Y21GMGFXOXVMWFJvYVdOcmJtVnpjenBwYm1sMGFXRnNPeUIwWlhoMExXbHVaR1Z1ZERvd2NIZzdJSFJsZUhRdGNtVnVaR1Z5YVc1bk9tZGxiMjFsZEhKcFkzQnlaV05wYzJsdmJqc2dkR1Y0ZEMxMGNtRnVjMlp2Y20wNmJtOXVaVHNnZG1WeWRHbGpZV3d0WVd4cFoyNDZZbUZ6Wld4cGJtVTdJSGRvYVhSbExYTndZV05sT201dmNtMWhiRHNnZDJsa2IzZHpPakk3SUhkdmNtUXRZbkpsWVdzNlluSmxZV3N0ZDI5eVpEc2dkMjl5WkMxemNHRmphVzVuT2pCd2VGd2lQakl1SU5HQzBZRFJnOUN4MExBZ01USXdMekV5TUM4MExUUWcwWWpSZ2kweE1pRFF2RHhjTDJScGRqNDhaR2wySUhOMGVXeGxQVndpTFhkbFltdHBkQzFtYjI1MExYTnRiMjkwYUdsdVp6cGhiblJwWVd4cFlYTmxaRHNnTFhkbFltdHBkQzEwWlhoMExYTjBjbTlyWlMxM2FXUjBhRG93Y0hnN0lHSmhZMnRuY205MWJtUXRZMjlzYjNJNkkyWTFaalZtTlRzZ1ltOXlaR1Z5T2pCd2VEc2dZMjlzYjNJNkl6TTJNMkkwTkRzZ1ptOXVkQzFtWVcxcGJIazZKbkYxYjNRN1VGUWdVMkZ1Y3laeGRXOTBPeXhCY21saGJDeHpZVzV6TFhObGNtbG1PeUJtYjI1MExXWmxZWFIxY21VdGMyVjBkR2x1WjNNNmFXNW9aWEpwZERzZ1ptOXVkQzFyWlhKdWFXNW5PbWx1YUdWeWFYUTdJR1p2Ym5RdGIzQjBhV05oYkMxemFYcHBibWM2YVc1b1pYSnBkRHNnWm05dWRDMXphWHBsTFdGa2FuVnpkRHBwYm1obGNtbDBPeUJtYjI1MExYTnBlbVU2TVRWd2VEc2dabTl1ZEMxemRISmxkR05vT21sdWFHVnlhWFE3SUdadmJuUXRjM1I1YkdVNmJtOXliV0ZzT3lCbWIyNTBMWFpoY21saGJuUXRZV3gwWlhKdVlYUmxjenBwYm1obGNtbDBPeUJtYjI1MExYWmhjbWxoYm5RdFkyRndjenB1YjNKdFlXdzdJR1p2Ym5RdGRtRnlhV0Z1ZEMxbFlYTjBMV0Z6YVdGdU9tbHVhR1Z5YVhRN0lHWnZiblF0ZG1GeWFXRnVkQzFsYlc5cWFUcHBibWhsY21sME95Qm1iMjUwTFhaaGNtbGhiblF0YkdsbllYUjFjbVZ6T201dmNtMWhiRHNnWm05dWRDMTJZWEpwWVc1MExXNTFiV1Z5YVdNNmFXNW9aWEpwZERzZ1ptOXVkQzEyWVhKcFlXNTBMWEJ2YzJsMGFXOXVPbWx1YUdWeWFYUTdJR1p2Ym5RdGRtRnlhV0YwYVc5dUxYTmxkSFJwYm1kek9tbHVhR1Z5YVhRN0lHWnZiblF0ZDJWcFoyaDBPalF3TURzZ2JHVjBkR1Z5TFhOd1lXTnBibWM2Ym05eWJXRnNPeUJzYVc1bExXaGxhV2RvZERveU1IQjRPeUJ0WVhKbmFXNHRZbTkwZEc5dE9qQTdJRzFoY21kcGJpMXNaV1owT2pBN0lHMWhjbWRwYmkxeWFXZG9kRG93T3lCdFlYSm5hVzR0ZEc5d09qQTdJRzl5Y0doaGJuTTZNanNnYjNWMGJHbHVaVHB1YjI1bE95QnZkbVZ5Wm14dmR5MTNjbUZ3T21KeVpXRnJMWGR2Y21RN0lIQmhaR1JwYm1jNk1IQjRPeUIwWlhoMExXRnNhV2R1T25OMFlYSjBPeUIwWlhoMExXUmxZMjl5WVhScGIyNHRZMjlzYjNJNmFXNXBkR2xoYkRzZ2RHVjRkQzFrWldOdmNtRjBhVzl1TFhOMGVXeGxPbWx1YVhScFlXdzdJSFJsZUhRdFpHVmpiM0poZEdsdmJpMTBhR2xqYTI1bGMzTTZhVzVwZEdsaGJEc2dkR1Y0ZEMxcGJtUmxiblE2TUhCNE95QjBaWGgwTFhKbGJtUmxjbWx1WnpwblpXOXRaWFJ5YVdOd2NtVmphWE5wYjI0N0lIUmxlSFF0ZEhKaGJuTm1iM0p0T201dmJtVTdJSFpsY25ScFkyRnNMV0ZzYVdkdU9tSmhjMlZzYVc1bE95QjNhR2wwWlMxemNHRmpaVHB1YjNKdFlXdzdJSGRwWkc5M2N6b3lPeUIzYjNKa0xXSnlaV0ZyT21KeVpXRnJMWGR2Y21RN0lIZHZjbVF0YzNCaFkybHVaem93Y0hoY0lqNHpMaURSZ3RHQTBZUFFzZEN3SURFd01DOHhNREF2TkMwMElOR0kwWUl0TVRJZzBMdzhYQzlrYVhZK1BHUnBkaUJ6ZEhsc1pUMWNJaTEzWldKcmFYUXRabTl1ZEMxemJXOXZkR2hwYm1jNllXNTBhV0ZzYVdGelpXUTdJQzEzWldKcmFYUXRkR1Y0ZEMxemRISnZhMlV0ZDJsa2RHZzZNSEI0T3lCaVlXTnJaM0p2ZFc1a0xXTnZiRzl5T2lObU5XWTFaalU3SUdKdmNtUmxjam93Y0hnN0lHTnZiRzl5T2lNek5qTmlORFE3SUdadmJuUXRabUZ0YVd4NU9pWnhkVzkwTzFCVUlGTmhibk1tY1hWdmREc3NRWEpwWVd3c2MyRnVjeTF6WlhKcFpqc2dabTl1ZEMxbVpXRjBkWEpsTFhObGRIUnBibWR6T21sdWFHVnlhWFE3SUdadmJuUXRhMlZ5Ym1sdVp6cHBibWhsY21sME95Qm1iMjUwTFc5d2RHbGpZV3d0YzJsNmFXNW5PbWx1YUdWeWFYUTdJR1p2Ym5RdGMybDZaUzFoWkdwMWMzUTZhVzVvWlhKcGREc2dabTl1ZEMxemFYcGxPakUxY0hnN0lHWnZiblF0YzNSeVpYUmphRHBwYm1obGNtbDBPeUJtYjI1MExYTjBlV3hsT201dmNtMWhiRHNnWm05dWRDMTJZWEpwWVc1MExXRnNkR1Z5Ym1GMFpYTTZhVzVvWlhKcGREc2dabTl1ZEMxMllYSnBZVzUwTFdOaGNITTZibTl5YldGc095Qm1iMjUwTFhaaGNtbGhiblF0WldGemRDMWhjMmxoYmpwcGJtaGxjbWwwT3lCbWIyNTBMWFpoY21saGJuUXRaVzF2YW1rNmFXNW9aWEpwZERzZ1ptOXVkQzEyWVhKcFlXNTBMV3hwWjJGMGRYSmxjenB1YjNKdFlXdzdJR1p2Ym5RdGRtRnlhV0Z1ZEMxdWRXMWxjbWxqT21sdWFHVnlhWFE3SUdadmJuUXRkbUZ5YVdGdWRDMXdiM05wZEdsdmJqcHBibWhsY21sME95Qm1iMjUwTFhaaGNtbGhkR2x2YmkxelpYUjBhVzVuY3pwcGJtaGxjbWwwT3lCbWIyNTBMWGRsYVdkb2REbzBNREE3SUd4bGRIUmxjaTF6Y0dGamFXNW5PbTV2Y20xaGJEc2diR2x1WlMxb1pXbG5hSFE2TWpCd2VEc2diV0Z5WjJsdUxXSnZkSFJ2YlRvd095QnRZWEpuYVc0dGJHVm1kRG93T3lCdFlYSm5hVzR0Y21sbmFIUTZNRHNnYldGeVoybHVMWFJ2Y0Rvd095QnZjbkJvWVc1ek9qSTdJRzkxZEd4cGJtVTZibTl1WlRzZ2IzWmxjbVpzYjNjdGQzSmhjRHBpY21WaGF5MTNiM0prT3lCd1lXUmthVzVuT2pCd2VEc2dkR1Y0ZEMxaGJHbG5ianB6ZEdGeWREc2dkR1Y0ZEMxa1pXTnZjbUYwYVc5dUxXTnZiRzl5T21sdWFYUnBZV3c3SUhSbGVIUXRaR1ZqYjNKaGRHbHZiaTF6ZEhsc1pUcHBibWwwYVdGc095QjBaWGgwTFdSbFkyOXlZWFJwYjI0dGRHaHBZMnR1WlhOek9tbHVhWFJwWVd3N0lIUmxlSFF0YVc1a1pXNTBPakJ3ZURzZ2RHVjRkQzF5Wlc1a1pYSnBibWM2WjJWdmJXVjBjbWxqY0hKbFkybHphVzl1T3lCMFpYaDBMWFJ5WVc1elptOXliVHB1YjI1bE95QjJaWEowYVdOaGJDMWhiR2xuYmpwaVlYTmxiR2x1WlRzZ2QyaHBkR1V0YzNCaFkyVTZibTl5YldGc095QjNhV1J2ZDNNNk1qc2dkMjl5WkMxaWNtVmhhenBpY21WaGF5MTNiM0prT3lCM2IzSmtMWE53WVdOcGJtYzZNSEI0WENJK05DNGcwWWpRc3RDMTBMdlF1OUMxMFlBZ01UUXROeURSaU5HQ0xURXlJTkM4UEZ3dlpHbDJQanhrYVhZZ2MzUjViR1U5WENJdGQyVmlhMmwwTFdadmJuUXRjMjF2YjNSb2FXNW5PbUZ1ZEdsaGJHbGhjMlZrT3lBdGQyVmlhMmwwTFhSbGVIUXRjM1J5YjJ0bExYZHBaSFJvT2pCd2VEc2dZbUZqYTJkeWIzVnVaQzFqYjJ4dmNqb2paalZtTldZMU95QmliM0prWlhJNk1IQjRPeUJqYjJ4dmNqb2pNell6WWpRME95Qm1iMjUwTFdaaGJXbHNlVG9tY1hWdmREdFFWQ0JUWVc1ekpuRjFiM1E3TEVGeWFXRnNMSE5oYm5NdGMyVnlhV1k3SUdadmJuUXRabVZoZEhWeVpTMXpaWFIwYVc1bmN6cHBibWhsY21sME95Qm1iMjUwTFd0bGNtNXBibWM2YVc1b1pYSnBkRHNnWm05dWRDMXZjSFJwWTJGc0xYTnBlbWx1WnpwcGJtaGxjbWwwT3lCbWIyNTBMWE5wZW1VdFlXUnFkWE4wT21sdWFHVnlhWFE3SUdadmJuUXRjMmw2WlRveE5YQjRPeUJtYjI1MExYTjBjbVYwWTJnNmFXNW9aWEpwZERzZ1ptOXVkQzF6ZEhsc1pUcHViM0p0WVd3N0lHWnZiblF0ZG1GeWFXRnVkQzFoYkhSbGNtNWhkR1Z6T21sdWFHVnlhWFE3SUdadmJuUXRkbUZ5YVdGdWRDMWpZWEJ6T201dmNtMWhiRHNnWm05dWRDMTJZWEpwWVc1MExXVmhjM1F0WVhOcFlXNDZhVzVvWlhKcGREc2dabTl1ZEMxMllYSnBZVzUwTFdWdGIycHBPbWx1YUdWeWFYUTdJR1p2Ym5RdGRtRnlhV0Z1ZEMxc2FXZGhkSFZ5WlhNNmJtOXliV0ZzT3lCbWIyNTBMWFpoY21saGJuUXRiblZ0WlhKcFl6cHBibWhsY21sME95Qm1iMjUwTFhaaGNtbGhiblF0Y0c5emFYUnBiMjQ2YVc1b1pYSnBkRHNnWm05dWRDMTJZWEpwWVhScGIyNHRjMlYwZEdsdVozTTZhVzVvWlhKcGREc2dabTl1ZEMxM1pXbG5hSFE2TkRBd095QnNaWFIwWlhJdGMzQmhZMmx1WnpwdWIzSnRZV3c3SUd4cGJtVXRhR1ZwWjJoME9qSXdjSGc3SUcxaGNtZHBiaTFpYjNSMGIyMDZNRHNnYldGeVoybHVMV3hsWm5RNk1Ec2diV0Z5WjJsdUxYSnBaMmgwT2pBN0lHMWhjbWRwYmkxMGIzQTZNRHNnYjNKd2FHRnVjem95T3lCdmRYUnNhVzVsT201dmJtVTdJRzkyWlhKbWJHOTNMWGR5WVhBNlluSmxZV3N0ZDI5eVpEc2djR0ZrWkdsdVp6b3djSGc3SUhSbGVIUXRZV3hwWjI0NmMzUmhjblE3SUhSbGVIUXRaR1ZqYjNKaGRHbHZiaTFqYjJ4dmNqcHBibWwwYVdGc095QjBaWGgwTFdSbFkyOXlZWFJwYjI0dGMzUjViR1U2YVc1cGRHbGhiRHNnZEdWNGRDMWtaV052Y21GMGFXOXVMWFJvYVdOcmJtVnpjenBwYm1sMGFXRnNPeUIwWlhoMExXbHVaR1Z1ZERvd2NIZzdJSFJsZUhRdGNtVnVaR1Z5YVc1bk9tZGxiMjFsZEhKcFkzQnlaV05wYzJsdmJqc2dkR1Y0ZEMxMGNtRnVjMlp2Y20wNmJtOXVaVHNnZG1WeWRHbGpZV3d0WVd4cFoyNDZZbUZ6Wld4cGJtVTdJSGRvYVhSbExYTndZV05sT201dmNtMWhiRHNnZDJsa2IzZHpPakk3SUhkdmNtUXRZbkpsWVdzNlluSmxZV3N0ZDI5eVpEc2dkMjl5WkMxemNHRmphVzVuT2pCd2VGd2lQalV1SU5HSTBMTFF0ZEM3MEx2UXRkR0FJREl5TFRJZzBZalJnaTB4TWlEUXZEeGNMMlJwZGo0OFpHbDJJSE4wZVd4bFBWd2lMWGRsWW10cGRDMW1iMjUwTFhOdGIyOTBhR2x1WnpwaGJuUnBZV3hwWVhObFpEc2dMWGRsWW10cGRDMTBaWGgwTFhOMGNtOXJaUzEzYVdSMGFEb3djSGc3SUdKaFkydG5jbTkxYm1RdFkyOXNiM0k2STJZMVpqVm1OVHNnWW05eVpHVnlPakJ3ZURzZ1kyOXNiM0k2SXpNMk0ySTBORHNnWm05dWRDMW1ZVzFwYkhrNkpuRjFiM1E3VUZRZ1UyRnVjeVp4ZFc5ME95eEJjbWxoYkN4ellXNXpMWE5sY21sbU95Qm1iMjUwTFdabFlYUjFjbVV0YzJWMGRHbHVaM002YVc1b1pYSnBkRHNnWm05dWRDMXJaWEp1YVc1bk9tbHVhR1Z5YVhRN0lHWnZiblF0YjNCMGFXTmhiQzF6YVhwcGJtYzZhVzVvWlhKcGREc2dabTl1ZEMxemFYcGxMV0ZrYW5WemREcHBibWhsY21sME95Qm1iMjUwTFhOcGVtVTZNVFZ3ZURzZ1ptOXVkQzF6ZEhKbGRHTm9PbWx1YUdWeWFYUTdJR1p2Ym5RdGMzUjViR1U2Ym05eWJXRnNPeUJtYjI1MExYWmhjbWxoYm5RdFlXeDBaWEp1WVhSbGN6cHBibWhsY21sME95Qm1iMjUwTFhaaGNtbGhiblF0WTJGd2N6cHViM0p0WVd3N0lHWnZiblF0ZG1GeWFXRnVkQzFsWVhOMExXRnphV0Z1T21sdWFHVnlhWFE3SUdadmJuUXRkbUZ5YVdGdWRDMWxiVzlxYVRwcGJtaGxjbWwwT3lCbWIyNTBMWFpoY21saGJuUXRiR2xuWVhSMWNtVnpPbTV2Y20xaGJEc2dabTl1ZEMxMllYSnBZVzUwTFc1MWJXVnlhV002YVc1b1pYSnBkRHNnWm05dWRDMTJZWEpwWVc1MExYQnZjMmwwYVc5dU9tbHVhR1Z5YVhRN0lHWnZiblF0ZG1GeWFXRjBhVzl1TFhObGRIUnBibWR6T21sdWFHVnlhWFE3SUdadmJuUXRkMlZwWjJoME9qUXdNRHNnYkdWMGRHVnlMWE53WVdOcGJtYzZibTl5YldGc095QnNhVzVsTFdobGFXZG9kRG95TUhCNE95QnRZWEpuYVc0dFltOTBkRzl0T2pBN0lHMWhjbWRwYmkxc1pXWjBPakE3SUcxaGNtZHBiaTF5YVdkb2REb3dPeUJ0WVhKbmFXNHRkRzl3T2pBN0lHOXljR2hoYm5NNk1qc2diM1YwYkdsdVpUcHViMjVsT3lCdmRtVnlabXh2ZHkxM2NtRndPbUp5WldGckxYZHZjbVE3SUhCaFpHUnBibWM2TUhCNE95QjBaWGgwTFdGc2FXZHVPbk4wWVhKME95QjBaWGgwTFdSbFkyOXlZWFJwYjI0dFkyOXNiM0k2YVc1cGRHbGhiRHNnZEdWNGRDMWtaV052Y21GMGFXOXVMWE4wZVd4bE9tbHVhWFJwWVd3N0lIUmxlSFF0WkdWamIzSmhkR2x2YmkxMGFHbGphMjVsYzNNNmFXNXBkR2xoYkRzZ2RHVjRkQzFwYm1SbGJuUTZNSEI0T3lCMFpYaDBMWEpsYm1SbGNtbHVaenBuWlc5dFpYUnlhV053Y21WamFYTnBiMjQ3SUhSbGVIUXRkSEpoYm5ObWIzSnRPbTV2Ym1VN0lIWmxjblJwWTJGc0xXRnNhV2R1T21KaGMyVnNhVzVsT3lCM2FHbDBaUzF6Y0dGalpUcHViM0p0WVd3N0lIZHBaRzkzY3pveU95QjNiM0prTFdKeVpXRnJPbUp5WldGckxYZHZjbVE3SUhkdmNtUXRjM0JoWTJsdVp6b3djSGhjSWo0MkxpRFJndEdBMFlQUXNkQ3dJRGd3THpnd0x6TXRNakFnMFlqUmdpMHhNaURRdkR4Y0wyUnBkajQ4WkdsMklITjBlV3hsUFZ3aUxYZGxZbXRwZEMxbWIyNTBMWE50YjI5MGFHbHVaenBoYm5ScFlXeHBZWE5sWkRzZ0xYZGxZbXRwZEMxMFpYaDBMWE4wY205clpTMTNhV1IwYURvd2NIZzdJR0poWTJ0bmNtOTFibVF0WTI5c2IzSTZJMlkxWmpWbU5Uc2dZbTl5WkdWeU9qQndlRHNnWTI5c2IzSTZJek0yTTJJME5Ec2dabTl1ZEMxbVlXMXBiSGs2Sm5GMWIzUTdVRlFnVTJGdWN5WnhkVzkwT3l4QmNtbGhiQ3h6WVc1ekxYTmxjbWxtT3lCbWIyNTBMV1psWVhSMWNtVXRjMlYwZEdsdVozTTZhVzVvWlhKcGREc2dabTl1ZEMxclpYSnVhVzVuT21sdWFHVnlhWFE3SUdadmJuUXRiM0IwYVdOaGJDMXphWHBwYm1jNmFXNW9aWEpwZERzZ1ptOXVkQzF6YVhwbExXRmthblZ6ZERwcGJtaGxjbWwwT3lCbWIyNTBMWE5wZW1VNk1UVndlRHNnWm05dWRDMXpkSEpsZEdOb09tbHVhR1Z5YVhRN0lHWnZiblF0YzNSNWJHVTZibTl5YldGc095Qm1iMjUwTFhaaGNtbGhiblF0WVd4MFpYSnVZWFJsY3pwcGJtaGxjbWwwT3lCbWIyNTBMWFpoY21saGJuUXRZMkZ3Y3pwdWIzSnRZV3c3SUdadmJuUXRkbUZ5YVdGdWRDMWxZWE4wTFdGemFXRnVPbWx1YUdWeWFYUTdJR1p2Ym5RdGRtRnlhV0Z1ZEMxbGJXOXFhVHBwYm1obGNtbDBPeUJtYjI1MExYWmhjbWxoYm5RdGJHbG5ZWFIxY21Wek9tNXZjbTFoYkRzZ1ptOXVkQzEyWVhKcFlXNTBMVzUxYldWeWFXTTZhVzVvWlhKcGREc2dabTl1ZEMxMllYSnBZVzUwTFhCdmMybDBhVzl1T21sdWFHVnlhWFE3SUdadmJuUXRkbUZ5YVdGMGFXOXVMWE5sZEhScGJtZHpPbWx1YUdWeWFYUTdJR1p2Ym5RdGQyVnBaMmgwT2pRd01Ec2diR1YwZEdWeUxYTndZV05wYm1jNmJtOXliV0ZzT3lCc2FXNWxMV2hsYVdkb2REb3lNSEI0T3lCdFlYSm5hVzR0WW05MGRHOXRPakE3SUcxaGNtZHBiaTFzWldaME9qQTdJRzFoY21kcGJpMXlhV2RvZERvd095QnRZWEpuYVc0dGRHOXdPakE3SUc5eWNHaGhibk02TWpzZ2IzVjBiR2x1WlRwdWIyNWxPeUJ2ZG1WeVpteHZkeTEzY21Gd09tSnlaV0ZyTFhkdmNtUTdJSEJoWkdScGJtYzZNSEI0T3lCMFpYaDBMV0ZzYVdkdU9uTjBZWEowT3lCMFpYaDBMV1JsWTI5eVlYUnBiMjR0WTI5c2IzSTZhVzVwZEdsaGJEc2dkR1Y0ZEMxa1pXTnZjbUYwYVc5dUxYTjBlV3hsT21sdWFYUnBZV3c3SUhSbGVIUXRaR1ZqYjNKaGRHbHZiaTEwYUdsamEyNWxjM002YVc1cGRHbGhiRHNnZEdWNGRDMXBibVJsYm5RNk1IQjRPeUIwWlhoMExYSmxibVJsY21sdVp6cG5aVzl0WlhSeWFXTndjbVZqYVhOcGIyNDdJSFJsZUhRdGRISmhibk5tYjNKdE9tNXZibVU3SUhabGNuUnBZMkZzTFdGc2FXZHVPbUpoYzJWc2FXNWxPeUIzYUdsMFpTMXpjR0ZqWlRwdWIzSnRZV3c3SUhkcFpHOTNjem95T3lCM2IzSmtMV0p5WldGck9tSnlaV0ZyTFhkdmNtUTdJSGR2Y21RdGMzQmhZMmx1Wnpvd2NIaGNJajQzTGlEUmc5Q3owTDdRdTlDKzBMb2dNVGN3THpFM01DMDJJTkM4UEZ3dlpHbDJQanhrYVhZZ2MzUjViR1U5WENJdGQyVmlhMmwwTFdadmJuUXRjMjF2YjNSb2FXNW5PbUZ1ZEdsaGJHbGhjMlZrT3lBdGQyVmlhMmwwTFhSbGVIUXRjM1J5YjJ0bExYZHBaSFJvT2pCd2VEc2dZbUZqYTJkeWIzVnVaQzFqYjJ4dmNqb2paalZtTldZMU95QmliM0prWlhJNk1IQjRPeUJqYjJ4dmNqb2pNell6WWpRME95Qm1iMjUwTFdaaGJXbHNlVG9tY1hWdmREdFFWQ0JUWVc1ekpuRjFiM1E3TEVGeWFXRnNMSE5oYm5NdGMyVnlhV1k3SUdadmJuUXRabVZoZEhWeVpTMXpaWFIwYVc1bmN6cHBibWhsY21sME95Qm1iMjUwTFd0bGNtNXBibWM2YVc1b1pYSnBkRHNnWm05dWRDMXZjSFJwWTJGc0xYTnBlbWx1WnpwcGJtaGxjbWwwT3lCbWIyNTBMWE5wZW1VdFlXUnFkWE4wT21sdWFHVnlhWFE3SUdadmJuUXRjMmw2WlRveE5YQjRPeUJtYjI1MExYTjBjbVYwWTJnNmFXNW9aWEpwZERzZ1ptOXVkQzF6ZEhsc1pUcHViM0p0WVd3N0lHWnZiblF0ZG1GeWFXRnVkQzFoYkhSbGNtNWhkR1Z6T21sdWFHVnlhWFE3SUdadmJuUXRkbUZ5YVdGdWRDMWpZWEJ6T201dmNtMWhiRHNnWm05dWRDMTJZWEpwWVc1MExXVmhjM1F0WVhOcFlXNDZhVzVvWlhKcGREc2dabTl1ZEMxMllYSnBZVzUwTFdWdGIycHBPbWx1YUdWeWFYUTdJR1p2Ym5RdGRtRnlhV0Z1ZEMxc2FXZGhkSFZ5WlhNNmJtOXliV0ZzT3lCbWIyNTBMWFpoY21saGJuUXRiblZ0WlhKcFl6cHBibWhsY21sME95Qm1iMjUwTFhaaGNtbGhiblF0Y0c5emFYUnBiMjQ2YVc1b1pYSnBkRHNnWm05dWRDMTJZWEpwWVhScGIyNHRjMlYwZEdsdVozTTZhVzVvWlhKcGREc2dabTl1ZEMxM1pXbG5hSFE2TkRBd095QnNaWFIwWlhJdGMzQmhZMmx1WnpwdWIzSnRZV3c3SUd4cGJtVXRhR1ZwWjJoME9qSXdjSGc3SUcxaGNtZHBiaTFpYjNSMGIyMDZNRHNnYldGeVoybHVMV3hsWm5RNk1Ec2diV0Z5WjJsdUxYSnBaMmgwT2pBN0lHMWhjbWRwYmkxMGIzQTZNRHNnYjNKd2FHRnVjem95T3lCdmRYUnNhVzVsT201dmJtVTdJRzkyWlhKbWJHOTNMWGR5WVhBNlluSmxZV3N0ZDI5eVpEc2djR0ZrWkdsdVp6b3djSGc3SUhSbGVIUXRZV3hwWjI0NmMzUmhjblE3SUhSbGVIUXRaR1ZqYjNKaGRHbHZiaTFqYjJ4dmNqcHBibWwwYVdGc095QjBaWGgwTFdSbFkyOXlZWFJwYjI0dGMzUjViR1U2YVc1cGRHbGhiRHNnZEdWNGRDMWtaV052Y21GMGFXOXVMWFJvYVdOcmJtVnpjenBwYm1sMGFXRnNPeUIwWlhoMExXbHVaR1Z1ZERvd2NIZzdJSFJsZUhRdGNtVnVaR1Z5YVc1bk9tZGxiMjFsZEhKcFkzQnlaV05wYzJsdmJqc2dkR1Y0ZEMxMGNtRnVjMlp2Y20wNmJtOXVaVHNnZG1WeWRHbGpZV3d0WVd4cFoyNDZZbUZ6Wld4cGJtVTdJSGRvYVhSbExYTndZV05sT201dmNtMWhiRHNnZDJsa2IzZHpPakk3SUhkdmNtUXRZbkpsWVdzNlluSmxZV3N0ZDI5eVpEc2dkMjl5WkMxemNHRmphVzVuT2pCd2VGd2lQamd1SU5HRDBMUFF2dEM3MEw3UXVpQXhNREF2TVRBd0x6RXdMVEV5SU5DOFBGd3ZaR2wyUGp4Y0wyUnBkajQ4WkdsMlBpWnVZbk53T3p4Y0wyUnBkajQ4WkdsMklHUmhkR0V0YzJsbmJtRjBkWEpsTFhkcFpHZGxkRDFjSW1OdmJuUmhhVzVsY2x3aVBqeGthWFlnWkdGMFlTMXphV2R1WVhSMWNtVXRkMmxrWjJWMFBWd2lZMjl1ZEdWdWRGd2lQanhrYVhZK1BHUnBkaUJ6ZEhsc1pUMWNJaTEzWldKcmFYUXRabTl1ZEMxemJXOXZkR2hwYm1jNllXNTBhV0ZzYVdGelpXUTdJQzEzWldKcmFYUXRkR1Y0ZEMxemRISnZhMlV0ZDJsa2RHZzZNSEI0T3lCaVlXTnJaM0p2ZFc1a0xXTnZiRzl5T2lObVptWm1abVk3SUdKdmNtUmxjam93Y0hnN0lHTnZiRzl5T2lNeVpUTTJOREE3SUdOMWNuTnZjanAwWlhoME95Qm1iMjUwTFdaaGJXbHNlVHBJWld4MlpYUnBZMkVzUVhKcFlXd3NjMkZ1Y3kxelpYSnBaanNnWm05dWRDMXphWHBsT2pFemNIZzdJR1p2Ym5RdGMzUnlaWFJqYURwcGJtaGxjbWwwT3lCbWIyNTBMWE4wZVd4bE9tNXZjbTFoYkRzZ1ptOXVkQzEyWVhKcFlXNTBMV05oY0hNNmJtOXliV0ZzT3lCbWIyNTBMWFpoY21saGJuUXRaV0Z6ZEMxaGMybGhianBwYm1obGNtbDBPeUJtYjI1MExYWmhjbWxoYm5RdGJHbG5ZWFIxY21Wek9tNXZjbTFoYkRzZ1ptOXVkQzEyWVhKcFlXNTBMVzUxYldWeWFXTTZhVzVvWlhKcGREc2dabTl1ZEMxM1pXbG5hSFE2TkRBd095QnNaWFIwWlhJdGMzQmhZMmx1WnpwdWIzSnRZV3c3SUd4cGJtVXRhR1ZwWjJoME9tbHVhR1Z5YVhRN0lHMWhjbWRwYmkxaWIzUjBiMjA2TUhCNE95QnRZWEpuYVc0dGJHVm1kRG93Y0hnN0lHMWhjbWRwYmkxeWFXZG9kRG93Y0hnN0lHMWhjbWRwYmkxMGIzQTZNSEI0T3lCdmNuQm9ZVzV6T2pJN0lHOTFkR3hwYm1VNk1IQjRPeUJ3WVdSa2FXNW5PakJ3ZURzZ2RHVjRkQzFoYkdsbmJqcHNaV1owT3lCMFpYaDBMV1JsWTI5eVlYUnBiMjR0WTI5c2IzSTZhVzVwZEdsaGJEc2dkR1Y0ZEMxa1pXTnZjbUYwYVc5dUxYTjBlV3hsT21sdWFYUnBZV3c3SUhSbGVIUXRaR1ZqYjNKaGRHbHZiaTEwYUdsamEyNWxjM002YVc1cGRHbGhiRHNnZEdWNGRDMXBibVJsYm5RNk1IQjRPeUIwWlhoMExYSmxibVJsY21sdVp6cG5aVzl0WlhSeWFXTndjbVZqYVhOcGIyNDdJSFJsZUhRdGRISmhibk5tYjNKdE9tNXZibVU3SUhabGNuUnBZMkZzTFdGc2FXZHVPbUpoYzJWc2FXNWxPeUIzYUdsMFpTMXpjR0ZqWlRwd2NtVXRkM0poY0RzZ2QybGtiM2R6T2pJN0lIZHZjbVF0YzNCaFkybHVaem93Y0hoY0lqNDhjM0JoYmlCemRIbHNaVDFjSW05MWRHeHBibVU2SURCd2VEdGliM0prWlhJNklEQndlRHR0WVhKbmFXNDZJREJ3ZUR0d1lXUmthVzVuT2lBd2NIZzdabTl1ZERvZ2FXNW9aWEpwZER0MlpYSjBhV05oYkMxaGJHbG5iam9nWW1GelpXeHBibVU3ZEdWNGRDMXlaVzVrWlhKcGJtYzZJR2RsYjIxbGRISnBZM0J5WldOcGMybHZianN0ZDJWaWEybDBMV1p2Ym5RdGMyMXZiM1JvYVc1bk9pQmhiblJwWVd4cFlYTmxaRHRqYjJ4dmNqb2djbWRpS0RRNUxDQTFOeXdnTmpZcE8xd2lQaTB0Sm01aWMzQTdQRnd2YzNCaGJqNDhYQzlrYVhZK1BHUnBkaUJ6ZEhsc1pUMWNJaTEzWldKcmFYUXRabTl1ZEMxemJXOXZkR2hwYm1jNllXNTBhV0ZzYVdGelpXUTdJQzEzWldKcmFYUXRkR1Y0ZEMxemRISnZhMlV0ZDJsa2RHZzZNSEI0T3lCaVlXTnJaM0p2ZFc1a0xXTnZiRzl5T2lObVptWm1abVk3SUdKdmNtUmxjam93Y0hnN0lHTnZiRzl5T2lNeVpUTTJOREE3SUdOMWNuTnZjanAwWlhoME95Qm1iMjUwTFdaaGJXbHNlVHBJWld4MlpYUnBZMkVzUVhKcFlXd3NjMkZ1Y3kxelpYSnBaanNnWm05dWRDMXphWHBsT2pFemNIZzdJR1p2Ym5RdGMzUnlaWFJqYURwcGJtaGxjbWwwT3lCbWIyNTBMWE4wZVd4bE9tNXZjbTFoYkRzZ1ptOXVkQzEyWVhKcFlXNTBMV05oY0hNNmJtOXliV0ZzT3lCbWIyNTBMWFpoY21saGJuUXRaV0Z6ZEMxaGMybGhianBwYm1obGNtbDBPeUJtYjI1MExYWmhjbWxoYm5RdGJHbG5ZWFIxY21Wek9tNXZjbTFoYkRzZ1ptOXVkQzEyWVhKcFlXNTBMVzUxYldWeWFXTTZhVzVvWlhKcGREc2dabTl1ZEMxM1pXbG5hSFE2TkRBd095QnNaWFIwWlhJdGMzQmhZMmx1WnpwdWIzSnRZV3c3SUd4cGJtVXRhR1ZwWjJoME9tbHVhR1Z5YVhRN0lHMWhjbWRwYmkxaWIzUjBiMjA2TUhCNE95QnRZWEpuYVc0dGJHVm1kRG93Y0hnN0lHMWhjbWRwYmkxeWFXZG9kRG93Y0hnN0lHMWhjbWRwYmkxMGIzQTZNSEI0T3lCdmNuQm9ZVzV6T2pJN0lHOTFkR3hwYm1VNk1IQjRPeUJ3WVdSa2FXNW5PakJ3ZURzZ2RHVjRkQzFoYkdsbmJqcHNaV1owT3lCMFpYaDBMV1JsWTI5eVlYUnBiMjR0WTI5c2IzSTZhVzVwZEdsaGJEc2dkR1Y0ZEMxa1pXTnZjbUYwYVc5dUxYTjBlV3hsT21sdWFYUnBZV3c3SUhSbGVIUXRaR1ZqYjNKaGRHbHZiaTEwYUdsamEyNWxjM002YVc1cGRHbGhiRHNnZEdWNGRDMXBibVJsYm5RNk1IQjRPeUIwWlhoMExYSmxibVJsY21sdVp6cG5aVzl0WlhSeWFXTndjbVZqYVhOcGIyNDdJSFJsZUhRdGRISmhibk5tYjNKdE9tNXZibVU3SUhabGNuUnBZMkZzTFdGc2FXZHVPbUpoYzJWc2FXNWxPeUIzYUdsMFpTMXpjR0ZqWlRwd2NtVXRkM0poY0RzZ2QybGtiM2R6T2pJN0lIZHZjbVF0YzNCaFkybHVaem93Y0hoY0lqNDhjM0JoYmlCemRIbHNaVDFjSW05MWRHeHBibVU2SURCd2VEdGliM0prWlhJNklEQndlRHR0WVhKbmFXNDZJREJ3ZUR0d1lXUmthVzVuT2lBd2NIZzdabTl1ZERvZ2FXNW9aWEpwZER0MlpYSjBhV05oYkMxaGJHbG5iam9nWW1GelpXeHBibVU3ZEdWNGRDMXlaVzVrWlhKcGJtYzZJR2RsYjIxbGRISnBZM0J5WldOcGMybHZianN0ZDJWaWEybDBMV1p2Ym5RdGMyMXZiM1JvYVc1bk9pQmhiblJwWVd4cFlYTmxaRHRqYjJ4dmNqb2dZbXhoWTJzN1hDSSswS0VnMEtQUXN0Q3cwTGJRdGRDOTBMalF0ZEM4TER4Y0wzTndZVzQrUEZ3dlpHbDJQanhrYVhZZ2MzUjViR1U5WENJdGQyVmlhMmwwTFdadmJuUXRjMjF2YjNSb2FXNW5PbUZ1ZEdsaGJHbGhjMlZrT3lBdGQyVmlhMmwwTFhSbGVIUXRjM1J5YjJ0bExYZHBaSFJvT2pCd2VEc2dZbUZqYTJkeWIzVnVaQzFqYjJ4dmNqb2pabVptWm1abU95QmliM0prWlhJNk1IQjRPeUJqYjJ4dmNqb2pNbVV6TmpRd095QmpkWEp6YjNJNmRHVjRkRHNnWm05dWRDMW1ZVzFwYkhrNlNHVnNkbVYwYVdOaExFRnlhV0ZzTEhOaGJuTXRjMlZ5YVdZN0lHWnZiblF0YzJsNlpUb3hNM0I0T3lCbWIyNTBMWE4wY21WMFkyZzZhVzVvWlhKcGREc2dabTl1ZEMxemRIbHNaVHB1YjNKdFlXdzdJR1p2Ym5RdGRtRnlhV0Z1ZEMxallYQnpPbTV2Y20xaGJEc2dabTl1ZEMxMllYSnBZVzUwTFdWaGMzUXRZWE5wWVc0NmFXNW9aWEpwZERzZ1ptOXVkQzEyWVhKcFlXNTBMV3hwWjJGMGRYSmxjenB1YjNKdFlXdzdJR1p2Ym5RdGRtRnlhV0Z1ZEMxdWRXMWxjbWxqT21sdWFHVnlhWFE3SUdadmJuUXRkMlZwWjJoME9qUXdNRHNnYkdWMGRHVnlMWE53WVdOcGJtYzZibTl5YldGc095QnNhVzVsTFdobGFXZG9kRHBwYm1obGNtbDBPeUJ0WVhKbmFXNHRZbTkwZEc5dE9qQndlRHNnYldGeVoybHVMV3hsWm5RNk1IQjRPeUJ0WVhKbmFXNHRjbWxuYUhRNk1IQjRPeUJ0WVhKbmFXNHRkRzl3T2pCd2VEc2diM0p3YUdGdWN6b3lPeUJ2ZFhSc2FXNWxPakJ3ZURzZ2NHRmtaR2x1Wnpvd2NIZzdJSFJsZUhRdFlXeHBaMjQ2YkdWbWREc2dkR1Y0ZEMxa1pXTnZjbUYwYVc5dUxXTnZiRzl5T21sdWFYUnBZV3c3SUhSbGVIUXRaR1ZqYjNKaGRHbHZiaTF6ZEhsc1pUcHBibWwwYVdGc095QjBaWGgwTFdSbFkyOXlZWFJwYjI0dGRHaHBZMnR1WlhOek9tbHVhWFJwWVd3N0lIUmxlSFF0YVc1a1pXNTBPakJ3ZURzZ2RHVjRkQzF5Wlc1a1pYSnBibWM2WjJWdmJXVjBjbWxqY0hKbFkybHphVzl1T3lCMFpYaDBMWFJ5WVc1elptOXliVHB1YjI1bE95QjJaWEowYVdOaGJDMWhiR2xuYmpwaVlYTmxiR2x1WlRzZ2QyaHBkR1V0YzNCaFkyVTZjSEpsTFhkeVlYQTdJSGRwWkc5M2N6b3lPeUIzYjNKa0xYTndZV05wYm1jNk1IQjRYQ0krUEhOd1lXNGdjM1I1YkdVOVhDSnZkWFJzYVc1bE9pQXdjSGc3WW05eVpHVnlPaUF3Y0hnN2JXRnlaMmx1T2lBd2NIZzdjR0ZrWkdsdVp6b2dNSEI0TzJadmJuUTZJR2x1YUdWeWFYUTdkbVZ5ZEdsallXd3RZV3hwWjI0NklHSmhjMlZzYVc1bE8zUmxlSFF0Y21WdVpHVnlhVzVuT2lCblpXOXRaWFJ5YVdOd2NtVmphWE5wYjI0N0xYZGxZbXRwZEMxbWIyNTBMWE50YjI5MGFHbHVaem9nWVc1MGFXRnNhV0Z6WldRN1kyOXNiM0k2SUdKc1lXTnJPMXdpUHRDYzBMWFF2ZEMxMExUUXR0QzEwWUFnMEw3Umd0QzAwTFhRdTlDd0lOQy8wWURRdnRDMDBMRFF0aUE4WEM5emNHRnVQc0tyMEp6UXRkR0MwTERRdTlDNzBLTFJnTkMxMExuUXRNSzdQRnd2WkdsMlBqeGthWFlnYzNSNWJHVTlYQ0l0ZDJWaWEybDBMV1p2Ym5RdGMyMXZiM1JvYVc1bk9tRnVkR2xoYkdsaGMyVmtPeUF0ZDJWaWEybDBMWFJsZUhRdGMzUnliMnRsTFhkcFpIUm9PakJ3ZURzZ1ltRmphMmR5YjNWdVpDMWpiMnh2Y2pvalptWm1abVptT3lCaWIzSmtaWEk2TUhCNE95QmpiMnh2Y2pvak1tVXpOalF3T3lCamRYSnpiM0k2ZEdWNGREc2dabTl1ZEMxbVlXMXBiSGs2U0dWc2RtVjBhV05oTEVGeWFXRnNMSE5oYm5NdGMyVnlhV1k3SUdadmJuUXRjMmw2WlRveE0zQjRPeUJtYjI1MExYTjBjbVYwWTJnNmFXNW9aWEpwZERzZ1ptOXVkQzF6ZEhsc1pUcHViM0p0WVd3N0lHWnZiblF0ZG1GeWFXRnVkQzFqWVhCek9tNXZjbTFoYkRzZ1ptOXVkQzEyWVhKcFlXNTBMV1ZoYzNRdFlYTnBZVzQ2YVc1b1pYSnBkRHNnWm05dWRDMTJZWEpwWVc1MExXeHBaMkYwZFhKbGN6cHViM0p0WVd3N0lHWnZiblF0ZG1GeWFXRnVkQzF1ZFcxbGNtbGpPbWx1YUdWeWFYUTdJR1p2Ym5RdGQyVnBaMmgwT2pRd01Ec2diR1YwZEdWeUxYTndZV05wYm1jNmJtOXliV0ZzT3lCc2FXNWxMV2hsYVdkb2REcHBibWhsY21sME95QnRZWEpuYVc0dFltOTBkRzl0T2pCd2VEc2diV0Z5WjJsdUxXeGxablE2TUhCNE95QnRZWEpuYVc0dGNtbG5hSFE2TUhCNE95QnRZWEpuYVc0dGRHOXdPakJ3ZURzZ2IzSndhR0Z1Y3pveU95QnZkWFJzYVc1bE9qQndlRHNnY0dGa1pHbHVaem93Y0hnN0lIUmxlSFF0WVd4cFoyNDZiR1ZtZERzZ2RHVjRkQzFrWldOdmNtRjBhVzl1TFdOdmJHOXlPbWx1YVhScFlXdzdJSFJsZUhRdFpHVmpiM0poZEdsdmJpMXpkSGxzWlRwcGJtbDBhV0ZzT3lCMFpYaDBMV1JsWTI5eVlYUnBiMjR0ZEdocFkydHVaWE56T21sdWFYUnBZV3c3SUhSbGVIUXRhVzVrWlc1ME9qQndlRHNnZEdWNGRDMXlaVzVrWlhKcGJtYzZaMlZ2YldWMGNtbGpjSEpsWTJsemFXOXVPeUIwWlhoMExYUnlZVzV6Wm05eWJUcHViMjVsT3lCMlpYSjBhV05oYkMxaGJHbG5ianBpWVhObGJHbHVaVHNnZDJocGRHVXRjM0JoWTJVNmNISmxMWGR5WVhBN0lIZHBaRzkzY3pveU95QjNiM0prTFhOd1lXTnBibWM2TUhCNFhDSSswSlBRdTlDdzBMVFJpOUdJMExYUXN0Q3dJTkNjMExEUmdOQ3owTERSZ05DNDBZTFFzQ0RRa05DNzBMWFF1dEdCMExEUXZkQzAwWURRdnRDeTBMM1FzRHhjTDJScGRqNDhaR2wySUhOMGVXeGxQVndpTFhkbFltdHBkQzFtYjI1MExYTnRiMjkwYUdsdVp6cGhiblJwWVd4cFlYTmxaRHNnTFhkbFltdHBkQzEwWlhoMExYTjBjbTlyWlMxM2FXUjBhRG93Y0hnN0lHSmhZMnRuY205MWJtUXRZMjlzYjNJNkkyWm1abVptWmpzZ1ltOXlaR1Z5T2pCd2VEc2dZMjlzYjNJNkl6SmxNelkwTURzZ1kzVnljMjl5T25SbGVIUTdJR1p2Ym5RdFptRnRhV3g1T2tobGJIWmxkR2xqWVN4QmNtbGhiQ3h6WVc1ekxYTmxjbWxtT3lCbWIyNTBMWE5wZW1VNk1UTndlRHNnWm05dWRDMXpkSEpsZEdOb09tbHVhR1Z5YVhRN0lHWnZiblF0YzNSNWJHVTZibTl5YldGc095Qm1iMjUwTFhaaGNtbGhiblF0WTJGd2N6cHViM0p0WVd3N0lHWnZiblF0ZG1GeWFXRnVkQzFsWVhOMExXRnphV0Z1T21sdWFHVnlhWFE3SUdadmJuUXRkbUZ5YVdGdWRDMXNhV2RoZEhWeVpYTTZibTl5YldGc095Qm1iMjUwTFhaaGNtbGhiblF0Ym5WdFpYSnBZenBwYm1obGNtbDBPeUJtYjI1MExYZGxhV2RvZERvME1EQTdJR3hsZEhSbGNpMXpjR0ZqYVc1bk9tNXZjbTFoYkRzZ2JHbHVaUzFvWldsbmFIUTZhVzVvWlhKcGREc2diV0Z5WjJsdUxXSnZkSFJ2YlRvd2NIZzdJRzFoY21kcGJpMXNaV1owT2pCd2VEc2diV0Z5WjJsdUxYSnBaMmgwT2pCd2VEc2diV0Z5WjJsdUxYUnZjRG93Y0hnN0lHOXljR2hoYm5NNk1qc2diM1YwYkdsdVpUb3djSGc3SUhCaFpHUnBibWM2TUhCNE95QjBaWGgwTFdGc2FXZHVPbXhsWm5RN0lIUmxlSFF0WkdWamIzSmhkR2x2YmkxamIyeHZjanBwYm1sMGFXRnNPeUIwWlhoMExXUmxZMjl5WVhScGIyNHRjM1I1YkdVNmFXNXBkR2xoYkRzZ2RHVjRkQzFrWldOdmNtRjBhVzl1TFhSb2FXTnJibVZ6Y3pwcGJtbDBhV0ZzT3lCMFpYaDBMV2x1WkdWdWREb3djSGc3SUhSbGVIUXRjbVZ1WkdWeWFXNW5PbWRsYjIxbGRISnBZM0J5WldOcGMybHZianNnZEdWNGRDMTBjbUZ1YzJadmNtMDZibTl1WlRzZ2RtVnlkR2xqWVd3dFlXeHBaMjQ2WW1GelpXeHBibVU3SUhkb2FYUmxMWE53WVdObE9uQnlaUzEzY21Gd095QjNhV1J2ZDNNNk1qc2dkMjl5WkMxemNHRmphVzVuT2pCd2VGd2lQaVp1WW5Od096eGNMMlJwZGo0OFpHbDJJSE4wZVd4bFBWd2lMWGRsWW10cGRDMW1iMjUwTFhOdGIyOTBhR2x1WnpwaGJuUnBZV3hwWVhObFpEc2dMWGRsWW10cGRDMTBaWGgwTFhOMGNtOXJaUzEzYVdSMGFEb3djSGc3SUdKaFkydG5jbTkxYm1RdFkyOXNiM0k2STJabVptWm1aanNnWW05eVpHVnlPakJ3ZURzZ1kyOXNiM0k2SXpKbE16WTBNRHNnWTNWeWMyOXlPblJsZUhRN0lHWnZiblF0Wm1GdGFXeDVPa2hsYkhabGRHbGpZU3hCY21saGJDeHpZVzV6TFhObGNtbG1PeUJtYjI1MExYTnBlbVU2TVROd2VEc2dabTl1ZEMxemRISmxkR05vT21sdWFHVnlhWFE3SUdadmJuUXRjM1I1YkdVNmJtOXliV0ZzT3lCbWIyNTBMWFpoY21saGJuUXRZMkZ3Y3pwdWIzSnRZV3c3SUdadmJuUXRkbUZ5YVdGdWRDMWxZWE4wTFdGemFXRnVPbWx1YUdWeWFYUTdJR1p2Ym5RdGRtRnlhV0Z1ZEMxc2FXZGhkSFZ5WlhNNmJtOXliV0ZzT3lCbWIyNTBMWFpoY21saGJuUXRiblZ0WlhKcFl6cHBibWhsY21sME95Qm1iMjUwTFhkbGFXZG9kRG8wTURBN0lHeGxkSFJsY2kxemNHRmphVzVuT201dmNtMWhiRHNnYkdsdVpTMW9aV2xuYUhRNmFXNW9aWEpwZERzZ2JXRnlaMmx1TFdKdmRIUnZiVG93Y0hnN0lHMWhjbWRwYmkxc1pXWjBPakJ3ZURzZ2JXRnlaMmx1TFhKcFoyaDBPakJ3ZURzZ2JXRnlaMmx1TFhSdmNEb3djSGc3SUc5eWNHaGhibk02TWpzZ2IzVjBiR2x1WlRvd2NIZzdJSEJoWkdScGJtYzZNSEI0T3lCMFpYaDBMV0ZzYVdkdU9teGxablE3SUhSbGVIUXRaR1ZqYjNKaGRHbHZiaTFqYjJ4dmNqcHBibWwwYVdGc095QjBaWGgwTFdSbFkyOXlZWFJwYjI0dGMzUjViR1U2YVc1cGRHbGhiRHNnZEdWNGRDMWtaV052Y21GMGFXOXVMWFJvYVdOcmJtVnpjenBwYm1sMGFXRnNPeUIwWlhoMExXbHVaR1Z1ZERvd2NIZzdJSFJsZUhRdGNtVnVaR1Z5YVc1bk9tZGxiMjFsZEhKcFkzQnlaV05wYzJsdmJqc2dkR1Y0ZEMxMGNtRnVjMlp2Y20wNmJtOXVaVHNnZG1WeWRHbGpZV3d0WVd4cFoyNDZZbUZ6Wld4cGJtVTdJSGRvYVhSbExYTndZV05sT25CeVpTMTNjbUZ3T3lCM2FXUnZkM002TWpzZ2QyOXlaQzF6Y0dGamFXNW5PakJ3ZUZ3aVB0Q2UwSjdRbmlEQ3E5Q2MwTFhSZ3RDdzBMdlF1OUNpMFlEUXRkQzUwTFRDdXp4Y0wyUnBkajQ4WkdsMklITjBlV3hsUFZ3aUxYZGxZbXRwZEMxbWIyNTBMWE50YjI5MGFHbHVaenBoYm5ScFlXeHBZWE5sWkRzZ0xYZGxZbXRwZEMxMFpYaDBMWE4wY205clpTMTNhV1IwYURvd2NIZzdJR0poWTJ0bmNtOTFibVF0WTI5c2IzSTZJMlptWm1abVpqc2dZbTl5WkdWeU9qQndlRHNnWTI5c2IzSTZJekpsTXpZME1Ec2dZM1Z5YzI5eU9uUmxlSFE3SUdadmJuUXRabUZ0YVd4NU9raGxiSFpsZEdsallTeEJjbWxoYkN4ellXNXpMWE5sY21sbU95Qm1iMjUwTFhOcGVtVTZNVE53ZURzZ1ptOXVkQzF6ZEhKbGRHTm9PbWx1YUdWeWFYUTdJR1p2Ym5RdGMzUjViR1U2Ym05eWJXRnNPeUJtYjI1MExYWmhjbWxoYm5RdFkyRndjenB1YjNKdFlXdzdJR1p2Ym5RdGRtRnlhV0Z1ZEMxbFlYTjBMV0Z6YVdGdU9tbHVhR1Z5YVhRN0lHWnZiblF0ZG1GeWFXRnVkQzFzYVdkaGRIVnlaWE02Ym05eWJXRnNPeUJtYjI1MExYWmhjbWxoYm5RdGJuVnRaWEpwWXpwcGJtaGxjbWwwT3lCbWIyNTBMWGRsYVdkb2REbzBNREE3SUd4bGRIUmxjaTF6Y0dGamFXNW5PbTV2Y20xaGJEc2diR2x1WlMxb1pXbG5hSFE2YVc1b1pYSnBkRHNnYldGeVoybHVMV0p2ZEhSdmJUb3djSGc3SUcxaGNtZHBiaTFzWldaME9qQndlRHNnYldGeVoybHVMWEpwWjJoME9qQndlRHNnYldGeVoybHVMWFJ2Y0Rvd2NIZzdJRzl5Y0doaGJuTTZNanNnYjNWMGJHbHVaVG93Y0hnN0lIQmhaR1JwYm1jNk1IQjRPeUIwWlhoMExXRnNhV2R1T214bFpuUTdJSFJsZUhRdFpHVmpiM0poZEdsdmJpMWpiMnh2Y2pwcGJtbDBhV0ZzT3lCMFpYaDBMV1JsWTI5eVlYUnBiMjR0YzNSNWJHVTZhVzVwZEdsaGJEc2dkR1Y0ZEMxa1pXTnZjbUYwYVc5dUxYUm9hV05yYm1WemN6cHBibWwwYVdGc095QjBaWGgwTFdsdVpHVnVkRG93Y0hnN0lIUmxlSFF0Y21WdVpHVnlhVzVuT21kbGIyMWxkSEpwWTNCeVpXTnBjMmx2YmpzZ2RHVjRkQzEwY21GdWMyWnZjbTA2Ym05dVpUc2dkbVZ5ZEdsallXd3RZV3hwWjI0NlltRnpaV3hwYm1VN0lIZG9hWFJsTFhOd1lXTmxPbkJ5WlMxM2NtRndPeUIzYVdSdmQzTTZNanNnZDI5eVpDMXpjR0ZqYVc1bk9qQndlRndpUGp4emNHRnVJSE4wZVd4bFBWd2liM1YwYkdsdVpUb2dNSEI0TzJKdmNtUmxjam9nTUhCNE8yMWhjbWRwYmpvZ01IQjRPM0JoWkdScGJtYzZJREJ3ZUR0bWIyNTBPaUJwYm1obGNtbDBPM1psY25ScFkyRnNMV0ZzYVdkdU9pQmlZWE5sYkdsdVpUdDBaWGgwTFhKbGJtUmxjbWx1WnpvZ1oyVnZiV1YwY21samNISmxZMmx6YVc5dU95MTNaV0pyYVhRdFptOXVkQzF6Ylc5dmRHaHBibWM2SUdGdWRHbGhiR2xoYzJWa08yTnZiRzl5T2lCaWJHRmphenRjSWo3Umd0QzEwTHM2SUR4emNHRnVQanh6Y0dGdVBqeHpjR0Z1SUdOc1lYTnpQVndpYW5NdGNHaHZibVV0Ym5WdFltVnlYQ0krT0NBb016a3hLU0F5T0RFdE1ERXRNREU4WEM5emNHRnVQanhjTDNOd1lXNCtQRnd2YzNCaGJqNDhYQzl6Y0dGdVBqeHpjR0Z1SUhOMGVXeGxQVndpYjNWMGJHbHVaVG9nTUhCNE8ySnZjbVJsY2pvZ01IQjRPMjFoY21kcGJqb2dNSEI0TzNCaFpHUnBibWM2SURCd2VEdG1iMjUwT2lCcGJtaGxjbWwwTzNabGNuUnBZMkZzTFdGc2FXZHVPaUJpWVhObGJHbHVaVHQwWlhoMExYSmxibVJsY21sdVp6b2daMlZ2YldWMGNtbGpjSEpsWTJsemFXOXVPeTEzWldKcmFYUXRabTl1ZEMxemJXOXZkR2hwYm1jNklHRnVkR2xoYkdsaGMyVmtPMk52Ykc5eU9pQnlaMklvTUN3Z01Dd2dNQ2s3WENJK0xDRFF0TkMrMExFdU5EQTFQRnd2YzNCaGJqNDhYQzlrYVhZK1BHUnBkaUJ6ZEhsc1pUMWNJaTEzWldKcmFYUXRabTl1ZEMxemJXOXZkR2hwYm1jNllXNTBhV0ZzYVdGelpXUTdJQzEzWldKcmFYUXRkR1Y0ZEMxemRISnZhMlV0ZDJsa2RHZzZNSEI0T3lCaVlXTnJaM0p2ZFc1a0xXTnZiRzl5T2lObVptWm1abVk3SUdKdmNtUmxjam93Y0hnN0lHTnZiRzl5T2lNeVpUTTJOREE3SUdOMWNuTnZjanAwWlhoME95Qm1iMjUwTFdaaGJXbHNlVHBJWld4MlpYUnBZMkVzUVhKcFlXd3NjMkZ1Y3kxelpYSnBaanNnWm05dWRDMXphWHBsT2pFemNIZzdJR1p2Ym5RdGMzUnlaWFJqYURwcGJtaGxjbWwwT3lCbWIyNTBMWE4wZVd4bE9tNXZjbTFoYkRzZ1ptOXVkQzEyWVhKcFlXNTBMV05oY0hNNmJtOXliV0ZzT3lCbWIyNTBMWFpoY21saGJuUXRaV0Z6ZEMxaGMybGhianBwYm1obGNtbDBPeUJtYjI1MExYWmhjbWxoYm5RdGJHbG5ZWFIxY21Wek9tNXZjbTFoYkRzZ1ptOXVkQzEyWVhKcFlXNTBMVzUxYldWeWFXTTZhVzVvWlhKcGREc2dabTl1ZEMxM1pXbG5hSFE2TkRBd095QnNaWFIwWlhJdGMzQmhZMmx1WnpwdWIzSnRZV3c3SUd4cGJtVXRhR1ZwWjJoME9tbHVhR1Z5YVhRN0lHMWhjbWRwYmkxaWIzUjBiMjA2TUhCNE95QnRZWEpuYVc0dGJHVm1kRG93Y0hnN0lHMWhjbWRwYmkxeWFXZG9kRG93Y0hnN0lHMWhjbWRwYmkxMGIzQTZNSEI0T3lCdmNuQm9ZVzV6T2pJN0lHOTFkR3hwYm1VNk1IQjRPeUJ3WVdSa2FXNW5PakJ3ZURzZ2RHVjRkQzFoYkdsbmJqcHNaV1owT3lCMFpYaDBMV1JsWTI5eVlYUnBiMjR0WTI5c2IzSTZhVzVwZEdsaGJEc2dkR1Y0ZEMxa1pXTnZjbUYwYVc5dUxYTjBlV3hsT21sdWFYUnBZV3c3SUhSbGVIUXRaR1ZqYjNKaGRHbHZiaTEwYUdsamEyNWxjM002YVc1cGRHbGhiRHNnZEdWNGRDMXBibVJsYm5RNk1IQjRPeUIwWlhoMExYSmxibVJsY21sdVp6cG5aVzl0WlhSeWFXTndjbVZqYVhOcGIyNDdJSFJsZUhRdGRISmhibk5tYjNKdE9tNXZibVU3SUhabGNuUnBZMkZzTFdGc2FXZHVPbUpoYzJWc2FXNWxPeUIzYUdsMFpTMXpjR0ZqWlRwd2NtVXRkM0poY0RzZ2QybGtiM2R6T2pJN0lIZHZjbVF0YzNCaFkybHVaem93Y0hoY0lqNDhjM0JoYmlCemRIbHNaVDFjSW05MWRHeHBibVU2SURCd2VEdGliM0prWlhJNklEQndlRHR0WVhKbmFXNDZJREJ3ZUR0d1lXUmthVzVuT2lBd2NIZzdabTl1ZERvZ2FXNW9aWEpwZER0MlpYSjBhV05oYkMxaGJHbG5iam9nWW1GelpXeHBibVU3ZEdWNGRDMXlaVzVrWlhKcGJtYzZJR2RsYjIxbGRISnBZM0J5WldOcGMybHZianN0ZDJWaWEybDBMV1p2Ym5RdGMyMXZiM1JvYVc1bk9pQmhiblJwWVd4cFlYTmxaRHRqYjJ4dmNqb2dZbXhoWTJzN1hDSSswTC9RdnRHSDBZTFFzRG9nTkRBMVFESTRNVEF4TURFdWNuVThYQzl6Y0dGdVBqeGNMMlJwZGo0OFpHbDJJSE4wZVd4bFBWd2lMWGRsWW10cGRDMW1iMjUwTFhOdGIyOTBhR2x1WnpwaGJuUnBZV3hwWVhObFpEc2dMWGRsWW10cGRDMTBaWGgwTFhOMGNtOXJaUzEzYVdSMGFEb3djSGc3SUdKaFkydG5jbTkxYm1RdFkyOXNiM0k2STJabVptWm1aanNnWW05eVpHVnlPakJ3ZURzZ1kyOXNiM0k2SXpKbE16WTBNRHNnWTNWeWMyOXlPblJsZUhRN0lHWnZiblF0Wm1GdGFXeDVPa2hsYkhabGRHbGpZU3hCY21saGJDeHpZVzV6TFhObGNtbG1PeUJtYjI1MExYTnBlbVU2TVROd2VEc2dabTl1ZEMxemRISmxkR05vT21sdWFHVnlhWFE3SUdadmJuUXRjM1I1YkdVNmJtOXliV0ZzT3lCbWIyNTBMWFpoY21saGJuUXRZMkZ3Y3pwdWIzSnRZV3c3SUdadmJuUXRkbUZ5YVdGdWRDMWxZWE4wTFdGemFXRnVPbWx1YUdWeWFYUTdJR1p2Ym5RdGRtRnlhV0Z1ZEMxc2FXZGhkSFZ5WlhNNmJtOXliV0ZzT3lCbWIyNTBMWFpoY21saGJuUXRiblZ0WlhKcFl6cHBibWhsY21sME95Qm1iMjUwTFhkbGFXZG9kRG8wTURBN0lHeGxkSFJsY2kxemNHRmphVzVuT201dmNtMWhiRHNnYkdsdVpTMW9aV2xuYUhRNmFXNW9aWEpwZERzZ2JXRnlaMmx1TFdKdmRIUnZiVG93Y0hnN0lHMWhjbWRwYmkxc1pXWjBPakJ3ZURzZ2JXRnlaMmx1TFhKcFoyaDBPakJ3ZURzZ2JXRnlaMmx1TFhSdmNEb3djSGc3SUc5eWNHaGhibk02TWpzZ2IzVjBiR2x1WlRvd2NIZzdJSEJoWkdScGJtYzZNSEI0T3lCMFpYaDBMV0ZzYVdkdU9teGxablE3SUhSbGVIUXRaR1ZqYjNKaGRHbHZiaTFqYjJ4dmNqcHBibWwwYVdGc095QjBaWGgwTFdSbFkyOXlZWFJwYjI0dGMzUjViR1U2YVc1cGRHbGhiRHNnZEdWNGRDMWtaV052Y21GMGFXOXVMWFJvYVdOcmJtVnpjenBwYm1sMGFXRnNPeUIwWlhoMExXbHVaR1Z1ZERvd2NIZzdJSFJsZUhRdGNtVnVaR1Z5YVc1bk9tZGxiMjFsZEhKcFkzQnlaV05wYzJsdmJqc2dkR1Y0ZEMxMGNtRnVjMlp2Y20wNmJtOXVaVHNnZG1WeWRHbGpZV3d0WVd4cFoyNDZZbUZ6Wld4cGJtVTdJSGRvYVhSbExYTndZV05sT25CeVpTMTNjbUZ3T3lCM2FXUnZkM002TWpzZ2QyOXlaQzF6Y0dGamFXNW5PakJ3ZUZ3aVBqeHpjR0Z1SUhOMGVXeGxQVndpYjNWMGJHbHVaVG9nTUhCNE8ySnZjbVJsY2pvZ01IQjRPMjFoY21kcGJqb2dNSEI0TzNCaFpHUnBibWM2SURCd2VEdG1iMjUwT2lCcGJtaGxjbWwwTzNabGNuUnBZMkZzTFdGc2FXZHVPaUJpWVhObGJHbHVaVHQwWlhoMExYSmxibVJsY21sdVp6b2daMlZ2YldWMGNtbGpjSEpsWTJsemFXOXVPeTEzWldKcmFYUXRabTl1ZEMxemJXOXZkR2hwYm1jNklHRnVkR2xoYkdsaGMyVmtPMk52Ykc5eU9pQmliR0ZqYXp0Y0lqN1FvZEN3MExuUmdqb2dkM2QzTGpJNE1UQXhNREV1Y25VOFhDOXpjR0Z1UGp4Y0wyUnBkajQ4WEM5a2FYWStQRnd2WkdsMlBqeGNMMlJwZGo0OFhDOUNUMFJaUGp4Y0wwaFVUVXcrWEc0aWZRPT0="
        # while True:    
        order_rec.consumer_test(hash=hash) # Выполняется паралельно но поставил заглушку
        #     hash = input("Введи hash:\n")
    else:
        order_rec.start()