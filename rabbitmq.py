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
from yandexgpt import custom_yandex_gpt
import config as conf
from thread import Thread

class Order_recognition():

    def __init__(self):
        self.find_mats = Find_materials()

    def write_logs(self, text, event=1):
        event = 'EVENT' if event == 1 else 'ERROR'
        date_time = datetime.now().astimezone()
        file_name = './logs/' + str(date_time.date()) + '.txt'
        with open(file_name, 'a', encoding="utf-8") as file:
            file.write(str(date_time) + ' | ' + event + ' | ' + text + '\n')


    def consumer_test(self, hash:str=None, content:str=None):
        if content is None:
            content = text_from_hash(hash)
        print('Text - ', content.split('\n'), flush=True)
        # self.test_analize_email(content)
        my_thread = Thread(target=self.test_analize_email, args=[content])
        my_thread.start()

    def test_analize_email(self, content):
        ygpt = custom_yandex_gpt()
        clear_email = ygpt.big_mail(content, False)
        # Отправляем распознаннaй текст(!) на поиск материалов
        print('Очищенные позиции -', clear_email)
        results = str(self.find_mats.paralell_rows(clear_email))
        self.write_logs('results - ' + results, 1)
        print('results = ', results)
        # self.send_result(results)

    def save_truth_test(self, content):
        if 'true_value' not in str(content):
            return
        self.write_logs('Получилось взять ответы МЕТОД 2', 1)
        print('Получилось взять ответы МЕТОД 2', flush=True)
        body = json.loads(content)
        print("METHOD 2 - ", body, flush=True)
        self.write_logs('METHOD 2 - ' + str(body), 1)
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
                request_text, _, _ = self.find_mats.new_mat_prep(request_text, val_ei, ei)
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
                    self.write_logs('Не нашёл такого материала ' + str(pos['true_material']) + ' ' + str(exc), event=0)
                    continue
                try:
                    print(self.find_mats.all_materials[self.find_mats.all_materials['Материал']
                                                       == (str(int(pos['true_material'])))])
                    print('Отправляем обучать !', flush=True)
                    self.write_logs('Отправляем обучать ! ' + request_text + '|' + true_first)
                    self.find_mats.models.fit(request_text, true_first, true_zero)
                except Exception as exc:
                    self.write_logs('Не смог обучить модельки для ' + str(pos['true_material']) + ' ' + str(exc),
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
            self.find_mats.method2.to_csv('data/method2.csv', index=False)
        else:
            self.write_logs('Не нашёл такого письма', event=0)
            print('Не нашёл такого письма', flush=True)
        print("Метод 2 всё", flush=True)

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
                    request_text, _, _ = self.find_mats.new_mat_prep(request_text, val_ei, ei)
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
                        self.write_logs('Не нашёл такого материала ' + str(pos['true_material']) + ' ' + str(exc),
                                        event=0)
                        continue
                    try:
                        print(self.find_mats.all_materials[self.find_mats.all_materials['Материал']
                                                           == (str(int(pos['true_material'])))])
                        print('Отправляем обучать !', flush=True)
                        self.write_logs('Отправляем обучать ! ' + request_text + '|' + true_first)
                        self.find_mats.models.fit(request_text, true_first, true_zero, fit_zero, fit_first)
                    except Exception as exc:
                        self.write_logs('Не смог обучить модельки для ' + str(pos['true_material']) + ' ' + str(exc),
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
                self.find_mats.method2.to_csv('data/method2.csv', index=False)
            else:
                self.write_logs('Не нашёл такого письма', event=0)
                print('Не нашёл такого письма', flush=True)
            print("Метод 2 всё", flush=True)

    def start_analize_email(self, content, msg, channel):
        print('Начало потока!', flush=True)
        ygpt = custom_yandex_gpt()
        clear_email = ygpt.big_mail(content)
        # Отправляем распознанный текст(!) на поиск материалов
        print('Clear email - ', clear_email)
        results = str(self.find_mats.paralell_rows(clear_email))
        self.write_logs('results - ' + results, 1)
        print('results = ', results)
        # self.send_result(results)
        # проверяем, требует ли сообщение ответа
        if msg.reply_to:
            # отправляем ответ в default exchange
            print('Отправляем результат', flush=True)
            self.write_logs('Отправляем результaт', 1)
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
            if len(body['email']) == 0:
                print('Письмо пустое!!!', flush=True)
                self.write_logs('Письмо пустое!!!', 1)
            content = text_from_hash(body['email'])
            # await self.start_analize_email(content, msg, channel)
            my_thread = Thread(target=self.start_analize_email, args=[content, msg, channel])
            my_thread.start()
            # my_thread.join()

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
    order_rec = Order_recognition()
    order_rec.start()
    # order_rec.consumer_test(hash="ZXlKaWRXTnJaWFJPWVcxbElqb2lZM0p0TFdWdFlXbHNJaXdpYjJKcVpXTjBUbUZ0WlNJNkltMXpaMTgwTkdZM016aGpNalV4TXpNeVpqVXlZVFk0T0RSak56STVNVEJtWkRWaFl5SXNJbVpwYkdWRGIyNTBaVzUwSWpvaVBHaDBiV3dnZUcxc2JuTTZkajFjSW5WeWJqcHpZMmhsYldGekxXMXBZM0p2YzI5bWRDMWpiMjA2ZG0xc1hDSWdlRzFzYm5NNmJ6MWNJblZ5YmpwelkyaGxiV0Z6TFcxcFkzSnZjMjltZEMxamIyMDZiMlptYVdObE9tOW1abWxqWlZ3aUlIaHRiRzV6T25jOVhDSjFjbTQ2YzJOb1pXMWhjeTF0YVdOeWIzTnZablF0WTI5dE9tOW1abWxqWlRwM2IzSmtYQ0lnZUcxc2JuTTZlRDFjSW5WeWJqcHpZMmhsYldGekxXMXBZM0p2YzI5bWRDMWpiMjA2YjJabWFXTmxPbVY0WTJWc1hDSWdlRzFzYm5NNmJUMWNJbWgwZEhBNkx5OXpZMmhsYldGekxtMXBZM0p2YzI5bWRDNWpiMjB2YjJabWFXTmxMekl3TURRdk1USXZiMjF0YkZ3aUlIaHRiRzV6UFZ3aWFIUjBjRG92TDNkM2R5NTNNeTV2Y21jdlZGSXZVa1ZETFdoMGJXdzBNRndpUGx4eVhHNDhhR1ZoWkQ1Y2NseHVQRzFsZEdFZ2FIUjBjQzFsY1hWcGRqMWNJa052Ym5SbGJuUXRWSGx3WlZ3aUlHTnZiblJsYm5ROVhDSjBaWGgwTDJoMGJXdzdJR05vWVhKelpYUTlhMjlwT0MxeVhDSStYSEpjYmp4dFpYUmhJRzVoYldVOVhDSkhaVzVsY21GMGIzSmNJaUJqYjI1MFpXNTBQVndpVFdsamNtOXpiMlowSUZkdmNtUWdNVFVnS0dacGJIUmxjbVZrSUcxbFpHbDFiU2xjSWo1Y2NseHVQSE4wZVd4bFBqd2hMUzFjY2x4dUx5b2dSbTl1ZENCRVpXWnBibWwwYVc5dWN5QXFMMXh5WEc1QVptOXVkQzFtWVdObFhISmNibHgwZTJadmJuUXRabUZ0YVd4NU9sd2lRMkZ0WW5KcFlTQk5ZWFJvWENJN1hISmNibHgwY0dGdWIzTmxMVEU2TWlBMElEVWdNeUExSURRZ05pQXpJRElnTkR0OVhISmNia0JtYjI1MExXWmhZMlZjY2x4dVhIUjdabTl1ZEMxbVlXMXBiSGs2UTJGc2FXSnlhVHRjY2x4dVhIUndZVzV2YzJVdE1Ub3lJREUxSURVZ01pQXlJRElnTkNBeklESWdORHQ5WEhKY2JpOHFJRk4wZVd4bElFUmxabWx1YVhScGIyNXpJQ292WEhKY2JuQXVUWE52VG05eWJXRnNMQ0JzYVM1TmMyOU9iM0p0WVd3c0lHUnBkaTVOYzI5T2IzSnRZV3hjY2x4dVhIUjdiV0Z5WjJsdU9qQmpiVHRjY2x4dVhIUnRZWEpuYVc0dFltOTBkRzl0T2k0d01EQXhjSFE3WEhKY2JseDBabTl1ZEMxemFYcGxPakV4TGpCd2REdGNjbHh1WEhSbWIyNTBMV1poYldsc2VUcGNJa05oYkdsaWNtbGNJaXh6WVc1ekxYTmxjbWxtTzF4eVhHNWNkRzF6YnkxbVlYSmxZWE4wTFd4aGJtZDFZV2RsT2tWT0xWVlRPMzFjY2x4dVlUcHNhVzVyTENCemNHRnVMazF6YjBoNWNHVnliR2x1YTF4eVhHNWNkSHR0YzI4dGMzUjViR1V0Y0hKcGIzSnBkSGs2T1RrN1hISmNibHgwWTI5c2IzSTZJekExTmpORE1UdGNjbHh1WEhSMFpYaDBMV1JsWTI5eVlYUnBiMjQ2ZFc1a1pYSnNhVzVsTzMxY2NseHVZVHAyYVhOcGRHVmtMQ0J6Y0dGdUxrMXpiMGg1Y0dWeWJHbHVhMFp2Ykd4dmQyVmtYSEpjYmx4MGUyMXpieTF6ZEhsc1pTMXdjbWx2Y21sMGVUbzVPVHRjY2x4dVhIUmpiMnh2Y2pvak9UVTBSamN5TzF4eVhHNWNkSFJsZUhRdFpHVmpiM0poZEdsdmJqcDFibVJsY214cGJtVTdmVnh5WEc1emNHRnVMa1Z0WVdsc1UzUjViR1V4TjF4eVhHNWNkSHR0YzI4dGMzUjViR1V0ZEhsd1pUcHdaWEp6YjI1aGJDMWpiMjF3YjNObE8xeHlYRzVjZEdadmJuUXRabUZ0YVd4NU9sd2lRMkZzYVdKeWFWd2lMSE5oYm5NdGMyVnlhV1k3WEhKY2JseDBZMjlzYjNJNmQybHVaRzkzZEdWNGREdDlYSEpjYmk1TmMyOURhSEJFWldaaGRXeDBYSEpjYmx4MGUyMXpieTF6ZEhsc1pTMTBlWEJsT21WNGNHOXlkQzF2Ym14NU8xeHlYRzVjZEcxemJ5MW1ZWEpsWVhOMExXeGhibWQxWVdkbE9rVk9MVlZUTzMxY2NseHVRSEJoWjJVZ1YyOXlaRk5sWTNScGIyNHhYSEpjYmx4MGUzTnBlbVU2TmpFeUxqQndkQ0EzT1RJdU1IQjBPMXh5WEc1Y2RHMWhjbWRwYmpveUxqQmpiU0EwTWk0MWNIUWdNaTR3WTIwZ015NHdZMjA3ZlZ4eVhHNWthWFl1VjI5eVpGTmxZM1JwYjI0eFhISmNibHgwZTNCaFoyVTZWMjl5WkZObFkzUnBiMjR4TzMxY2NseHVMUzArUEZ3dmMzUjViR1UrUENFdExWdHBaaUJuZEdVZ2JYTnZJRGxkUGp4NGJXdytYSEpjYmp4dk9uTm9ZWEJsWkdWbVlYVnNkSE1nZGpwbGVIUTlYQ0psWkdsMFhDSWdjM0JwWkcxaGVEMWNJakV3TWpaY0lpQXZQbHh5WEc0OFhDOTRiV3crUENGYlpXNWthV1pkTFMwK1BDRXRMVnRwWmlCbmRHVWdiWE52SURsZFBqeDRiV3crWEhKY2JqeHZPbk5vWVhCbGJHRjViM1YwSUhZNlpYaDBQVndpWldScGRGd2lQbHh5WEc0OGJ6cHBaRzFoY0NCMk9tVjRkRDFjSW1Wa2FYUmNJaUJrWVhSaFBWd2lNVndpSUM4K1hISmNianhjTDI4NmMyaGhjR1ZzWVhsdmRYUStQRnd2ZUcxc1Bqd2hXMlZ1WkdsbVhTMHRQbHh5WEc0OFhDOW9aV0ZrUGx4eVhHNDhZbTlrZVNCc1lXNW5QVndpVWxWY0lpQnNhVzVyUFZ3aUl6QTFOak5ETVZ3aUlIWnNhVzVyUFZ3aUl6azFORVkzTWx3aVBseHlYRzQ4WkdsMklHTnNZWE56UFZ3aVYyOXlaRk5sWTNScGIyNHhYQ0krWEhKY2JqeHdJR05zWVhOelBWd2lUWE52VG05eWJXRnNYQ0krMEpUUXZ0Q3gwWURSaTlDNUlOQzAwTFhRdmRHTUxpRFFuOUdBMEw3UmlOR0RJTkdCMExyUXZ0QzgwTC9RdTlDMTBMclJndEMrMExMUXNOR0MwWXdnMEx6UXNOR0kwTGpRdmRHRElOQzkwTEFnMEpIUmdOQ3cwWUxSZ2RDNjBMalF1U0RSaE5DNDBMdlF1TkN3MExzNlBHODZjRDQ4WEM5dk9uQStQRnd2Y0Q1Y2NseHVQSEFnWTJ4aGMzTTlYQ0pOYzI5T2IzSnRZV3hjSWo0OGJ6cHdQaVp1WW5Od096eGNMMjg2Y0Q0OFhDOXdQbHh5WEc0OGRHRmliR1VnWTJ4aGMzTTlYQ0pOYzI5T2IzSnRZV3hVWVdKc1pWd2lJR0p2Y21SbGNqMWNJakJjSWlCalpXeHNjM0JoWTJsdVp6MWNJakJjSWlCalpXeHNjR0ZrWkdsdVp6MWNJakJjSWlCM2FXUjBhRDFjSWpCY0lpQnpkSGxzWlQxY0luZHBaSFJvT2pjeE5pNHdjSFE3WW05eVpHVnlMV052Ykd4aGNITmxPbU52Ykd4aGNITmxYQ0krWEhKY2JqeDBZbTlrZVQ1Y2NseHVQSFJ5SUhOMGVXeGxQVndpYUdWcFoyaDBPakUxTGpCd2RGd2lQbHh5WEc0OGRHUWdkMmxrZEdnOVhDSTBNRE5jSWlCdWIzZHlZWEE5WENKY0lpQjJZV3hwWjI0OVhDSmliM1IwYjIxY0lpQnpkSGxzWlQxY0luZHBaSFJvT2pNd01pNHdjSFE3Y0dGa1pHbHVaem93WTIwZ05TNDBjSFFnTUdOdElEVXVOSEIwTzJobGFXZG9kRG94TlM0d2NIUmNJajVjY2x4dVBIQWdZMnhoYzNNOVhDSk5jMjlPYjNKdFlXeGNJajQ4YzNCaGJpQnpkSGxzWlQxY0ltTnZiRzl5T21Kc1lXTnJPMjF6YnkxbVlYSmxZWE4wTFd4aGJtZDFZV2RsT2xKVlhDSSswSmpSZ2RDKzBKclFsQzNRbE5DKzBMTXlNREU1THpBd016Y3RNVGc0UEc4NmNENDhYQzl2T25BK1BGd3ZjM0JoYmo0OFhDOXdQbHh5WEc0OFhDOTBaRDVjY2x4dVBIUmtJSGRwWkhSb1BWd2lNVEl3WENJZ2JtOTNjbUZ3UFZ3aVhDSWdZMjlzYzNCaGJqMWNJakpjSWlCMllXeHBaMjQ5WENKaWIzUjBiMjFjSWlCemRIbHNaVDFjSW5kcFpIUm9Pamt3TGpCd2REdHdZV1JrYVc1bk9qQmpiU0ExTGpSd2RDQXdZMjBnTlM0MGNIUTdhR1ZwWjJoME9qRTFMakJ3ZEZ3aVBseHlYRzQ4WEM5MFpENWNjbHh1UEhSa0lIZHBaSFJvUFZ3aU5qUmNJaUJ1YjNkeVlYQTlYQ0pjSWlCamIyeHpjR0Z1UFZ3aU1sd2lJSFpoYkdsbmJqMWNJbUp2ZEhSdmJWd2lJSE4wZVd4bFBWd2lkMmxrZEdnNk5EZ3VNSEIwTzNCaFpHUnBibWM2TUdOdElEVXVOSEIwSURCamJTQTFMalJ3ZER0b1pXbG5hSFE2TVRVdU1IQjBYQ0krWEhKY2JqeGNMM1JrUGx4eVhHNDhkR1FnZDJsa2RHZzlYQ0kyTkZ3aUlHNXZkM0poY0QxY0lsd2lJR052YkhOd1lXNDlYQ0l5WENJZ2RtRnNhV2R1UFZ3aVltOTBkRzl0WENJZ2MzUjViR1U5WENKM2FXUjBhRG8wT0M0d2NIUTdjR0ZrWkdsdVp6b3dZMjBnTlM0MGNIUWdNR050SURVdU5IQjBPMmhsYVdkb2REb3hOUzR3Y0hSY0lqNWNjbHh1UEZ3dmRHUStYSEpjYmp4MFpDQjNhV1IwYUQxY0lqYzVYQ0lnYm05M2NtRndQVndpWENJZ2RtRnNhV2R1UFZ3aVltOTBkRzl0WENJZ2MzUjViR1U5WENKM2FXUjBhRG8xT1M0d2NIUTdjR0ZrWkdsdVp6b3dZMjBnTlM0MGNIUWdNR050SURVdU5IQjBPMmhsYVdkb2REb3hOUzR3Y0hSY0lqNWNjbHh1UEZ3dmRHUStYSEpjYmp4MFpDQjNhV1IwYUQxY0lqa3lYQ0lnYm05M2NtRndQVndpWENJZ1kyOXNjM0JoYmoxY0lqSmNJaUIyWVd4cFoyNDlYQ0ppYjNSMGIyMWNJaUJ6ZEhsc1pUMWNJbmRwWkhSb09qWTVMakJ3ZER0d1lXUmthVzVuT2pCamJTQTFMalJ3ZENBd1kyMGdOUzQwY0hRN2FHVnBaMmgwT2pFMUxqQndkRndpUGx4eVhHNDhYQzkwWkQ1Y2NseHVQSFJrSUhkcFpIUm9QVndpTVRNelhDSWdibTkzY21Gd1BWd2lYQ0lnZG1Gc2FXZHVQVndpWW05MGRHOXRYQ0lnYzNSNWJHVTlYQ0ozYVdSMGFEb3hNREF1TUhCME8zQmhaR1JwYm1jNk1HTnRJRFV1TkhCMElEQmpiU0ExTGpSd2REdG9aV2xuYUhRNk1UVXVNSEIwWENJK1hISmNianhjTDNSa1BseHlYRzQ4WEM5MGNqNWNjbHh1UEhSeUlITjBlV3hsUFZ3aWFHVnBaMmgwT2pFMUxqYzFjSFJjSWo1Y2NseHVQSFJrSUhkcFpIUm9QVndpTkRBelhDSWdibTkzY21Gd1BWd2lYQ0lnZG1Gc2FXZHVQVndpWW05MGRHOXRYQ0lnYzNSNWJHVTlYQ0ozYVdSMGFEb3pNREl1TUhCME8ySnZjbVJsY2pwemIyeHBaQ0IzYVc1a2IzZDBaWGgwSURFdU1IQjBPM0JoWkdScGJtYzZNR050SURVdU5IQjBJREJqYlNBMUxqUndkRHRvWldsbmFIUTZNVFV1TnpWd2RGd2lQbHh5WEc0OGNDQmpiR0Z6Y3oxY0lrMXpiMDV2Y20xaGJGd2lQanh6Y0dGdUlITjBlV3hsUFZ3aVptOXVkQzF6YVhwbE9qRXlMakJ3ZER0amIyeHZjanBpYkdGamF6dHRjMjh0Wm1GeVpXRnpkQzFzWVc1bmRXRm5aVHBTVlZ3aVB0Q2EwWURSZzlDeklOR0IwWUxRc05DNzBZelF2ZEMrMExrZ01UYlF2TkM4SU5DaDBZSXpQRzg2Y0Q0OFhDOXZPbkErUEZ3dmMzQmhiajQ4WEM5d1BseHlYRzQ4WEM5MFpENWNjbHh1UEhSa0lIZHBaSFJvUFZ3aU5qUmNJaUJ6ZEhsc1pUMWNJbmRwWkhSb09qUTRMakJ3ZER0aWIzSmtaWEk2YzI5c2FXUWdkMmx1Wkc5M2RHVjRkQ0F4TGpCd2REdGliM0prWlhJdGJHVm1kRHB1YjI1bE8zQmhaR1JwYm1jNk1HTnRJRFV1TkhCMElEQmpiU0ExTGpSd2REdG9aV2xuYUhRNk1UVXVOelZ3ZEZ3aVBseHlYRzQ4Y0NCamJHRnpjejFjSWsxemIwNXZjbTFoYkZ3aUlHRnNhV2R1UFZ3aVkyVnVkR1Z5WENJZ2MzUjViR1U5WENKMFpYaDBMV0ZzYVdkdU9tTmxiblJsY2x3aVBqeHpjR0Z1SUhOMGVXeGxQVndpWm05dWRDMXphWHBsT2pFeUxqQndkRHRtYjI1MExXWmhiV2xzZVRvbWNYVnZkRHRVYVcxbGN5Qk9aWGNnVW05dFlXNG1jWFZ2ZERzc2MyVnlhV1k3YlhOdkxXWmhjbVZoYzNRdGJHRnVaM1ZoWjJVNlVsVmNJajdSZ3RDOVBHODZjRDQ4WEM5dk9uQStQRnd2YzNCaGJqNDhYQzl3UGx4eVhHNDhYQzkwWkQ1Y2NseHVQSFJrSUhkcFpIUm9QVndpTmpSY0lpQmpiMnh6Y0dGdVBWd2lNbHdpSUhOMGVXeGxQVndpZDJsa2RHZzZORGd1TUhCME8ySnZjbVJsY2pwemIyeHBaQ0IzYVc1a2IzZDBaWGgwSURFdU1IQjBPMkp2Y21SbGNpMXNaV1owT201dmJtVTdjR0ZrWkdsdVp6b3dZMjBnTlM0MGNIUWdNR050SURVdU5IQjBPMmhsYVdkb2REb3hOUzQzTlhCMFhDSStYSEpjYmp4d0lHTnNZWE56UFZ3aVRYTnZUbTl5YldGc1hDSWdZV3hwWjI0OVhDSmpaVzUwWlhKY0lpQnpkSGxzWlQxY0luUmxlSFF0WVd4cFoyNDZZMlZ1ZEdWeVhDSStQSE53WVc0Z2MzUjViR1U5WENKbWIyNTBMWE5wZW1VNk1USXVNSEIwTzJadmJuUXRabUZ0YVd4NU9pWnhkVzkwTzFScGJXVnpJRTVsZHlCU2IyMWhiaVp4ZFc5ME95eHpaWEpwWmp0dGMyOHRabUZ5WldGemRDMXNZVzVuZFdGblpUcFNWVndpUGpBc05UWThienB3UGp4Y0wyODZjRDQ4WEM5emNHRnVQanhjTDNBK1hISmNianhjTDNSa1BseHlYRzQ4ZEdRZ2QybGtkR2c5WENJM09Wd2lJR052YkhOd1lXNDlYQ0l5WENJZ2MzUjViR1U5WENKM2FXUjBhRG8xT1M0d2NIUTdZbTl5WkdWeU9uTnZiR2xrSUhkcGJtUnZkM1JsZUhRZ01TNHdjSFE3WW05eVpHVnlMV3hsWm5RNmJtOXVaVHR3WVdSa2FXNW5PakJqYlNBMUxqUndkQ0F3WTIwZ05TNDBjSFE3YUdWcFoyaDBPakUxTGpjMWNIUmNJajVjY2x4dVBIQWdZMnhoYzNNOVhDSk5jMjlPYjNKdFlXeGNJaUJoYkdsbmJqMWNJbU5sYm5SbGNsd2lJSE4wZVd4bFBWd2lkR1Y0ZEMxaGJHbG5ianBqWlc1MFpYSmNJajQ4YzNCaGJpQnpkSGxzWlQxY0ltWnZiblF0YzJsNlpUb3hNaTR3Y0hRN1ptOXVkQzFtWVcxcGJIazZKbkYxYjNRN1ZHbHRaWE1nVG1WM0lGSnZiV0Z1Sm5GMWIzUTdMSE5sY21sbU8yMXpieTFtWVhKbFlYTjBMV3hoYm1kMVlXZGxPbEpWWENJK05qWWdNREUyTERBd1BHODZjRDQ4WEM5dk9uQStQRnd2YzNCaGJqNDhYQzl3UGx4eVhHNDhYQzkwWkQ1Y2NseHVQSFJrSUhkcFpIUm9QVndpTVRNelhDSWdZMjlzYzNCaGJqMWNJak5jSWlCemRIbHNaVDFjSW5kcFpIUm9PakV3TUM0d2NIUTdZbTl5WkdWeU9uTnZiR2xrSUhkcGJtUnZkM1JsZUhRZ01TNHdjSFE3WW05eVpHVnlMV3hsWm5RNmJtOXVaVHR3WVdSa2FXNW5PakJqYlNBMUxqUndkQ0F3WTIwZ05TNDBjSFE3YUdWcFoyaDBPakUxTGpjMWNIUmNJajVjY2x4dVBIQWdZMnhoYzNNOVhDSk5jMjlPYjNKdFlXeGNJaUJoYkdsbmJqMWNJbU5sYm5SbGNsd2lJSE4wZVd4bFBWd2lkR1Y0ZEMxaGJHbG5ianBqWlc1MFpYSmNJajQ4YzNCaGJpQnpkSGxzWlQxY0ltWnZiblF0YzJsNlpUb3hNaTR3Y0hRN1ptOXVkQzFtWVcxcGJIazZKbkYxYjNRN1ZHbHRaWE1nVG1WM0lGSnZiV0Z1Sm5GMWIzUTdMSE5sY21sbU8yMXpieTFtWVhKbFlYTjBMV3hoYm1kMVlXZGxPbEpWWENJKzBKSFJnTkN3MFlMUmdkQzZQRzg2Y0Q0OFhDOXZPbkErUEZ3dmMzQmhiajQ4WEM5d1BseHlYRzQ4WEM5MFpENWNjbHh1UEhSa0lITjBlV3hsUFZ3aVltOXlaR1Z5T201dmJtVTdjR0ZrWkdsdVp6b3dZMjBnTUdOdElEQmpiU0F3WTIxY0lpQjNhV1IwYUQxY0lqSXhNbHdpSUdOdmJITndZVzQ5WENJeVhDSStYSEpjYmp4d0lHTnNZWE56UFZ3aVRYTnZUbTl5YldGc1hDSStKbTVpYzNBN1BGd3ZjRDVjY2x4dVBGd3ZkR1ErWEhKY2JqeGNMM1J5UGx4eVhHNDhkSElnYzNSNWJHVTlYQ0pvWldsbmFIUTZNVFV1TnpWd2RGd2lQbHh5WEc0OGRHUWdkMmxrZEdnOVhDSTBNRE5jSWlCdWIzZHlZWEE5WENKY0lpQjJZV3hwWjI0OVhDSmliM1IwYjIxY0lpQnpkSGxzWlQxY0luZHBaSFJvT2pNd01pNHdjSFE3WW05eVpHVnlPbk52Ykdsa0lIZHBibVJ2ZDNSbGVIUWdNUzR3Y0hRN1ltOXlaR1Z5TFhSdmNEcHViMjVsTzNCaFpHUnBibWM2TUdOdElEVXVOSEIwSURCamJTQTFMalJ3ZER0b1pXbG5hSFE2TVRVdU56VndkRndpUGx4eVhHNDhjQ0JqYkdGemN6MWNJazF6YjA1dmNtMWhiRndpUGp4emNHRnVJSE4wZVd4bFBWd2labTl1ZEMxemFYcGxPakV5TGpCd2REdGpiMnh2Y2pwaWJHRmphenR0YzI4dFptRnlaV0Z6ZEMxc1lXNW5kV0ZuWlRwU1ZWd2lQdENhMFlEUmc5Q3pJTkdCMFlMUXNOQzcwWXpRdmRDKzBMa2dNVGpRdk5DOElOQ2gwWUl6UEc4NmNENDhYQzl2T25BK1BGd3ZjM0JoYmo0OFhDOXdQbHh5WEc0OFhDOTBaRDVjY2x4dVBIUmtJSGRwWkhSb1BWd2lOalJjSWlCemRIbHNaVDFjSW5kcFpIUm9PalE0TGpCd2REdGliM0prWlhJdGRHOXdPbTV2Ym1VN1ltOXlaR1Z5TFd4bFpuUTZibTl1WlR0aWIzSmtaWEl0WW05MGRHOXRPbk52Ykdsa0lIZHBibVJ2ZDNSbGVIUWdNUzR3Y0hRN1ltOXlaR1Z5TFhKcFoyaDBPbk52Ykdsa0lIZHBibVJ2ZDNSbGVIUWdNUzR3Y0hRN2NHRmtaR2x1Wnpvd1kyMGdOUzQwY0hRZ01HTnRJRFV1TkhCME8yaGxhV2RvZERveE5TNDNOWEIwWENJK1hISmNianh3SUdOc1lYTnpQVndpVFhOdlRtOXliV0ZzWENJZ1lXeHBaMjQ5WENKalpXNTBaWEpjSWlCemRIbHNaVDFjSW5SbGVIUXRZV3hwWjI0NlkyVnVkR1Z5WENJK1BITndZVzRnYzNSNWJHVTlYQ0ptYjI1MExYTnBlbVU2TVRJdU1IQjBPMlp2Ym5RdFptRnRhV3g1T2laeGRXOTBPMVJwYldWeklFNWxkeUJTYjIxaGJpWnhkVzkwT3l4elpYSnBaanR0YzI4dFptRnlaV0Z6ZEMxc1lXNW5kV0ZuWlRwU1ZWd2lQdEdDMEwwOGJ6cHdQanhjTDI4NmNENDhYQzl6Y0dGdVBqeGNMM0ErWEhKY2JqeGNMM1JrUGx4eVhHNDhkR1FnZDJsa2RHZzlYQ0kyTkZ3aUlHTnZiSE53WVc0OVhDSXlYQ0lnYzNSNWJHVTlYQ0ozYVdSMGFEbzBPQzR3Y0hRN1ltOXlaR1Z5TFhSdmNEcHViMjVsTzJKdmNtUmxjaTFzWldaME9tNXZibVU3WW05eVpHVnlMV0p2ZEhSdmJUcHpiMnhwWkNCM2FXNWtiM2QwWlhoMElERXVNSEIwTzJKdmNtUmxjaTF5YVdkb2REcHpiMnhwWkNCM2FXNWtiM2QwWlhoMElERXVNSEIwTzNCaFpHUnBibWM2TUdOdElEVXVOSEIwSURCamJTQTFMalJ3ZER0b1pXbG5hSFE2TVRVdU56VndkRndpUGx4eVhHNDhjQ0JqYkdGemN6MWNJazF6YjA1dmNtMWhiRndpSUdGc2FXZHVQVndpWTJWdWRHVnlYQ0lnYzNSNWJHVTlYQ0owWlhoMExXRnNhV2R1T21ObGJuUmxjbHdpUGp4emNHRnVJSE4wZVd4bFBWd2labTl1ZEMxemFYcGxPakV5TGpCd2REdG1iMjUwTFdaaGJXbHNlVG9tY1hWdmREdFVhVzFsY3lCT1pYY2dVbTl0WVc0bWNYVnZkRHNzYzJWeWFXWTdiWE52TFdaaGNtVmhjM1F0YkdGdVozVmhaMlU2VWxWY0lqNHdMRE0wUEc4NmNENDhYQzl2T25BK1BGd3ZjM0JoYmo0OFhDOXdQbHh5WEc0OFhDOTBaRDVjY2x4dVBIUmtJSGRwWkhSb1BWd2lOemxjSWlCamIyeHpjR0Z1UFZ3aU1sd2lJSE4wZVd4bFBWd2lkMmxrZEdnNk5Ua3VNSEIwTzJKdmNtUmxjaTEwYjNBNmJtOXVaVHRpYjNKa1pYSXRiR1ZtZERwdWIyNWxPMkp2Y21SbGNpMWliM1IwYjIwNmMyOXNhV1FnZDJsdVpHOTNkR1Y0ZENBeExqQndkRHRpYjNKa1pYSXRjbWxuYUhRNmMyOXNhV1FnZDJsdVpHOTNkR1Y0ZENBeExqQndkRHR3WVdSa2FXNW5PakJqYlNBMUxqUndkQ0F3WTIwZ05TNDBjSFE3YUdWcFoyaDBPakUxTGpjMWNIUmNJajVjY2x4dVBIQWdZMnhoYzNNOVhDSk5jMjlPYjNKdFlXeGNJaUJoYkdsbmJqMWNJbU5sYm5SbGNsd2lJSE4wZVd4bFBWd2lkR1Y0ZEMxaGJHbG5ianBqWlc1MFpYSmNJajQ4YzNCaGJpQnpkSGxzWlQxY0ltWnZiblF0YzJsNlpUb3hNaTR3Y0hRN1ptOXVkQzFtWVcxcGJIazZKbkYxYjNRN1ZHbHRaWE1nVG1WM0lGSnZiV0Z1Sm5GMWIzUTdMSE5sY21sbU8yMXpieTFtWVhKbFlYTjBMV3hoYm1kMVlXZGxPbEpWWENJK05qWWdNREUyTERBd1BHODZjRDQ4WEM5dk9uQStQRnd2YzNCaGJqNDhYQzl3UGx4eVhHNDhYQzkwWkQ1Y2NseHVQSFJrSUhkcFpIUm9QVndpTVRNelhDSWdZMjlzYzNCaGJqMWNJak5jSWlCemRIbHNaVDFjSW5kcFpIUm9PakV3TUM0d2NIUTdZbTl5WkdWeUxYUnZjRHB1YjI1bE8ySnZjbVJsY2kxc1pXWjBPbTV2Ym1VN1ltOXlaR1Z5TFdKdmRIUnZiVHB6YjJ4cFpDQjNhVzVrYjNkMFpYaDBJREV1TUhCME8ySnZjbVJsY2kxeWFXZG9kRHB6YjJ4cFpDQjNhVzVrYjNkMFpYaDBJREV1TUhCME8zQmhaR1JwYm1jNk1HTnRJRFV1TkhCMElEQmpiU0ExTGpSd2REdG9aV2xuYUhRNk1UVXVOelZ3ZEZ3aVBseHlYRzQ4Y0NCamJHRnpjejFjSWsxemIwNXZjbTFoYkZ3aUlHRnNhV2R1UFZ3aVkyVnVkR1Z5WENJZ2MzUjViR1U5WENKMFpYaDBMV0ZzYVdkdU9tTmxiblJsY2x3aVBqeHpjR0Z1SUhOMGVXeGxQVndpWm05dWRDMXphWHBsT2pFeUxqQndkRHRtYjI1MExXWmhiV2xzZVRvbWNYVnZkRHRVYVcxbGN5Qk9aWGNnVW05dFlXNG1jWFZ2ZERzc2MyVnlhV1k3YlhOdkxXWmhjbVZoYzNRdGJHRnVaM1ZoWjJVNlVsVmNJajdRa2RHQTBMRFJndEdCMExvOGJ6cHdQanhjTDI4NmNENDhYQzl6Y0dGdVBqeGNMM0ErWEhKY2JqeGNMM1JrUGx4eVhHNDhkR1FnYzNSNWJHVTlYQ0ppYjNKa1pYSTZibTl1WlR0d1lXUmthVzVuT2pCamJTQXdZMjBnTUdOdElEQmpiVndpSUhkcFpIUm9QVndpTWpFeVhDSWdZMjlzYzNCaGJqMWNJakpjSWo1Y2NseHVQSEFnWTJ4aGMzTTlYQ0pOYzI5T2IzSnRZV3hjSWo0bWJtSnpjRHM4WEM5d1BseHlYRzQ4WEM5MFpENWNjbHh1UEZ3dmRISStYSEpjYmp4MGNpQnpkSGxzWlQxY0ltaGxhV2RvZERveE5TNDNOWEIwWENJK1hISmNiangwWkNCM2FXUjBhRDFjSWpRd00xd2lJRzV2ZDNKaGNEMWNJbHdpSUhaaGJHbG5iajFjSW1KdmRIUnZiVndpSUhOMGVXeGxQVndpZDJsa2RHZzZNekF5TGpCd2REdGliM0prWlhJNmMyOXNhV1FnZDJsdVpHOTNkR1Y0ZENBeExqQndkRHRpYjNKa1pYSXRkRzl3T201dmJtVTdjR0ZrWkdsdVp6b3dZMjBnTlM0MGNIUWdNR050SURVdU5IQjBPMmhsYVdkb2REb3hOUzQzTlhCMFhDSStYSEpjYmp4d0lHTnNZWE56UFZ3aVRYTnZUbTl5YldGc1hDSStQSE53WVc0Z2MzUjViR1U5WENKbWIyNTBMWE5wZW1VNk1USXVNSEIwTzJOdmJHOXlPbUpzWVdOck8yMXpieTFtWVhKbFlYTjBMV3hoYm1kMVlXZGxPbEpWWENJKzBKdlF1TkdCMFlJZ005R0ZNVFV3TU5HRk5qQXdNQ0RRb2RHQ01EblFrekxRb1NEUWs5Q2UwS0hRb2lBeE5EWXpOeTA0T1R4dk9uQStQRnd2Ynpwd1BqeGNMM053WVc0K1BGd3ZjRDVjY2x4dVBGd3ZkR1ErWEhKY2JqeDBaQ0IzYVdSMGFEMWNJalkwWENJZ2MzUjViR1U5WENKM2FXUjBhRG8wT0M0d2NIUTdZbTl5WkdWeUxYUnZjRHB1YjI1bE8ySnZjbVJsY2kxc1pXWjBPbTV2Ym1VN1ltOXlaR1Z5TFdKdmRIUnZiVHB6YjJ4cFpDQjNhVzVrYjNkMFpYaDBJREV1TUhCME8ySnZjbVJsY2kxeWFXZG9kRHB6YjJ4cFpDQjNhVzVrYjNkMFpYaDBJREV1TUhCME8zQmhaR1JwYm1jNk1HTnRJRFV1TkhCMElEQmpiU0ExTGpSd2REdG9aV2xuYUhRNk1UVXVOelZ3ZEZ3aVBseHlYRzQ4Y0NCamJHRnpjejFjSWsxemIwNXZjbTFoYkZ3aUlHRnNhV2R1UFZ3aVkyVnVkR1Z5WENJZ2MzUjViR1U5WENKMFpYaDBMV0ZzYVdkdU9tTmxiblJsY2x3aVBqeHpjR0Z1SUhOMGVXeGxQVndpWm05dWRDMXphWHBsT2pFeUxqQndkRHRtYjI1MExXWmhiV2xzZVRvbWNYVnZkRHRVYVcxbGN5Qk9aWGNnVW05dFlXNG1jWFZ2ZERzc2MyVnlhV1k3YlhOdkxXWmhjbVZoYzNRdGJHRnVaM1ZoWjJVNlVsVmNJajdSZ3RDOVBHODZjRDQ4WEM5dk9uQStQRnd2YzNCaGJqNDhYQzl3UGx4eVhHNDhYQzkwWkQ1Y2NseHVQSFJrSUhkcFpIUm9QVndpTmpSY0lpQmpiMnh6Y0dGdVBWd2lNbHdpSUhOMGVXeGxQVndpZDJsa2RHZzZORGd1TUhCME8ySnZjbVJsY2kxMGIzQTZibTl1WlR0aWIzSmtaWEl0YkdWbWREcHViMjVsTzJKdmNtUmxjaTFpYjNSMGIyMDZjMjlzYVdRZ2QybHVaRzkzZEdWNGRDQXhMakJ3ZER0aWIzSmtaWEl0Y21sbmFIUTZjMjlzYVdRZ2QybHVaRzkzZEdWNGRDQXhMakJ3ZER0d1lXUmthVzVuT2pCamJTQTFMalJ3ZENBd1kyMGdOUzQwY0hRN2FHVnBaMmgwT2pFMUxqYzFjSFJjSWo1Y2NseHVQSEFnWTJ4aGMzTTlYQ0pOYzI5T2IzSnRZV3hjSWlCaGJHbG5iajFjSW1ObGJuUmxjbHdpSUhOMGVXeGxQVndpZEdWNGRDMWhiR2xuYmpwalpXNTBaWEpjSWo0OGMzQmhiaUJ6ZEhsc1pUMWNJbVp2Ym5RdGMybDZaVG94TWk0d2NIUTdabTl1ZEMxbVlXMXBiSGs2Sm5GMWIzUTdWR2x0WlhNZ1RtVjNJRkp2YldGdUpuRjFiM1E3TEhObGNtbG1PMjF6YnkxbVlYSmxZWE4wTFd4aGJtZDFZV2RsT2xKVlhDSStOQ3d4T1R4dk9uQStQRnd2Ynpwd1BqeGNMM053WVc0K1BGd3ZjRDVjY2x4dVBGd3ZkR1ErWEhKY2JqeDBaQ0IzYVdSMGFEMWNJamM1WENJZ1kyOXNjM0JoYmoxY0lqSmNJaUJ6ZEhsc1pUMWNJbmRwWkhSb09qVTVMakJ3ZER0aWIzSmtaWEl0ZEc5d09tNXZibVU3WW05eVpHVnlMV3hsWm5RNmJtOXVaVHRpYjNKa1pYSXRZbTkwZEc5dE9uTnZiR2xrSUhkcGJtUnZkM1JsZUhRZ01TNHdjSFE3WW05eVpHVnlMWEpwWjJoME9uTnZiR2xrSUhkcGJtUnZkM1JsZUhRZ01TNHdjSFE3Y0dGa1pHbHVaem93WTIwZ05TNDBjSFFnTUdOdElEVXVOSEIwTzJobGFXZG9kRG94TlM0M05YQjBYQ0krWEhKY2JqeHdJR05zWVhOelBWd2lUWE52VG05eWJXRnNYQ0lnWVd4cFoyNDlYQ0pqWlc1MFpYSmNJaUJ6ZEhsc1pUMWNJblJsZUhRdFlXeHBaMjQ2WTJWdWRHVnlYQ0krUEhOd1lXNGdjM1I1YkdVOVhDSm1iMjUwTFhOcGVtVTZNVEl1TUhCME8yWnZiblF0Wm1GdGFXeDVPaVp4ZFc5ME8xUnBiV1Z6SUU1bGR5QlNiMjFoYmlaeGRXOTBPeXh6WlhKcFpqdHRjMjh0Wm1GeVpXRnpkQzFzWVc1bmRXRm5aVHBTVlZ3aVBqWTRJREF5Tml3d01EeHZPbkErUEZ3dmJ6cHdQanhjTDNOd1lXNCtQRnd2Y0Q1Y2NseHVQRnd2ZEdRK1hISmNiangwWkNCM2FXUjBhRDFjSWpFek0xd2lJR052YkhOd1lXNDlYQ0l6WENJZ2MzUjViR1U5WENKM2FXUjBhRG94TURBdU1IQjBPMkp2Y21SbGNpMTBiM0E2Ym05dVpUdGliM0prWlhJdGJHVm1kRHB1YjI1bE8ySnZjbVJsY2kxaWIzUjBiMjA2YzI5c2FXUWdkMmx1Wkc5M2RHVjRkQ0F4TGpCd2REdGliM0prWlhJdGNtbG5hSFE2YzI5c2FXUWdkMmx1Wkc5M2RHVjRkQ0F4TGpCd2REdHdZV1JrYVc1bk9qQmpiU0ExTGpSd2RDQXdZMjBnTlM0MGNIUTdhR1ZwWjJoME9qRTFMamMxY0hSY0lqNWNjbHh1UEhBZ1kyeGhjM005WENKTmMyOU9iM0p0WVd4Y0lpQmhiR2xuYmoxY0ltTmxiblJsY2x3aUlITjBlV3hsUFZ3aWRHVjRkQzFoYkdsbmJqcGpaVzUwWlhKY0lqNDhjM0JoYmlCemRIbHNaVDFjSW1admJuUXRjMmw2WlRveE1pNHdjSFE3Wm05dWRDMW1ZVzFwYkhrNkpuRjFiM1E3VkdsdFpYTWdUbVYzSUZKdmJXRnVKbkYxYjNRN0xITmxjbWxtTzIxemJ5MW1ZWEpsWVhOMExXeGhibWQxWVdkbE9sSlZYQ0krMEpIUmdOQ3cwWUxSZ2RDNlBHODZjRDQ4WEM5dk9uQStQRnd2YzNCaGJqNDhYQzl3UGx4eVhHNDhYQzkwWkQ1Y2NseHVQSFJrSUhOMGVXeGxQVndpWW05eVpHVnlPbTV2Ym1VN2NHRmtaR2x1Wnpvd1kyMGdNR050SURCamJTQXdZMjFjSWlCM2FXUjBhRDFjSWpJeE1sd2lJR052YkhOd1lXNDlYQ0l5WENJK1hISmNianh3SUdOc1lYTnpQVndpVFhOdlRtOXliV0ZzWENJK0ptNWljM0E3UEZ3dmNENWNjbHh1UEZ3dmRHUStYSEpjYmp4Y0wzUnlQbHh5WEc0OGRISWdhR1ZwWjJoMFBWd2lNRndpUGx4eVhHNDhkR1FnZDJsa2RHZzlYQ0kwTUROY0lpQnpkSGxzWlQxY0ltSnZjbVJsY2pwdWIyNWxYQ0krUEZ3dmRHUStYSEpjYmp4MFpDQjNhV1IwYUQxY0lqWTBYQ0lnYzNSNWJHVTlYQ0ppYjNKa1pYSTZibTl1WlZ3aVBqeGNMM1JrUGx4eVhHNDhkR1FnZDJsa2RHZzlYQ0kxTmx3aUlITjBlV3hsUFZ3aVltOXlaR1Z5T201dmJtVmNJajQ4WEM5MFpENWNjbHh1UEhSa0lIZHBaSFJvUFZ3aU9Gd2lJSE4wZVd4bFBWd2lZbTl5WkdWeU9tNXZibVZjSWo0OFhDOTBaRDVjY2x4dVBIUmtJSGRwWkhSb1BWd2lOVFpjSWlCemRIbHNaVDFjSW1KdmNtUmxjanB1YjI1bFhDSStQRnd2ZEdRK1hISmNiangwWkNCM2FXUjBhRDFjSWpJelhDSWdjM1I1YkdVOVhDSmliM0prWlhJNmJtOXVaVndpUGp4Y0wzUmtQbHh5WEc0OGRHUWdkMmxrZEdnOVhDSTBNVndpSUhOMGVXeGxQVndpWW05eVpHVnlPbTV2Ym1WY0lqNDhYQzkwWkQ1Y2NseHVQSFJrSUhkcFpIUm9QVndpTnpsY0lpQnpkSGxzWlQxY0ltSnZjbVJsY2pwdWIyNWxYQ0krUEZ3dmRHUStYSEpjYmp4MFpDQjNhV1IwYUQxY0lqRXpYQ0lnYzNSNWJHVTlYQ0ppYjNKa1pYSTZibTl1WlZ3aVBqeGNMM1JrUGx4eVhHNDhkR1FnZDJsa2RHZzlYQ0kzT1Z3aUlITjBlV3hsUFZ3aVltOXlaR1Z5T201dmJtVmNJajQ4WEM5MFpENWNjbHh1UEhSa0lIZHBaSFJvUFZ3aU1UTXpYQ0lnYzNSNWJHVTlYQ0ppYjNKa1pYSTZibTl1WlZ3aVBqeGNMM1JrUGx4eVhHNDhYQzkwY2o1Y2NseHVQRnd2ZEdKdlpIaytYSEpjYmp4Y0wzUmhZbXhsUGx4eVhHNDhjQ0JqYkdGemN6MWNJazF6YjA1dmNtMWhiRndpUGp4dk9uQStKbTVpYzNBN1BGd3ZienB3UGp4Y0wzQStYSEpjYmp4MFlXSnNaU0JqYkdGemN6MWNJazF6YjA1dmNtMWhiRlJoWW14bFhDSWdZbTl5WkdWeVBWd2lNRndpSUdObGJHeHpjR0ZqYVc1blBWd2lNRndpSUdObGJHeHdZV1JrYVc1blBWd2lNRndpSUhkcFpIUm9QVndpTUZ3aUlITjBlV3hsUFZ3aWQybGtkR2c2TnpFMkxqSTFjSFE3WW05eVpHVnlMV052Ykd4aGNITmxPbU52Ykd4aGNITmxYQ0krWEhKY2JqeDBZbTlrZVQ1Y2NseHVQSFJ5SUhOMGVXeGxQVndpYUdWcFoyaDBPakUxTGpjMWNIUmNJajVjY2x4dVBIUmtJSGRwWkhSb1BWd2lOREF6WENJZ2JtOTNjbUZ3UFZ3aVhDSWdkbUZzYVdkdVBWd2lZbTkwZEc5dFhDSWdjM1I1YkdVOVhDSjNhV1IwYURvek1ESXVNVFZ3ZER0d1lXUmthVzVuT2pCamJTQTFMalJ3ZENBd1kyMGdOUzQwY0hRN2FHVnBaMmgwT2pFMUxqYzFjSFJjSWo1Y2NseHVQSEFnWTJ4aGMzTTlYQ0pOYzI5T2IzSnRZV3hjSWo0OGMzQmhiaUJ6ZEhsc1pUMWNJbU52Ykc5eU9tSnNZV05yTzIxemJ5MW1ZWEpsWVhOMExXeGhibWQxWVdkbE9sSlZYQ0krMEpqUmdkQyswSnJRbEMzUWxOQyswTE15TURFNUx6QXdNemN0TVRnelBHODZjRDQ4WEM5dk9uQStQRnd2YzNCaGJqNDhYQzl3UGx4eVhHNDhYQzkwWkQ1Y2NseHVQSFJrSUhkcFpIUm9QVndpTVRJd1hDSWdibTkzY21Gd1BWd2lYQ0lnWTI5c2MzQmhiajFjSWpKY0lpQjJZV3hwWjI0OVhDSmliM1IwYjIxY0lpQnpkSGxzWlQxY0luZHBaSFJvT2prd0xqQTFjSFE3Y0dGa1pHbHVaem93WTIwZ05TNDBjSFFnTUdOdElEVXVOSEIwTzJobGFXZG9kRG94TlM0M05YQjBYQ0krWEhKY2JqeGNMM1JrUGx4eVhHNDhkR1FnZDJsa2RHZzlYQ0kyTkZ3aUlHNXZkM0poY0QxY0lsd2lJR052YkhOd1lXNDlYQ0l5WENJZ2RtRnNhV2R1UFZ3aVltOTBkRzl0WENJZ2MzUjViR1U5WENKM2FXUjBhRG8wT0M0d2NIUTdjR0ZrWkdsdVp6b3dZMjBnTlM0MGNIUWdNR050SURVdU5IQjBPMmhsYVdkb2REb3hOUzQzTlhCMFhDSStYSEpjYmp4Y0wzUmtQbHh5WEc0OGRHUWdkMmxrZEdnOVhDSTJORndpSUc1dmQzSmhjRDFjSWx3aUlHTnZiSE53WVc0OVhDSXlYQ0lnZG1Gc2FXZHVQVndpWW05MGRHOXRYQ0lnYzNSNWJHVTlYQ0ozYVdSMGFEbzBPQzR3Y0hRN2NHRmtaR2x1Wnpvd1kyMGdOUzQwY0hRZ01HTnRJRFV1TkhCME8yaGxhV2RvZERveE5TNDNOWEIwWENJK1hISmNianhjTDNSa1BseHlYRzQ4ZEdRZ2QybGtkR2c5WENJM09Wd2lJRzV2ZDNKaGNEMWNJbHdpSUhaaGJHbG5iajFjSW1KdmRIUnZiVndpSUhOMGVXeGxQVndpZDJsa2RHZzZOVGt1TUhCME8zQmhaR1JwYm1jNk1HTnRJRFV1TkhCMElEQmpiU0ExTGpSd2REdG9aV2xuYUhRNk1UVXVOelZ3ZEZ3aVBseHlYRzQ4WEM5MFpENWNjbHh1UEhSa0lIZHBaSFJvUFZ3aU9USmNJaUJ1YjNkeVlYQTlYQ0pjSWlCamIyeHpjR0Z1UFZ3aU1sd2lJSFpoYkdsbmJqMWNJbUp2ZEhSdmJWd2lJSE4wZVd4bFBWd2lkMmxrZEdnNk5qa3VNSEIwTzNCaFpHUnBibWM2TUdOdElEVXVOSEIwSURCamJTQTFMalJ3ZER0b1pXbG5hSFE2TVRVdU56VndkRndpUGx4eVhHNDhYQzkwWkQ1Y2NseHVQSFJrSUhkcFpIUm9QVndpTVRNelhDSWdibTkzY21Gd1BWd2lYQ0lnYzNSNWJHVTlYQ0ozYVdSMGFEb3hNREF1TURWd2REdHdZV1JrYVc1bk9qQmpiU0ExTGpSd2RDQXdZMjBnTlM0MGNIUTdhR1ZwWjJoME9qRTFMamMxY0hSY0lqNWNjbHh1UEZ3dmRHUStYSEpjYmp4Y0wzUnlQbHh5WEc0OGRISWdjM1I1YkdVOVhDSm9aV2xuYUhRNk1UVXVOelZ3ZEZ3aVBseHlYRzQ4ZEdRZ2QybGtkR2c5WENJME1ETmNJaUJ1YjNkeVlYQTlYQ0pjSWlCMllXeHBaMjQ5WENKaWIzUjBiMjFjSWlCemRIbHNaVDFjSW5kcFpIUm9Pak13TWk0eE5YQjBPMkp2Y21SbGNqcHpiMnhwWkNCM2FXNWtiM2QwWlhoMElERXVNSEIwTzNCaFpHUnBibWM2TUdOdElEVXVOSEIwSURCamJTQTFMalJ3ZER0b1pXbG5hSFE2TVRVdU56VndkRndpUGx4eVhHNDhjQ0JqYkdGemN6MWNJazF6YjA1dmNtMWhiRndpUGp4emNHRnVJSE4wZVd4bFBWd2labTl1ZEMxemFYcGxPakV5TGpCd2REdHRjMjh0Wm1GeVpXRnpkQzFzWVc1bmRXRm5aVHBTVlZ3aVB0Q2IwTGpSZ2RHQ0lEYlJoVEUxTUREUmhUWXdNREFnMEtIUmdqTWcwSlBRbnRDaDBLSWdNVGs1TURNdE1qQXhOVHh2T25BK1BGd3ZienB3UGp4Y0wzTndZVzQrUEZ3dmNENWNjbHh1UEZ3dmRHUStYSEpjYmp4MFpDQjNhV1IwYUQxY0lqWTBYQ0lnYzNSNWJHVTlYQ0ozYVdSMGFEbzBPQzR3Y0hRN1ltOXlaR1Z5T25OdmJHbGtJSGRwYm1SdmQzUmxlSFFnTVM0d2NIUTdZbTl5WkdWeUxXeGxablE2Ym05dVpUdHdZV1JrYVc1bk9qQmpiU0ExTGpSd2RDQXdZMjBnTlM0MGNIUTdhR1ZwWjJoME9qRTFMamMxY0hSY0lqNWNjbHh1UEhBZ1kyeGhjM005WENKTmMyOU9iM0p0WVd4Y0lpQmhiR2xuYmoxY0ltTmxiblJsY2x3aUlITjBlV3hsUFZ3aWRHVjRkQzFoYkdsbmJqcGpaVzUwWlhKY0lqNDhjM0JoYmlCemRIbHNaVDFjSW1admJuUXRjMmw2WlRveE1pNHdjSFE3Wm05dWRDMW1ZVzFwYkhrNkpuRjFiM1E3VkdsdFpYTWdUbVYzSUZKdmJXRnVKbkYxYjNRN0xITmxjbWxtTzIxemJ5MW1ZWEpsWVhOMExXeGhibWQxWVdkbE9sSlZYQ0krMFlMUXZUeHZPbkErUEZ3dmJ6cHdQanhjTDNOd1lXNCtQRnd2Y0Q1Y2NseHVQRnd2ZEdRK1hISmNiangwWkNCM2FXUjBhRDFjSWpZMFhDSWdZMjlzYzNCaGJqMWNJakpjSWlCemRIbHNaVDFjSW5kcFpIUm9PalE0TGpCd2REdGliM0prWlhJNmMyOXNhV1FnZDJsdVpHOTNkR1Y0ZENBeExqQndkRHRpYjNKa1pYSXRiR1ZtZERwdWIyNWxPM0JoWkdScGJtYzZNR050SURVdU5IQjBJREJqYlNBMUxqUndkRHRvWldsbmFIUTZNVFV1TnpWd2RGd2lQbHh5WEc0OGNDQmpiR0Z6Y3oxY0lrMXpiMDV2Y20xaGJGd2lJR0ZzYVdkdVBWd2lZMlZ1ZEdWeVhDSWdjM1I1YkdVOVhDSjBaWGgwTFdGc2FXZHVPbU5sYm5SbGNsd2lQanh6Y0dGdUlITjBlV3hsUFZ3aVptOXVkQzF6YVhwbE9qRXlMakJ3ZER0bWIyNTBMV1poYldsc2VUb21jWFZ2ZER0VWFXMWxjeUJPWlhjZ1VtOXRZVzRtY1hWdmREc3NjMlZ5YVdZN2JYTnZMV1poY21WaGMzUXRiR0Z1WjNWaFoyVTZVbFZjSWo0eE5Td3dNRHh2T25BK1BGd3ZienB3UGp4Y0wzTndZVzQrUEZ3dmNENWNjbHh1UEZ3dmRHUStYSEpjYmp4MFpDQjNhV1IwYUQxY0lqYzVYQ0lnWTI5c2MzQmhiajFjSWpKY0lpQnpkSGxzWlQxY0luZHBaSFJvT2pVNUxqQndkRHRpYjNKa1pYSTZjMjlzYVdRZ2QybHVaRzkzZEdWNGRDQXhMakJ3ZER0aWIzSmtaWEl0YkdWbWREcHViMjVsTzNCaFpHUnBibWM2TUdOdElEVXVOSEIwSURCamJTQTFMalJ3ZER0b1pXbG5hSFE2TVRVdU56VndkRndpUGx4eVhHNDhjQ0JqYkdGemN6MWNJazF6YjA1dmNtMWhiRndpSUdGc2FXZHVQVndpWTJWdWRHVnlYQ0lnYzNSNWJHVTlYQ0owWlhoMExXRnNhV2R1T21ObGJuUmxjbHdpUGp4emNHRnVJSE4wZVd4bFBWd2labTl1ZEMxemFYcGxPakV5TGpCd2REdG1iMjUwTFdaaGJXbHNlVG9tY1hWdmREdFVhVzFsY3lCT1pYY2dVbTl0WVc0bWNYVnZkRHNzYzJWeWFXWTdiWE52TFdaaGNtVmhjM1F0YkdGdVozVmhaMlU2VWxWY0lqNDJOQ0F5T0RVc01EQThienB3UGp4Y0wyODZjRDQ4WEM5emNHRnVQanhjTDNBK1hISmNianhjTDNSa1BseHlYRzQ4ZEdRZ2QybGtkR2c5WENJeE16TmNJaUJqYjJ4emNHRnVQVndpTTF3aUlITjBlV3hsUFZ3aWQybGtkR2c2TVRBd0xqQTFjSFE3WW05eVpHVnlMWFJ2Y0RwemIyeHBaQ0IzYVc1a2IzZDBaWGgwSURFdU1IQjBPMkp2Y21SbGNpMXNaV1owT201dmJtVTdZbTl5WkdWeUxXSnZkSFJ2YlRwemIyeHBaQ0IzYVc1a2IzZDBaWGgwSURFdU1IQjBPMkp2Y21SbGNpMXlhV2RvZERwdWIyNWxPM0JoWkdScGJtYzZNR050SURVdU5IQjBJREJqYlNBMUxqUndkRHRvWldsbmFIUTZNVFV1TnpWd2RGd2lQbHh5WEc0OGNDQmpiR0Z6Y3oxY0lrMXpiMDV2Y20xaGJGd2lJR0ZzYVdkdVBWd2lZMlZ1ZEdWeVhDSWdjM1I1YkdVOVhDSjBaWGgwTFdGc2FXZHVPbU5sYm5SbGNsd2lQanh6Y0dGdUlITjBlV3hsUFZ3aVptOXVkQzF6YVhwbE9qRXlMakJ3ZER0bWIyNTBMV1poYldsc2VUb21jWFZ2ZER0VWFXMWxjeUJPWlhjZ1VtOXRZVzRtY1hWdmREc3NjMlZ5YVdZN2JYTnZMV1poY21WaGMzUXRiR0Z1WjNWaFoyVTZVbFZjSWo3UWtkR0EwTERSZ3RHQjBMbzhienB3UGp4Y0wyODZjRDQ4WEM5emNHRnVQanhjTDNBK1hISmNianhjTDNSa1BseHlYRzQ4ZEdRZ2MzUjViR1U5WENKaWIzSmtaWEk2Ym05dVpUdHdZV1JrYVc1bk9qQmpiU0F3WTIwZ01HTnRJREJqYlZ3aUlIZHBaSFJvUFZ3aU1qRXlYQ0lnWTI5c2MzQmhiajFjSWpKY0lqNWNjbHh1UEhBZ1kyeGhjM005WENKTmMyOU9iM0p0WVd4Y0lqNG1ibUp6Y0RzOFhDOXdQbHh5WEc0OFhDOTBaRDVjY2x4dVBGd3ZkSEkrWEhKY2JqeDBjaUJvWldsbmFIUTlYQ0l3WENJK1hISmNiangwWkNCM2FXUjBhRDFjSWpRd00xd2lJSE4wZVd4bFBWd2lZbTl5WkdWeU9tNXZibVZjSWo0OFhDOTBaRDVjY2x4dVBIUmtJSGRwWkhSb1BWd2lOalJjSWlCemRIbHNaVDFjSW1KdmNtUmxjanB1YjI1bFhDSStQRnd2ZEdRK1hISmNiangwWkNCM2FXUjBhRDFjSWpVMlhDSWdjM1I1YkdVOVhDSmliM0prWlhJNmJtOXVaVndpUGp4Y0wzUmtQbHh5WEc0OGRHUWdkMmxrZEdnOVhDSTRYQ0lnYzNSNWJHVTlYQ0ppYjNKa1pYSTZibTl1WlZ3aVBqeGNMM1JrUGx4eVhHNDhkR1FnZDJsa2RHZzlYQ0kxTmx3aUlITjBlV3hsUFZ3aVltOXlaR1Z5T201dmJtVmNJajQ4WEM5MFpENWNjbHh1UEhSa0lIZHBaSFJvUFZ3aU1qTmNJaUJ6ZEhsc1pUMWNJbUp2Y21SbGNqcHViMjVsWENJK1BGd3ZkR1ErWEhKY2JqeDBaQ0IzYVdSMGFEMWNJalF4WENJZ2MzUjViR1U5WENKaWIzSmtaWEk2Ym05dVpWd2lQanhjTDNSa1BseHlYRzQ4ZEdRZ2QybGtkR2c5WENJM09Wd2lJSE4wZVd4bFBWd2lZbTl5WkdWeU9tNXZibVZjSWo0OFhDOTBaRDVjY2x4dVBIUmtJSGRwWkhSb1BWd2lNVE5jSWlCemRIbHNaVDFjSW1KdmNtUmxjanB1YjI1bFhDSStQRnd2ZEdRK1hISmNiangwWkNCM2FXUjBhRDFjSWpjNVhDSWdjM1I1YkdVOVhDSmliM0prWlhJNmJtOXVaVndpUGp4Y0wzUmtQbHh5WEc0OGRHUWdkMmxrZEdnOVhDSXhNek5jSWlCemRIbHNaVDFjSW1KdmNtUmxjanB1YjI1bFhDSStQRnd2ZEdRK1hISmNianhjTDNSeVBseHlYRzQ4WEM5MFltOWtlVDVjY2x4dVBGd3ZkR0ZpYkdVK1hISmNianh3SUdOc1lYTnpQVndpVFhOdlRtOXliV0ZzWENJK1BHODZjRDRtYm1KemNEczhYQzl2T25BK1BGd3ZjRDVjY2x4dVBIQWdZMnhoYzNNOVhDSk5jMjlPYjNKdFlXeGNJajQ4Ynpwd1BpWnVZbk53T3p4Y0wyODZjRDQ4WEM5d1BseHlYRzQ4Y0NCamJHRnpjejFjSWsxemIwNXZjbTFoYkZ3aVBqeHpjR0Z1SUhOMGVXeGxQVndpYlhOdkxXWmhjbVZoYzNRdGJHRnVaM1ZoWjJVNlVsVmNJajdRbk5DMTBMM1F0ZEMwMExiUXRkR0FJTkNlMEp6UW90Q2hJRHh2T25BK1BGd3ZienB3UGp4Y0wzTndZVzQrUEZ3dmNENWNjbHh1UEhBZ1kyeGhjM005WENKTmMyOU9iM0p0WVd4Y0lqNDhjM0JoYmlCemRIbHNaVDFjSW0xemJ5MW1ZWEpsWVhOMExXeGhibWQxWVdkbE9sSlZYQ0krMEp6UXNOQzcwWkhRdmRDNjBMalF2U0RRa3RDdzBZSFF1TkM3MExqUXVUeHZPbkErUEZ3dmJ6cHdQanhjTDNOd1lXNCtQRnd2Y0Q1Y2NseHVQSEFnWTJ4aGMzTTlYQ0pOYzI5T2IzSnRZV3hjSWo0OGMzQmhiaUJ6ZEhsc1pUMWNJbTF6YnkxbVlYSmxZWE4wTFd4aGJtZDFZV2RsT2xKVlhDSSswSjdRbnRDZUlDWnNZWEYxYnp2UW1OQ2gwSjRtY21GeGRXODdJTkN6TGlEUW10R0EwTERSZ2RDOTBMN1JqOUdBMFlIUXVqeHZPbkErUEZ3dmJ6cHdQanhjTDNOd1lXNCtQRnd2Y0Q1Y2NseHVQSEFnWTJ4aGMzTTlYQ0pOYzI5T2IzSnRZV3hjSWo0OGMzQmhiaUJ6ZEhsc1pUMWNJbTF6YnkxbVlYSmxZWE4wTFd4aGJtZDFZV2RsT2xKVlhDSSswS0l1MFlBdUtETTVNU2t5TlRZdE16RXRPRFlzSU5DNjBMN1JnQzRvTURBeUtUTXhMVGcyUEc4NmNENDhYQzl2T25BK1BGd3ZjM0JoYmo0OFhDOXdQbHh5WEc0OGNDQmpiR0Z6Y3oxY0lrMXpiMDV2Y20xaGJGd2lQanh6Y0dGdUlHeGhibWM5WENKRlRpMVZVMXdpSUhOMGVXeGxQVndpYlhOdkxXWmhjbVZoYzNRdGJHRnVaM1ZoWjJVNlVsVmNJajQ4WVNCb2NtVm1QVndpYldGcGJIUnZPbFpoYzJsc2FYa3VUV0ZzWlc1cmFXNUFhWE52TFhObGNuWXVZMjl0WENJK1BITndZVzRnYzNSNWJHVTlYQ0pqYjJ4dmNqcGliSFZsWENJK1ZtRnphV3hwZVR4Y0wzTndZVzQrUEhOd1lXNGdiR0Z1WnoxY0lsSlZYQ0lnYzNSNWJHVTlYQ0pqYjJ4dmNqcGliSFZsWENJK0xqeGNMM053WVc0K1BITndZVzRnYzNSNWJHVTlYQ0pqYjJ4dmNqcGliSFZsWENJK1RXRnNaVzVyYVc0OFhDOXpjR0Z1UGp4emNHRnVJR3hoYm1jOVhDSlNWVndpSUhOMGVXeGxQVndpWTI5c2IzSTZZbXgxWlZ3aVBrQThYQzl6Y0dGdVBqeHpjR0Z1SUhOMGVXeGxQVndpWTI5c2IzSTZZbXgxWlZ3aVBtbHpienhjTDNOd1lXNCtQSE53WVc0Z2JHRnVaejFjSWxKVlhDSWdjM1I1YkdVOVhDSmpiMnh2Y2pwaWJIVmxYQ0krTFR4Y0wzTndZVzQrUEhOd1lXNGdjM1I1YkdVOVhDSmpiMnh2Y2pwaWJIVmxYQ0krYzJWeWRqeGNMM053WVc0K1BITndZVzRnYkdGdVp6MWNJbEpWWENJZ2MzUjViR1U5WENKamIyeHZjanBpYkhWbFhDSStManhjTDNOd1lXNCtQSE53WVc0Z2MzUjViR1U5WENKamIyeHZjanBpYkhWbFhDSStZMjl0UEZ3dmMzQmhiajQ4WEM5aFBqeGNMM053WVc0K1BITndZVzRnYzNSNWJHVTlYQ0p0YzI4dFptRnlaV0Z6ZEMxc1lXNW5kV0ZuWlRwU1ZWd2lQanh2T25BK1BGd3ZienB3UGp4Y0wzTndZVzQrUEZ3dmNENWNjbHh1UEhBZ1kyeGhjM005WENKTmMyOU9iM0p0WVd4Y0lqNDhienB3UGladVluTndPenhjTDI4NmNENDhYQzl3UGx4eVhHNDhYQzlrYVhZK1hISmNianhpY2o1Y2NseHVQR1p2Ym5RZ2MybDZaVDFjSWpGY0lpQmpiMnh2Y2oxY0lpTTRNRGd3T0RCY0lpQm1ZV05sUFZ3aVlYSnBZV3hjSWo3UW45R0EwTFhRdE5HRDBML1JnTkMxMExiUXROQzEwTDNRdU5DMU9pRFFuZEN3MFlIUmd0QyswWS9SaWRDMTBMVWcwWUhRdnRDKzBMSFJpZEMxMEwzUXVOQzFMQ0RRdTlHTzBMSFF2dEM1SU5DKzBMSFF2TkMxMEwwZzBML1JnTkM0MEx2UXZ0QzIwTFhRdmRDOTBZdlF2TkM0SU5DLzBZRFF2dEMxMExyUmd0Q3cwTHpRdUNEUmdkQzAwTFhRdTlDKzBMb2dLTkMwMEw3UXM5QyswTExRdnRHQTBMN1FzaURRdUNEUXROR0FMaWtnMExqUXU5QzRJTkdEMFlIUXU5QyswTExRdU5HUDBMelF1Q0RSZ2RDMDBMWFF1OUMrMExvc0lOQyswWUhSZzlHSjBMWFJnZEdDMExMUXU5R1AwTFhSZ3RHQjBZOGcwTGpSZ2RDNjBMdlJqdEdIMExqUmd0QzEwTHZSak5DOTBMNGcwTFRRdTlHUElOR0cwTFhRdTlDMTBMa2cwTC9SZ05DMTBMVFFzdEN3MFlEUXVOR0MwTFhRdTlHTTBMM1F2dEN6MEw0ZzBMN1FzZEdCMFlQUXR0QzAwTFhRdmRDNDBZOGcwTC9SZ05DKzBMWFF1dEdDMEw3UXNpRFJnZEMwMExYUXU5QyswTG9nMExnZzBMM1F0U0RSajlDeTBMdlJqOUMxMFlMUmdkR1BYSEpjYmlEUXZ0R0UwTFhSZ05HQzBMN1F1U3dnMEwvUmdOQzQwTFBRdTlDdzBZalF0ZEM5MExqUXRkQzhJTkMwMExYUXU5Q3cwWUxSakNEUXZ0R0UwTFhSZ05HQzBZc3NJTkMvMFlEUXVOQzkwWS9SZ3RDNDBMWFF2Q0RRdnRHRTBMWFJnTkdDMFlzc0lOQzMwTERRdXRDNzBZN1JoOUMxMEwzUXVOQzEwTHdnMEwvUmdOQzEwTFRRc3RDdzBZRFF1TkdDMExYUXU5R00wTDNRdnRDejBMNGcwTFRRdnRDejBMN1FzdEMrMFlEUXNDRFF1TkM3MExnZzBMVFF2dEN6MEw3UXN0QyswWURRc0NEUXNpRFF2OUMrMFlEUmo5QzAwTHJRdFNEUXZ5NHlJTkdCMFlJdUlEUXpOQ0RRazlDYUlOQ2cwS1FnMExnZzBMdlJqdEN4MEw3UXM5QytJTkMwMFlEUmc5Q3owTDdRczlDK0lOQy8wWURRdU5DODBMWFF2ZEM0MEx6UXZ0Q3owTDRnMExmUXNOQzYwTDdRdmRDKzBMVFFzTkdDMExYUXU5R00wWUhSZ3RDeTBMQXVJTkNiMExqUmlOR01JTkMvMEw3UmdkQzcwTFVnMExUUXZ0R0IwWUxRdU5DMjBMWFF2ZEM0MFk4ZzBZSFF2dEN6MEx2UXNOR0kwTFhRdmRDNDBZOGcwTC9RdmlEUXN0R0IwTFhRdkNEUmdkR0QwWW5RdGRHQjBZTFFzdEMxMEwzUXZkR0wwTHdnMFlQUmdkQzcwTDdRc3RDNDBZL1F2Q3dnMFk3UmdOQzQwTFRRdU5HSDBMWFJnZEM2MExoY2NseHVJTkMrMExIUmo5QzMwWXZRc3RDdzBZN1JpZEN3MFk4ZzBZSFF0TkMxMEx2UXV0Q3dJTkN4MFlQUXROQzEwWUlnMExmUXNOQzYwTHZSanRHSDBMWFF2ZEN3SU5DLzBZUFJndEMxMEx3ZzBZSFF2dEdCMFlMUXNOQ3kwTHZRdGRDOTBMalJqeURRdnRDMDBMM1F2dEN6MEw0ZzBMVFF2dEM2MFlQUXZOQzEwTDNSZ3RDd0xDRFF0TkMrMEx2UXR0QzkwWXZRdkNEUXZ0Q3gwWURRc05DMzBMN1F2Q0RRdjlDKzBMVFF2OUM0MFlIUXNOQzkwTDNRdnRDejBMNGcwTExSZ2RDMTBMelF1Q0RSZ2RHQzBMN1JnTkMrMEwzUXNOQzgwTGd1SU5DYzBZc2cwWUhRdnRHRjBZRFFzTkM5MFkvUXRkQzhJTkMzMExBZzBZSFF2dEN4MEw3UXVTRFF2OUdBMExEUXN0QytJTkMvMEw0ZzBZSFFzdEMrMExYUXZOR0RJTkMvMEw3UXU5QzkwTDdRdk5HRElOR0QwWUhRdk5DKzBZTFJnTkMxMEwzUXVOR09JTkN5SU5DKzBMVFF2ZEMrMFlIUmd0QyswWURRdnRDOTBMM1F0ZEM4SU5DLzBMN1JnTkdQMExUUXV0QzFJTkMvMFlEUXRkQzYwWURRc05HQzBMalJndEdNSU5DLzBMWFJnTkMxMExQUXZ0Q3kwTDdSZ05HTElOQy8wTDRnMEx2Ump0Q3gwTDdRdVNEUXY5R0EwTGpSaDlDNDBMM1F0U3dnMExIUXRkQzNJTkM2MExEUXV0QyswTGt0MEx2UXVOQ3gwTDRnMEw3UXNkR1AwTGZRc05DOTBMM1F2dEdCMFlMUXVGeHlYRzRnMFlFZzBMM1FzTkdJMExYUXVTRFJnZEdDMEw3UmdOQyswTDNSaXlEUXVOQzkwWVRRdnRHQTBMelF1TkdBMEw3UXN0Q3cwWUxSakNEUXROR0EwWVBRczlHRDBZNGcwWUhSZ3RDKzBZRFF2dEM5MFlNZzBMNGcwWUxRc05DNjBMalJoU0RRdjlHQTBMalJoOUM0MEwzUXNOR0ZMaURRbU5DOTBZVFF2dEdBMEx6UXNOR0cwTGpSanl3ZzBZSFF2dEMwMExYUmdOQzIwTERSaWRDdzBZL1JnZEdQSU5DeUlOR04wWUxRdnRDOElOR04wTHZRdGRDNjBZTFJnTkMrMEwzUXZkQyswTHdnMFlIUXZ0QyswTEhSaWRDMTBMM1F1TkM0TENEUmo5Q3kwTHZSajlDMTBZTFJnZEdQSU5DNjBMN1F2ZEdFMExqUXROQzEwTDNSaHRDNDBMRFF1OUdNMEwzUXZ0QzVJTkM0SU5DOTBMVWcwTC9RdnRDMDBMdlF0ZEMyMExqUmdpRFJnTkN3MExmUXM5QzcwTERSaU5DMTBMM1F1TkdPSU5HQzBZRFF0ZEdDMFl6UXVOQzhJTkM3MExqUmh0Q3cwTHd1UEdKeVBseHlYRzdRa2lEUXZkQ3cwWWpRdGRDNUlOQyswWURRczlDdzBMM1F1TkMzMExEUmh0QzQwTGdnMExUUXRkQzUwWUhSZ3RDeTBZUFF0ZEdDSU5HQjBMdlJnOUMyMExIUXNDd2cwTHJRdnRHQzBMN1JnTkN3MFk4ZzBML1F2dEM4MEw3UXM5Q3cwTFhSZ2lEUXN0R0wwWS9Rc3RDNzBZL1JndEdNSU5DNElOQy8wWURRdGRDMDBMN1JndEN5MFlEUXNOR0owTERSZ3RHTUlOR0IwTHZSZzlHSDBMRFF1Q0RRdmRDMTBMVFF2dEN4MFlEUXZ0R0IwTDdRc3RDMTBZSFJndEM5MFl2UmhTRFF0TkMxMExuUmdkR0MwTExRdU5DNUlOQzYwTDdRdmRHQzBZRFFzTkN6MExYUXZkR0MwTDdRc2lEUXVDRFJnZEMrMFlMUmdOR0QwTFRRdmRDNDBMclF2dEN5SU5DYTBMN1F2TkMvMExEUXZkQzQwTGdnSmlNNE1qRXhPeURSZ2RDNzBZUFF0dEN4MExBZzBMVFF2dEN5MExYUmdOQzQwWThnSm14aGNYVnZPOUNoMExqUXM5QzlRVXd0VUhKdkpuSmhjWFZ2T3k0OFluSStYSEpjYnRDVjBZSFF1OUM0SU5DeUlOR0YwTDdRdE5DMUlOQ3kwTGZRc05DNDBMelF2dEMwMExYUXVkR0IwWUxRc3RDNDBZOGcwWUVtYm1KemNEc2cwTDNRc05HSTBMWFF1U0RRdXRDKzBMelF2OUN3MEwzUXVOQzEwTGtnMEpMUml5RFJnZEdDMEw3UXU5QzYwTDNSZzlDNzBMalJnZEdNSU5HQklOR0UwTERRdXRHQzBMRFF2TkM0SU5DOTBMWFF0TkMrMExIUmdOQyswWUhRdnRDeTBMWFJnZEdDMEwzUmk5R0ZJTkMwMExYUXVkR0IwWUxRc3RDNDBMa3NJTkM5MExEUmdOR0QwWWpRdGRDOTBMalJqOUM4MExnc0lOR0YwTGpSaWRDMTBMM1F1TkdQMEx6UXVDRFF1TkM3MExnZzBZSFF2dEdDMFlEUmc5QzAwTDNRdU5DNjBMRFF2TkM0TENEUXNpRFJoOUMxMFlIUmd0QzkwTDdSZ2RHQzBMZ2cwTHJRdnRHQzBMN1JnTkdMMFlVZzBKTFJpeURSZ2RDKzBMelF2ZEMxMExMUXNOQzEwWUxRdGRHQjBZd3NJTkdCMEw3UXZ0Q3gwWW5RdU5HQzBMVWcwTDdRc1NEUmpkR0MwTDdRdkNEUXY5QytJTkMrMExUUXZkQyswTHpSZ3lEUXVOQzNJTkM2MExEUXZkQ3cwTHZRdnRDeUlOR0IwTExSajlDMzBMZ2cwS0hRdTlHRDBMYlFzZEdMSU5DMDBMN1FzdEMxMFlEUXVOR1BJQ1pzWVhGMWJ6dlFvZEM0MExQUXZVRk1MVkJ5YnlaeVlYRjFienM2SU5DLzBMNGcwWUxRdGRDNzBMWFJoTkMrMEwzUmcxeHlYRzQ4ZFQ0NElEZ3dNQ0F5TlRBZ016SWdOamc4WEM5MVBpRFF1Q0RRdjlDK0lOR04wTHN1SU5DLzBMN1JoOUdDMExVZ2MybG5ibUZzUUhCeWIzWmxiblIxY3kxd2NtOHVjblVnTGp4aWNqNWNjbHh1UEdKeVBseHlYRzVFYVhOamJHRnBiV1Z5T2lCVWFHbHpJRzFsYzNOaFoyVWdZVzVrSUdGdWVTQmxlR05vWVc1blpTQnZaaUJsYm1Oc2IzTmxaQ0JrY21GbWRDQmpiMjUwY21GamRITWdiM0lnWTI5dWRISmhZM1IxWVd3Z2RHVnliWE1nWVhKbElHWnZjaUJrYVhOamRYTnphVzl1SUhCMWNuQnZjMlZ6SUc5dWJIa2dZVzVrSUdSdklHNXZkQ0JqYjI1emRHbDBkWFJsSUdGdUlHOW1abVZ5TENCaElITnZiR2xqYVhSaGRHbHZiaUJ2WmlCaGJpQnZabVpsY2l3Z1lXNGdZV05qWlhCMFlXNWpaU0J2WmlCaGJpQnZabVpsY2l3Z1lTQndjbVZzYVcxcGJtRnllU0JqYjI1MGNtRmpkQ0J2Y2lCamIyNTBjbUZqZENCMWJtUmxjaUJ6WldNdVhISmNiaUF5SUc5bUlHRnlkQzRnTkRNMElHOW1JSFJvWlNCU1JpQkRhWFpwYkNCRGIyUmxJRzl5SUdGdWVTQnZkR2hsY2lCaGNIQnNhV05oWW14bElHeGhkeTRnVDI1c2VTQmhablJsY2lCaGJpQmhaM0psWlcxbGJuUWdhWE1nY21WaFkyaGxaQ0J2YmlCaGJHd2daWE56Wlc1MGFXRnNJSFJsY20xeklHRWdiR1ZuWVd4c2VTQmlhVzVrYVc1bklHTnZiblJ5WVdOMElIZHBiR3dnWW1VZ2JXRmtaU0JwYmlCMGFHVWdabTl5YlNCdlppQmhJSE5wYm1kc1pTQjNjbWwwZEdWdUlHbHVjM1J5ZFcxbGJuUWdaSFZzZVNCemFXZHVaV1FnWW5rZ1lXeHNJSEJoY25ScFpYTXVJRmRsSUhKbGMyVnlkbVVnZEdobElISnBaMmgwSUhSdlhISmNiaUJrYVhOamIyNTBhVzUxWlNCaGJua2dibVZuYjNScFlYUnBiMjV6SUdsdUlHOTFjaUJtZFd4c0lHUnBjMk55WlhScGIyNGdabTl5SUdGdWVTQnlaV0Z6YjI0Z1lXNWtJSGRwZEdodmRYUWdZVzU1SUc5aWJHbG5ZWFJwYjI0Z2RHOGdhVzVtYjNKdElIbHZkU0J2WmlCemRXTm9JSEpsWVhOdmJpNGdWR2hsSUdsdVptOXliV0YwYVc5dUlHbHVJSFJvYVhNZ2JXVnpjMkZuWlNCcGN5QmpiMjVtYVdSbGJuUnBZV3dnWVc1a0lHMWhlU0JpWlNCc1pXZGhiR3g1SUhCeWFYWnBiR1ZuWldRdVBHSnlQbHh5WEc1SmJpQnZkWElnUTI5dGNHRnVlU3dnYjNWeUlGTkpSMDVCVEMxUWNtOGdhRzkwYkdsdVpTQndjbTkyYVdSbGN5QmxiWEJzYjNsbFpYTXNJR0Z6SUhkbGJHd2dZWE1nWW5WemFXNWxjM01nY0dGeWRHNWxjbk1nWVc1a0lHOTBhR1Z5Y3lCM2FYUm9JR0VnYldWaGJuTWdkRzhnY21Wd2IzSjBJSEJ2ZEdWdWRHbGhiQ0IyYVc5c1lYUnBiMjV6SUc5bUlIUm9aU0JEYjIxd1lXNTVKaU00TWpFM08zTWdRMjlrWlNCdlppQkZkR2hwWTNNc0lHOTFjaUJ3YjJ4cFkybGxjeUJ2Y2lCaGNIQnNhV05oWW14bElHeGhkeTQ4WW5JK1hISmNia2xtSUdsdUlIUm9aU0JqYjNWeWMyVWdiMllnZVc5MWNpQnBiblJsY21GamRHbHZiaUIzYVhSb0lHOTFjaUJEYjIxd1lXNTVJSGx2ZFNCb1lYWmxJR052YldVZ1lXTnliM056SUdaaFkzUnpJRzltSUhWdVptRnBjaUJ3Y21GamRHbGpaWE1zSUhacGIyeGhkR2x2Ym5Nc0lIUm9aV1owSUc5eUlHVnRjR3h2ZVdWbGN5QjNhRzl6WlNCb2IyNWxjM1I1SUhsdmRTQmtiM1ZpZEN3Z2NHeGxZWE5sSUdsdVptOXliU0IxY3lCMmFXRWdiMjVsSUc5bUlIUm9aU0JqYjIxdGRXNXBZMkYwYVc5dUlHTm9ZVzV1Wld4eklHOW1JSFJvWlNCVFNVZE9RVXd0VUhKdklHaHZkR3hwYm1VNklHSjVJSEJvYjI1bFhISmNiangxUGpnZ09EQXdJREkxTUNBek1pQTJPRHhjTDNVK0lHOXlJR0o1SUdWdFlXbHNJSE5wWjI1aGJFQndjbTkyWlc1MGRYTXRjSEp2TG5KMUxpQThYQzltYjI1MFBseHlYRzQ4WEM5aWIyUjVQbHh5WEc0OFhDOW9kRzFzUGx4eVhHNGlmUT09")
    # order_rec.consumer_test(content="""Б НЛГ 30Б1 шт""")
    # TO DO: HARD
    # order_rec.consumer_test(hash='ZX...')