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
        print('Очищенное сообщение -', clear_email)
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
            # через partial прокидываем в наш обработчик сам канал
            await queue.consume(partial(self.consumer, channel=channel), timeout=60000)
            print('Слушаем очередь', flush=True)


            queue2 = await channel.declare_queue(conf.second_queue, timeout=10000)
            await queue2.bind(exchange=conf.exchange, routing_key=conf.routing_key, timeout=10000)
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
    # order_rec.consumer_test(content="""С–8 5021 6м 3шт""")
    # order_rec.consumer_test(content="""Б профильная 75x750x0.9 L 6000 9 шт
    # А 45 68 34шт
    # У 45 68 34шт""")
    # order_rec.consumer_test(hash='ZXlKaWRXTnJaWFJPWVcxbElqb2lZM0p0TFdWdFlXbHNJaXdpYjJKcVpXTjBUbUZ0WlNJNkltMXpaMTltTUdSa1pqTm1ZMlkyWWpJNU5EazNOemcwWldZNU16QTNZVGs1Wm1ZeU9TSXNJbVpwYkdWRGIyNTBaVzUwSWpvaVhHNDhTRlJOVEQ0OFFrOUVXVDQ4Y0NCemRIbHNaVDFjSW0xaGNtZHBiaTEwYjNBNklEQndlRHRjSWlCa2FYSTlYQ0pzZEhKY0lqNDhYQzl3UGx4dVBHUnBkaUJwWkQxY0ltMWhhV3d0WVhCd0xXRjFkRzh0WkdWbVlYVnNkQzF6YVdkdVlYUjFjbVZjSWo1Y2JpQThjQ0JrYVhJOVhDSnNkSEpjSWo0dExUeGljajVjYmlBZ0lOQ2UwWUxRdjlHQTBMRFFzdEM3MExYUXZkQytJTkM0MExjZ1BHRWdhSEpsWmoxY0ltaDBkSEJ6T2k4dmJXRnBiQzV5ZFM5Y0lqNU5ZV2xzUEZ3dllUNGcwTFRRdTlHUElFRnVaSEp2YVdROFhDOXdQbHh1UEZ3dlpHbDJQaTB0TFMwdExTMHRJTkNmMExYUmdOQzEwWUhRdTlDdzBMM1F2ZEMrMExVZzBML1F1TkdCMFl6UXZOQytJQzB0TFMwdExTMHRQR0p5THo3UW50R0NPaURRcU5DdzBZRFF1TkMvMEw3UXNpRFFsTkN3MEx6UXVOR0FJTkNZMFlEUXRkQzYwTDdRc3RDNDBZY2dQR0VnYUhKbFpqMWNJbTFoYVd4MGJ6cHphR0Z5YVhCdmRtUnBRSE53YXk1eWRWd2lQbk5vWVhKcGNHOTJaR2xBYzNCckxuSjFQRnd2WVQ0OFluSXZQdENhMEw3UXZOR0RPaUJFWVcxcGNpQlRhR0Z5YVhCdmRpQThZU0JvY21WbVBWd2liV0ZwYkhSdk9tUmhiV2x5TG5Ob1lYSnBjRzkyTWpOQWJXRnBiQzV5ZFZ3aVBtUmhiV2x5TG5Ob1lYSnBjRzkyTWpOQWJXRnBiQzV5ZFR4Y0wyRStQR0p5THo3UWxOQ3cwWUxRc0RvZzBML1JqOUdDMEwzUXVOR0cwTEFzSURBMElOQyswTHJSZ3RHUDBMSFJnTkdQSURJd01qVFFzeTRzSURFeU9qVXlJQ3N3TlRvd01EeGljaTgrMEtMUXRkQzgwTEE2SU5DajBMUFF2dEM3MEw3UXVpQXlQR0p5UGp4aWNqNDhZbXh2WTJ0eGRXOTBaU0JwWkQxY0ltMWhhV3d0WVhCd0xXRjFkRzh0Y1hWdmRHVmNJaUJqYVhSbFBWd2lNVGN5T0RBeU9ETTNOekUyTURBek9UWTNNamhjSWlCemRIbHNaVDFjSW1KdmNtUmxjaTFzWldaME9qRndlQ0J6YjJ4cFpDQWpNREEzTjBaR095QnRZWEpuYVc0Nk1IQjRJREJ3ZUNBd2NIZ2dNVEJ3ZURzZ2NHRmtaR2x1Wnpvd2NIZ2dNSEI0SURCd2VDQXhNSEI0TzF3aVBqeGthWFlnWTJ4aGMzTTlYQ0pxY3kxb1pXeHdaWElnYW5NdGNtVmhaRzF6WnkxdGMyZGNJajVjYmlBZ0lDQmNiaUFnSUNBOGMzUjViR1VnZEhsd1pUMWNJblJsZUhRdlkzTnpYQ0krUEZ3dmMzUjViR1UrWEc0Z0lDQWdQR0poYzJVZ2RHRnlaMlYwUFZ3aVgzTmxiR1pjSWlCb2NtVm1QVndpYUhSMGNITTZMeTlsTG0xaGFXd3VjblV2WENJZ0x6NWNiaUFnSUNBOFpHbDJJR2xrUFZ3aWMzUjViR1ZmTVRjeU9EQXlPRE0zTnpFMk1EQXpPVFkzTWpoY0lqNWNiaUFnSUNBZ0lDQWdQR1JwZGlCcFpEMWNJbk4wZVd4bFh6RTNNamd3TWpnek56Y3hOakF3TXprMk56STRYMEpQUkZsY0lqNDhaR2wySUdOc1lYTnpQVndpWTJ4Zk1EY3lNemt4WENJK1hHNWNibHh1WEc1Y2JseHVYRzQ4WkdsMklHTnNZWE56UFZ3aVYyOXlaRk5sWTNScGIyNHhYMjF5WDJOemMxOWhkSFJ5WENJK1hHNDhjQ0JqYkdGemN6MWNJazF6YjA1dmNtMWhiRjl0Y2w5amMzTmZZWFIwY2x3aVB0Q2owTFBRdnRDNzBMN1F1aUF4TURCNE1UQXdQRnd2Y0Q1Y2JqeHdJR05zWVhOelBWd2lUWE52VG05eWJXRnNYMjF5WDJOemMxOWhkSFJ5WENJKzBLUFFzOUMrMEx2UXZ0QzZJREV3TUhnMk16eGNMM0ErWEc0OGNDQmpiR0Z6Y3oxY0lrMXpiMDV2Y20xaGJGOXRjbDlqYzNOZllYUjBjbHdpUHRDajBMUFF2dEM3MEw3UXVpQXhNVEI0TVRFd1BGd3ZjRDVjYmp4d0lHTnNZWE56UFZ3aVRYTnZUbTl5YldGc1gyMXlYMk56YzE5aGRIUnlYQ0krMEtQUXM5QyswTHZRdnRDNklERXlOWGd4TWpVOFhDOXdQbHh1UEhBZ1kyeGhjM005WENKTmMyOU9iM0p0WVd4ZmJYSmZZM056WDJGMGRISmNJajdRbzlDejBMN1F1OUMrMExvZ01UUXdlREUwTUR4Y0wzQStYRzQ4Y0NCamJHRnpjejFjSWsxemIwNXZjbTFoYkY5dGNsOWpjM05mWVhSMGNsd2lQdENqMExQUXZ0QzcwTDdRdWlBeE5qQjRNVEF3UEZ3dmNENWNianh3SUdOc1lYTnpQVndpVFhOdlRtOXliV0ZzWDIxeVgyTnpjMTloZEhSeVhDSSswS1BRczlDKzBMdlF2dEM2SURFMk1IZ3hOakE4WEM5d1BseHVQSEFnWTJ4aGMzTTlYQ0pOYzI5T2IzSnRZV3hmYlhKZlkzTnpYMkYwZEhKY0lqN1FvOUN6MEw3UXU5QyswTG9nTVRnd2VERTRNRHhjTDNBK1hHNDhjQ0JqYkdGemN6MWNJazF6YjA1dmNtMWhiRjl0Y2w5amMzTmZZWFIwY2x3aVB0Q2owTFBRdnRDNzBMN1F1aUF5TURCNE1USTFQRnd2Y0Q1Y2JqeHdJR05zWVhOelBWd2lUWE52VG05eWJXRnNYMjF5WDJOemMxOWhkSFJ5WENJKzBLUFFzOUMrMEx2UXZ0QzZJREkxZURJMVBGd3ZjRDVjYmp4d0lHTnNZWE56UFZ3aVRYTnZUbTl5YldGc1gyMXlYMk56YzE5aGRIUnlYQ0krMEtQUXM5QyswTHZRdnRDNklETXllRE15UEZ3dmNENWNianh3SUdOc1lYTnpQVndpVFhOdlRtOXliV0ZzWDIxeVgyTnpjMTloZEhSeVhDSSswS1BRczlDKzBMdlF2dEM2SURNMWVETTFQRnd2Y0Q1Y2JqeHdJR05zWVhOelBWd2lUWE52VG05eWJXRnNYMjF5WDJOemMxOWhkSFJ5WENJKzBLUFFzOUMrMEx2UXZ0QzZJRFF3ZURRd1BGd3ZjRDVjYmp4d0lHTnNZWE56UFZ3aVRYTnZUbTl5YldGc1gyMXlYMk56YzE5aGRIUnlYQ0krMEtQUXM5QyswTHZRdnRDNklEUTFlRFExUEZ3dmNENWNianh3SUdOc1lYTnpQVndpVFhOdlRtOXliV0ZzWDIxeVgyTnpjMTloZEhSeVhDSSswS1BRczlDKzBMdlF2dEM2SURVd2VEVXdQRnd2Y0Q1Y2JqeHdJR05zWVhOelBWd2lUWE52VG05eWJXRnNYMjF5WDJOemMxOWhkSFJ5WENJKzBLUFFzOUMrMEx2UXZ0QzZJRFl6ZURRd1BGd3ZjRDVjYmp4d0lHTnNZWE56UFZ3aVRYTnZUbTl5YldGc1gyMXlYMk56YzE5aGRIUnlYQ0krMEtQUXM5QyswTHZRdnRDNklEY3dlRGN3UEZ3dmNENWNianh3SUdOc1lYTnpQVndpVFhOdlRtOXliV0ZzWDIxeVgyTnpjMTloZEhSeVhDSSswS1BRczlDKzBMdlF2dEM2SURjMWVEVXdQRnd2Y0Q1Y2JqeHdJR05zWVhOelBWd2lUWE52VG05eWJXRnNYMjF5WDJOemMxOWhkSFJ5WENJKzBLUFFzOUMrMEx2UXZ0QzZJRGd3ZURnd1BGd3ZjRDVjYmp4d0lHTnNZWE56UFZ3aVRYTnZUbTl5YldGc1gyMXlYMk56YzE5aGRIUnlYQ0krMEtQUXM5QyswTHZRdnRDNklEa3dlRGt3UEZ3dmNENWNianhjTDJScGRqNWNianh3SUhOMGVXeGxQVndpWTI5c2IzSTZJek5oTnpWak5EdG1iMjUwT2psd2RDQkJjbWxoYkZ3aVB0Q2owTExRc05DMjBMRFF0ZEM4MFl2UXRTRFF1dEMrMEx2UXU5QzEwTFBRdUNEUXVDRFF2OUN3MFlEUmd0QzkwTFhSZ05HTExEeGNMM0ErWEc0OGNDQnpkSGxzWlQxY0ltTnZiRzl5T2lNellUYzFZelE3Wm05dWREbzVjSFFnUVhKcFlXeGNJajdRbmRDdzBZalFzQ0RRbXRDKzBMelF2OUN3MEwzUXVOR1BJTkMvMFlEUXVOQzAwTFhSZ05DMjBMalFzdEN3MExYUmd0R0IwWThnMFkzUmd0QzQwWWZRdGRHQjBMclF1TkdGSU5DLzBZRFF1TkM5MFliUXVOQy8wTDdRc2lEUXN0QzEwTFRRdGRDOTBMalJqeURRc2RDNDBMZlF2ZEMxMFlIUXNDRFF1Q0RRdE5DMTBMdlFzTkMxMFlJZzBMTFJnZEMxSU5DMDBMdlJqeURSZ3RDKzBMUFF2aXdnMFlmUmd0QyswTEhSaXlEUXN0QzMwTERRdU5DODBMN1F2dEdDMEwzUXZ0R0kwTFhRdmRDNDBZOGcwWUVnMEwzUXNOR0kwTGpRdk5DNElOQy8wTERSZ05HQzBMM1F0ZEdBMExEUXZOQzRJTkdCMFlMUmdOQyswTGpRdTlDNDBZSFJqQ0RRdmRDd0lOQy8wWURRdU5DOTBZYlF1TkMvMExEUmhTRFF2dEdDMExyUmdOR0wwWUxRdnRHQjBZTFF1Q0RRdUNEUXY5R0EwTDdRdDlHQTBMRFJoOUM5MEw3UmdkR0MwTGd1SU5DZjBMN1JqZEdDMEw3UXZOR0RJTkMvMFlEUXZ0R0IwTGpRdkNEUWt0Q3cwWUVnMFlIUXZ0QyswTEhSaWRDdzBZTFJqQ0RRdmRDdzBMd2cwTDdRc2RDK0lOQ3kwWUhRdGRHRlhHNGcwTDNRdGRDejBMRFJndEM0MExMUXZkR0wwWVVnMFlUUXNOQzYwWUxRc05HRklOQ3kwTDRnMExMUXQ5Q3cwTGpRdk5DKzBMN1JndEM5MEw3UmlOQzEwTDNRdU5HUDBZVWcwWUVnMEwzUXNOR0kwTFhRdVNEUXV0QyswTHpRdjlDdzBMM1F1TkMxMExrZzBML1F2aURRc05DMDBZRFF0ZEdCMFlNZ1BHRWdjM1I1YkdVOVhDSmpiMnh2Y2pvak0yRTNOV00wTzF3aUlHaHlaV1k5WENJdkwyVXViV0ZwYkM1eWRTOWpiMjF3YjNObEx6OXRZV2xzZEc4OWJXRnBiSFJ2SlROaFpHOTJaWEpwWlVCelkyMHVjblZjSWlCMFlYSm5aWFE5WENKZllteGhibXRjSWlBZ2NtVnNQVndpSUc1dmIzQmxibVZ5SUc1dmNtVm1aWEp5WlhKY0lpQStYRzVrYjNabGNtbGxRSE5qYlM1eWRUeGNMMkUrTGlEUWt0R0IwWThnMExqUXZkR0UwTDdSZ05DODBMRFJodEM0MFk4ZzBML1F2dEdCMFlMUmc5Qy8wTERRdGRHQ0lOQ3lJTkM5MExYUXQ5Q3cwTExRdU5HQjBMalF2TkdEMFk0ZzBZSFF1OUdEMExiUXNkR0RJTkN5MEwzUmc5R0MwWURRdGRDOTBMM1F0ZEN6MEw0ZzBMRFJnOUMwMExqUmd0Q3dManhjTDNBK1hHNDhjQ0J6ZEhsc1pUMWNJbU52Ykc5eU9pTXpZVGMxWXpRN1ptOXVkRG81Y0hRZ1FYSnBZV3hjSWo3UW45R0EwTFhSZ3RDMTBMM1F0OUM0MExnZzBML1F2aURRdXRDdzBZZlF0ZEdCMFlMUXN0R0RJTkMrMExIUmdkQzcwWVBRdHRDNDBMTFFzTkM5MExqUmp5RFF1TkM3MExnZzBZTFF2dEN5MExEUmdOQ3dJTkMvMFlEUXVOQzkwTGpRdk5DdzBZN1JndEdCMFk4ZzBMM1FzQ0RSZ3RDMTBMdlF0ZEdFMEw3UXZTRFFzOUMrMFlEUmo5R0gwTFhRdVNEUXU5QzQwTDNRdU5DNFhHNDhkVDQ4YzNCaGJpQmpiR0Z6Y3oxY0ltcHpMWEJvYjI1bExXNTFiV0psY2x3aVBqZ3RPREF3TFRjd01EQXRNVEl6UEZ3dmMzQmhiajQ4WEM5MVBpNGcwSmZRc3RDKzBMM1F1dEM0SU5DLzBMNGcwS0RRdnRHQjBZSFF1TkM0SU5DeDBMWFJnZEMvMEx2UXNOR0MwTDNRdmp4Y0wzQStYRzVjYmx4dVBGd3ZaR2wyUGp4Y0wyUnBkajVjYmlBZ0lDQWdJQ0FnWEc0Z0lDQWdQRnd2WkdsMlBseHVQRnd2WkdsMlBqeGNMMkpzYjJOcmNYVnZkR1UrUEZ3dlFrOUVXVDQ4WEM5SVZFMU1QbHh1SW4wPQ==')
    # order_rec.save_truth_test(content="{'req_number': '187ca897-4b2c-4b07-aa75-4f0d9dff8fc5', 'mail_code': '0057653611', 'user': 'SHARIPOVDI', 'positions': [{'position_id': '4', 'true_material': '000000000000083739', 'true_ei': 'ШТ', 'true_value': '15.000', 'spec_mat': ''}]}".replace("'", '"'))