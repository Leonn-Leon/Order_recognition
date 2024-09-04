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
                        true_mat = self.find_mats.all_materials[self.find_mats.all_materials['Материал'].\
                            str.contains(str(int(pos['true_material'])))]['Полное наименование материала'].values[0]
                        true_first = self.find_mats.all_materials[self.find_mats.all_materials['Материал']
                                                     == (str(int(pos['true_material'])))]['Название иерархии-1'].values[0]
                        true_zero = self.find_mats.all_materials[self.find_mats.all_materials['Материал']
                                                                  == (str(int(pos['true_material'])))][
                            'Название иерархии-0'].values[0]
                        # true_mat = str(int(pos['true_material']))

                    except Exception as exc:
                        self.write_logs('Не нашёл такого материала '+str(pos['true_material']) + ' ' + str(exc), event=0)
                        continue
                    try:
                        print(self.find_mats.all_materials[self.find_mats.all_materials['Материал']
                                                           == (str(int(pos['true_material'])))])
                        print('Отправляем обучать !', flush=True)
                        self.write_logs('Отправляем обучать ! ' + request_text + '|' + true_first)
                        self.find_mats.models.fit(request_text, true_first, true_zero)
                    except Exception as exc:
                        self.write_logs('Не смог обучить модельки для '+str(pos['true_material']) + ' ' + str(exc), event=0)
                        continue

                    if 'spec_mat' in pos.keys():
                        this_client_only = True if pos['spec_mat'] == 'X' else False
                    else:
                        this_client_only = False
                    res = str({'num_mat':str(int(pos['true_material'])),
                                'name_mat':true_mat,
                                'true_ei':pos['true_ei'],
                                'true_value':pos['true_value'],
                                'spec_mat':str(this_client_only)})
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
    # order_rec.start()
    # order_rec.consumer_test(content="""С–8 5021 6м 3шт""")
    # order_rec.consumer_test(content="""22. Труба профильная 75x750x0.9 L 6000 9 шт""")
    order_rec.consumer_test(hash='ZXlKaWRXTnJaWFJPWVcxbElqb2lZM0p0TFdWdFlXbHNJaXdpYjJKcVpXTjBUbUZ0WlNJNkltMXpaMTh6TUdRNU0yWXpaVFJpWlRBNVlUZzFaVFk0WldZM01XUTFaR0kyTnpjd1lTSXNJbVpwYkdWRGIyNTBaVzUwSWpvaVhHNDhTRlJOVEQ0OFFrOUVXVDQ4Y0NCemRIbHNaVDFjSW0xaGNtZHBiaTEwYjNBNklEQndlRHRjSWlCa2FYSTlYQ0pzZEhKY0lqNDhYQzl3UGx4dVBHUnBkaUJwWkQxY0ltMWhhV3d0WVhCd0xXRjFkRzh0WkdWbVlYVnNkQzF6YVdkdVlYUjFjbVZjSWo1Y2JpQThjQ0JrYVhJOVhDSnNkSEpjSWo0dExUeGljajVjYmlBZ0lOQ2UwWUxRdjlHQTBMRFFzdEM3MExYUXZkQytJTkM0MExjZ1BHRWdhSEpsWmoxY0ltaDBkSEJ6T2k4dmJXRnBiQzV5ZFM5Y0lqNU5ZV2xzUEZ3dllUNGcwTFRRdTlHUElFRnVaSEp2YVdROFhDOXdQbHh1UEZ3dlpHbDJQaTB0TFMwdExTMHRJTkNmMExYUmdOQzEwWUhRdTlDdzBMM1F2ZEMrMExVZzBML1F1TkdCMFl6UXZOQytJQzB0TFMwdExTMHRQR0p5THo3UW50R0NPaURRcU5DdzBZRFF1TkMvMEw3UXNpRFFsTkN3MEx6UXVOR0FJTkNZMFlEUXRkQzYwTDdRc3RDNDBZY2dQR0VnYUhKbFpqMWNJbTFoYVd4MGJ6cHphR0Z5YVhCdmRtUnBRSE53YXk1eWRWd2lQbk5vWVhKcGNHOTJaR2xBYzNCckxuSjFQRnd2WVQ0OFluSXZQdENhMEw3UXZOR0RPaUJFWVcxcGNpQlRhR0Z5YVhCdmRpQThZU0JvY21WbVBWd2liV0ZwYkhSdk9tUmhiV2x5TG5Ob1lYSnBjRzkyTWpOQWJXRnBiQzV5ZFZ3aVBtUmhiV2x5TG5Ob1lYSnBjRzkyTWpOQWJXRnBiQzV5ZFR4Y0wyRStQR0p5THo3UWxOQ3cwWUxRc0RvZzBML1F2dEM5MExYUXROQzEwTHZSak5DOTBMalF1aXdnTURJZzBZSFF0ZEM5MFlMUmo5Q3gwWURSanlBeU1ESTAwTE11TENBeE1qb3dNQ0FyTURVNk1EQThZbkl2UHRDaTBMWFF2TkN3T2lEUW9OQ3cwWUhRdjlDKzBMZlF2ZEN3MExMUXNOQzkwTGpRdFM0ZzBKRFJnTkM4MExEUmd0R0QwWURRc0NBeE1DNGcwTC9RdnRDNzBMM1F2dEMxSU5DOTBMRFF1TkM4MExYUXZkQyswTExRc05DOTBMalF0VHhpY2o0OFluSStQR0pzYjJOcmNYVnZkR1VnYVdROVhDSnRZV2xzTFdGd2NDMWhkWFJ2TFhGMWIzUmxYQ0lnWTJsMFpUMWNJakUzTWpVeU5qQTBNelF4TkRJM01ETTVNVE13WENJZ2MzUjViR1U5WENKaWIzSmtaWEl0YkdWbWREb3hjSGdnYzI5c2FXUWdJekF3TnpkR1Jqc2diV0Z5WjJsdU9qQndlQ0F3Y0hnZ01IQjRJREV3Y0hnN0lIQmhaR1JwYm1jNk1IQjRJREJ3ZUNBd2NIZ2dNVEJ3ZUR0Y0lqNDhaR2wySUdOc1lYTnpQVndpYW5NdGFHVnNjR1Z5SUdwekxYSmxZV1J0YzJjdGJYTm5YQ0krWEc0Z0lDQWdYRzRnSUNBZ1BITjBlV3hsSUhSNWNHVTlYQ0owWlhoMEwyTnpjMXdpUGp4Y0wzTjBlV3hsUGx4dUlDQWdJRHhpWVhObElIUmhjbWRsZEQxY0lsOXpaV3htWENJZ2FISmxaajFjSW1oMGRIQnpPaTh2WlM1dFlXbHNMbkoxTDF3aUlDOCtYRzRnSUNBZ1BHUnBkaUJwWkQxY0luTjBlV3hsWHpFM01qVXlOakEwTXpReE5ESTNNRE01TVRNd1hDSStYRzRnSUNBZ0lDQWdJRHhrYVhZZ2FXUTlYQ0p6ZEhsc1pWOHhOekkxTWpZd05ETTBNVFF5TnpBek9URXpNRjlDVDBSWlhDSStQR1JwZGlCamJHRnpjejFjSW1Oc1h6STRNVGt3TWx3aVBseHVYRzVjYmx4dVhHNWNibHh1UEdScGRpQmpiR0Z6Y3oxY0lsZHZjbVJUWldOMGFXOXVNVjl0Y2w5amMzTmZZWFIwY2x3aVBseHVQSEFnWTJ4aGMzTTlYQ0pOYzI5T2IzSnRZV3hmYlhKZlkzTnpYMkYwZEhKY0lqN1FrQ0F4TUNBeE1TNDMwSndnMEpBeU5EQWdNelF3TWpndE1UWWdYSFV5TURFeklERWcwWWpSZ2p4emNHRnVJSE4wZVd4bFBWd2labTl1ZEMxemFYcGxPakV4TGpCd2REdHRjMjh0Wm1GeVpXRnpkQzFzWVc1bmRXRm5aVHBGVGkxVlUxd2lQanhjTDNOd1lXNCtQRnd2Y0Q1Y2JqeHdJR05zWVhOelBWd2lUWE52VG05eWJXRnNYMjF5WDJOemMxOWhkSFJ5WENJKzBKQWdNVEFnTVRFdU45Q2NJTkNRTkRBd0lETTBNREk0TFRFMklGeDFNakF4TXlBeUlOR0kwWUlnUEZ3dmNENWNianh3SUdOc1lYTnpQVndpVFhOdlRtOXliV0ZzWDIxeVgyTnpjMTloZEhSeVhDSSswSkFnTVRBZ01URXVOOUNjSU5DUU5UQXdJTkNoSURNME1ESTRMVEUySUZ4MU1qQXhNeUF6SU5HSTBZSThYQzl3UGx4dVBIQWdZMnhoYzNNOVhDSk5jMjlPYjNKdFlXeGZiWEpmWTNOelgyRjBkSEpjSWo3UWtDQXhNQ0F4TVM0MzBKd2cwSkExTURBZzBLSFFsU0F6TkRBeU9DMHhOaUJjZFRJd01UTWdNVEFnMFlqUmdqeGNMM0ErWEc0OGNDQmpiR0Z6Y3oxY0lrMXpiMDV2Y20xaGJGOXRjbDlqYzNOZllYUjBjbHdpUHRDUUlERXdJREV5MEp3ZzBKQXlOREFnTXpRd01qZ3RNVFlnWEhVeU1ERXpJREl3SU5HSTBZSThYQzl3UGx4dVBIQWdZMnhoYzNNOVhDSk5jMjlPYjNKdFlXeGZiWEpmWTNOelgyRjBkSEpjSWo3UWtDQXhNQ0F4TXRDY0lOQ1FOREF3SURNME1ESTRMVEUySUZ4MU1qQXhNeUF6TUNEUmlOR0NQRnd2Y0Q1Y2JqeHdJR05zWVhOelBWd2lUWE52VG05eWJXRnNYMjF5WDJOemMxOWhkSFJ5WENJKzBKQWdNVEFnTVRMUW5DRFFrRFV3TUNEUW9TQXpOREF5T0MweE5pQmNkVEl3TVRNZ01UQXdJTkdJMFlJOFhDOXdQbHh1UEhBZ1kyeGhjM005WENKTmMyOU9iM0p0WVd4ZmJYSmZZM056WDJGMGRISmNJajdRa0NBeE1DQTFMamcxMEp3ZzBKQXlOREFnTXpRd01qZ3RNVFlnWEhVeU1ERXpJREl3TUNEUmlOR0NQRnd2Y0Q1Y2JqeHdJR05zWVhOelBWd2lUWE52VG05eWJXRnNYMjF5WDJOemMxOWhkSFJ5WENJKzBKQWdNVEFnTlM0NE5kQ2NJTkNRTlRBd0lOQ2hJRE0wTURJNExURTJJRngxTWpBeE15QXpNREFnMFlqUmdqeGNMM0ErWEc0OGNDQmpiR0Z6Y3oxY0lrMXpiMDV2Y20xaGJGOXRjbDlqYzNOZllYUjBjbHdpUHRDUUlERXdJRGJRbkNEUWtESTBNQ0F6TkRBeU9DMHhOaUJjZFRJd01UTWdNVFV3SU5DNjBMTThYQzl3UGx4dVBIQWdZMnhoYzNNOVhDSk5jMjlPYjNKdFlXeGZiWEpmWTNOelgyRjBkSEpjSWo3UWtDQXhNQ0EyMEp3ZzBKQTBNREFnTXpRd01qZ3RNVFlnWEhVeU1ERXpJREVnMFlJOFhDOXdQbHh1UEhBZ1kyeGhjM005WENKTmMyOU9iM0p0WVd4ZmJYSmZZM056WDJGMGRISmNJajdRa0NBeE1DQTIwSndnMEpBMU1EQWcwS0VnTXpRd01qZ3RNVFlnWEhVeU1ERXpJRExSZ3RDOVBGd3ZjRDVjYmp4d0lHTnNZWE56UFZ3aVRYTnZUbTl5YldGc1gyMXlYMk56YzE5aGRIUnlYQ0krUEhOd1lXNGdjM1I1YkdVOVhDSm1iMjUwTFhOcGVtVTZNVEV1TUhCME8yWnZiblF0Wm1GdGFXeDVPaWREWVd4cFluSnBKeXh6WVc1ekxYTmxjbWxtTzJOdmJHOXlPaU14UmpRNU4wUTdiWE52TFdaaGNtVmhjM1F0YkdGdVozVmhaMlU2UlU0dFZWTmNJajdDb0R4Y0wzTndZVzQrUEZ3dmNENWNianh3SUdOc1lYTnpQVndpVFhOdlRtOXliV0ZzWDIxeVgyTnpjMTloZEhSeVhDSStQSE53WVc0Z2MzUjViR1U5WENKbWIyNTBMWE5wZW1VNk1URXVNSEIwTzJadmJuUXRabUZ0YVd4NU9pZERZV3hwWW5KcEp5eHpZVzV6TFhObGNtbG1PMk52Ykc5eU9pTXhSalE1TjBRN2JYTnZMV1poY21WaGMzUXRiR0Z1WjNWaFoyVTZSVTR0VlZOY0lqN0NvRHhjTDNOd1lXNCtQRnd2Y0Q1Y2JqeGthWFkrWEc0OFpHbDJJSE4wZVd4bFBWd2lZbTl5WkdWeU9tNXZibVU3WW05eVpHVnlMWFJ2Y0RwemIyeHBaQ0FqUlRGRk1VVXhJREV1TUhCME8zQmhaR1JwYm1jNk15NHdjSFFnTUdOdElEQmpiU0F3WTIxY0lqNWNianh3SUdOc1lYTnpQVndpVFhOdlRtOXliV0ZzWDIxeVgyTnpjMTloZEhSeVhDSStQR0krUEhOd1lXNGdjM1I1YkdVOVhDSm1iMjUwTFhOcGVtVTZNVEV1TUhCME8yWnZiblF0Wm1GdGFXeDVPaWREWVd4cFluSnBKeXh6WVc1ekxYTmxjbWxtWENJK1JuSnZiVG84WEM5emNHRnVQanhjTDJJK1BITndZVzRnYzNSNWJHVTlYQ0ptYjI1MExYTnBlbVU2TVRFdU1IQjBPMlp2Ym5RdFptRnRhV3g1T2lkRFlXeHBZbkpwSnl4ellXNXpMWE5sY21sbVhDSStJRVJoYldseUlGTm9ZWEpwY0c5MklEdzhZU0JvY21WbVBWd2lMMk52YlhCdmMyVS9WRzg5WkdGdGFYSXVjMmhoY21sd2IzWXlNMEJ0WVdsc0xuSjFYQ0krWkdGdGFYSXVjMmhoY21sd2IzWXlNMEJ0WVdsc0xuSjFQRnd2WVQ0K1hHNDhZbkkrWEc0OFlqNVRaVzUwT2p4Y0wySStJRTF2Ym1SaGVTd2dVMlZ3ZEdWdFltVnlJRElzSURJd01qUWdNVEk2TURBZ1VFMDhZbkkrWEc0OFlqNVViem84WEM5aVBpRFFxTkN3MFlEUXVOQy8wTDdRc2lEUWxOQ3cwTHpRdU5HQUlOQ1kwWURRdGRDNjBMN1FzdEM0MFljZ1BEeGhJR2h5WldZOVhDSXZZMjl0Y0c5elpUOVViejF6YUdGeWFYQnZkbVJwUUhOd2F5NXlkVndpUG5Ob1lYSnBjRzkyWkdsQWMzQnJMbkoxUEZ3dllUNCtQR0p5UGx4dVBHSStVM1ZpYW1WamREbzhYQzlpUGlCVWMzUThYQzl6Y0dGdVBqeGNMM0ErWEc0OFhDOWthWFkrWEc0OFhDOWthWFkrWEc0OGNDQmpiR0Z6Y3oxY0lrMXpiMDV2Y20xaGJGOXRjbDlqYzNOZllYUjBjbHdpUHNLZ1BGd3ZjRDVjYmp4d1BqeHBQanh6Y0dGdUlITjBlV3hsUFZ3aVptOXVkQzF6YVhwbE9qRXdMakJ3ZER0amIyeHZjanBpYkhWbFhDSSswSkxRbmRDVjBLalFuZEN2MEs4ZzBKL1FudENuMEtMUWtEb2cwSlhSZ2RDNzBMZ2cwTDdSZ3RDLzBZRFFzTkN5MExqUmd0QzEwTHZSakNEUXZkQzEwTGpRdDlDeTBMWFJnZEdDMExYUXZTd2cwTDNRdFNEUXY5QzEwWURRdGRHRjBMN1F0TkM0MFlMUXRTRFF2OUMrSU5HQjBZSFJpOUM3MExyUXNOQzhMQ0RRdmRDMUlOQyswWUxRdjlHQTBMRFFzdEM3MFkvUXVkR0MwTFVnMEwvUXNOR0EwTDdRdTlDNExDRFJnU0RRdnRHQjBZTFF2dEdBMEw3UXR0QzkwTDdSZ2RHQzBZelJqaURRdnRHQzBMclJnTkdMMExMUXNOQzUwWUxRdFNEUXN0QzcwTDdRdHRDMTBMM1F1TkdQTGp4Y0wzTndZVzQrUEZ3dmFUNDhjM0JoYmlCemRIbHNaVDFjSW1admJuUXRjMmw2WlRveE1DNHdjSFE3WTI5c2IzSTZZbXgxWlZ3aVBqeGNMM053WVc0K1BGd3ZjRDVjYmp4d0lHTnNZWE56UFZ3aVRYTnZUbTl5YldGc1gyMXlYMk56YzE5aGRIUnlYQ0lnYzNSNWJHVTlYQ0p0WVhKbmFXNHRZbTkwZEc5dE9qRXlMakJ3ZEZ3aVBqeGljajVjYmp4aWNqNWNianhpY2o1Y2JqeGNMM0ErWEc0OFpHbDJQbHh1UEhBZ2MzUjViR1U5WENKdFlYSm5hVzR0ZEc5d09qQmpiVndpUGp4aWNqNWNiakV5TXp4aWNqNWNiaTB0UEdKeVBseHUwSjdSZ3RDLzBZRFFzTkN5MEx2UXRkQzkwTDRnMExqUXR5Qk5ZV2xzSU5DMDBMdlJqeUJCYm1SeWIybGtQRnd2Y0Q1Y2JqeGNMMlJwZGo1Y2JqeGNMMlJwZGo1Y2JqeHdJSE4wZVd4bFBWd2lZMjlzYjNJNkl6TmhOelZqTkR0bWIyNTBPamx3ZENCQmNtbGhiRndpUHRDajBMTFFzTkMyMExEUXRkQzgwWXZRdFNEUXV0QyswTHZRdTlDMTBMUFF1Q0RRdUNEUXY5Q3cwWURSZ3RDOTBMWFJnTkdMTER4Y0wzQStYRzQ4Y0NCemRIbHNaVDFjSW1OdmJHOXlPaU16WVRjMVl6UTdabTl1ZERvNWNIUWdRWEpwWVd4Y0lqN1FuZEN3MFlqUXNDRFFtdEMrMEx6UXY5Q3cwTDNRdU5HUElOQy8wWURRdU5DMDBMWFJnTkMyMExqUXN0Q3cwTFhSZ3RHQjBZOGcwWTNSZ3RDNDBZZlF0ZEdCMExyUXVOR0ZJTkMvMFlEUXVOQzkwWWJRdU5DLzBMN1FzaURRc3RDMTBMVFF0ZEM5MExqUmp5RFFzZEM0MExmUXZkQzEwWUhRc0NEUXVDRFF0TkMxMEx2UXNOQzEwWUlnMExMUmdkQzFJTkMwMEx2Ump5RFJndEMrMExQUXZpd2cwWWZSZ3RDKzBMSFJpeURRc3RDMzBMRFF1TkM4MEw3UXZ0R0MwTDNRdnRHSTBMWFF2ZEM0MFk4ZzBZRWcwTDNRc05HSTBMalF2TkM0SU5DLzBMRFJnTkdDMEwzUXRkR0EwTERRdk5DNElOR0IwWUxSZ05DKzBMalF1OUM0MFlIUmpDRFF2ZEN3SU5DLzBZRFF1TkM5MFliUXVOQy8wTERSaFNEUXZ0R0MwTHJSZ05HTDBZTFF2dEdCMFlMUXVDRFF1Q0RRdjlHQTBMN1F0OUdBMExEUmg5QzkwTDdSZ2RHQzBMZ3VJTkNmMEw3UmpkR0MwTDdRdk5HRElOQy8wWURRdnRHQjBMalF2Q0RRa3RDdzBZRWcwWUhRdnRDKzBMSFJpZEN3MFlMUmpDRFF2ZEN3MEx3ZzBMN1FzZEMrSU5DeTBZSFF0ZEdGWEc0ZzBMM1F0ZEN6MExEUmd0QzQwTExRdmRHTDBZVWcwWVRRc05DNjBZTFFzTkdGSU5DeTBMNGcwTExRdDlDdzBMalF2TkMrMEw3Umd0QzkwTDdSaU5DMTBMM1F1TkdQMFlVZzBZRWcwTDNRc05HSTBMWFF1U0RRdXRDKzBMelF2OUN3MEwzUXVOQzEwTGtnMEwvUXZpRFFzTkMwMFlEUXRkR0IwWU1nUEdFZ2MzUjViR1U5WENKamIyeHZjam9qTTJFM05XTTBPMXdpSUdoeVpXWTlYQ0l2TDJVdWJXRnBiQzV5ZFM5amIyMXdiM05sTHo5dFlXbHNkRzg5YldGcGJIUnZKVE5oWkc5MlpYSnBaVUJ6WTIwdWNuVmNJaUIwWVhKblpYUTlYQ0pmWW14aGJtdGNJaUFnY21Wc1BWd2lJRzV2YjNCbGJtVnlJRzV2Y21WbVpYSnlaWEpjSWlBK1hHNWtiM1psY21sbFFITmpiUzV5ZFR4Y0wyRStMaURRa3RHQjBZOGcwTGpRdmRHRTBMN1JnTkM4MExEUmh0QzQwWThnMEwvUXZ0R0IwWUxSZzlDLzBMRFF0ZEdDSU5DeUlOQzkwTFhRdDlDdzBMTFF1TkdCMExqUXZOR0QwWTRnMFlIUXU5R0QwTGJRc2RHRElOQ3kwTDNSZzlHQzBZRFF0ZEM5MEwzUXRkQ3owTDRnMExEUmc5QzAwTGpSZ3RDd0xqeGNMM0ErWEc0OGNDQnpkSGxzWlQxY0ltTnZiRzl5T2lNellUYzFZelE3Wm05dWREbzVjSFFnUVhKcFlXeGNJajdRbjlHQTBMWFJndEMxMEwzUXQ5QzQwTGdnMEwvUXZpRFF1dEN3MFlmUXRkR0IwWUxRc3RHRElOQyswTEhSZ2RDNzBZUFF0dEM0MExMUXNOQzkwTGpSanlEUXVOQzcwTGdnMFlMUXZ0Q3kwTERSZ05Dd0lOQy8wWURRdU5DOTBMalF2TkN3MFk3Umd0R0IwWThnMEwzUXNDRFJndEMxMEx2UXRkR0UwTDdRdlNEUXM5QyswWURSajlHSDBMWFF1U0RRdTlDNDBMM1F1TkM0WEc0OGRUNDhjM0JoYmlCamJHRnpjejFjSW1wekxYQm9iMjVsTFc1MWJXSmxjbHdpUGpndE9EQXdMVGN3TURBdE1USXpQRnd2YzNCaGJqNDhYQzkxUGk0ZzBKZlFzdEMrMEwzUXV0QzRJTkMvMEw0ZzBLRFF2dEdCMFlIUXVOQzRJTkN4MExYUmdkQy8wTHZRc05HQzBMM1F2anhjTDNBK1hHNWNibHh1UEZ3dlpHbDJQanhjTDJScGRqNWNiaUFnSUNBZ0lDQWdYRzRnSUNBZ1BGd3ZaR2wyUGx4dVBGd3ZaR2wyUGp4Y0wySnNiMk5yY1hWdmRHVStQRnd2UWs5RVdUNDhYQzlJVkUxTVBseHVJbjA9')
    # order_rec.save_truth_test(content="{'req_number': '187ca897-4b2c-4b07-aa75-4f0d9dff8fc5', 'mail_code': '0057653611', 'user': 'SHARIPOVDI', 'positions': [{'position_id': '4', 'true_material': '000000000000083739', 'true_ei': 'ШТ', 'true_value': '15.000', 'spec_mat': ''}]}".replace("'", '"'))