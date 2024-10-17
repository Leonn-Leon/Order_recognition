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
    # order_rec.consumer_test(content="""Б НЛГ 30Б1 шт""")
    # order_rec.consumer_test(content="""Б профильная 75x750x0.9 L 6000 9 шт
    # А 45 68 34шт
    # У 45 68 34шт""")
    # order_rec.consumer_test(hash='ZXlKaWRXTnJaWFJPWVcxbElqb2lZM0p0TFdWdFlXbHNJaXdpYjJKcVpXTjBUbUZ0WlNJNkltMXpaMTgxTm1ZeU0ySTBZemt4Tm1GaVptWTVOalUxWWpaall6azJNR1UyTldaaU1TSXNJbVpwYkdWRGIyNTBaVzUwSWpvaVBHUnBkaUJrYVhJOVhDSnNkSEpjSWo0OFluSStQR0p5UGp4a2FYWWdZMnhoYzNNOVhDSm5iV0ZwYkY5eGRXOTBaVndpUGp4a2FYWWdaR2x5UFZ3aWJIUnlYQ0lnWTJ4aGMzTTlYQ0puYldGcGJGOWhkSFJ5WENJK0xTMHRMUzB0TFMwdExTQkdiM0ozWVhKa1pXUWdiV1Z6YzJGblpTQXRMUzB0TFMwdExTMDhZbkkrMEo3Umdqb2dQSE4wY205dVp5QmpiR0Z6Y3oxY0ltZHRZV2xzWDNObGJtUmxjbTVoYldWY0lpQmthWEk5WENKaGRYUnZYQ0krMEtqUXNOR0EwTGpRdjlDKzBMSWcwSlRRc05DODBMalJnQ0RRbU5HQTBMWFF1dEMrMExMUXVOR0hQRnd2YzNSeWIyNW5QaUE4YzNCaGJpQmthWEk5WENKaGRYUnZYQ0krSm14ME96eGhJR2h5WldZOVhDSnRZV2xzZEc4NmMyaGhjbWx3YjNaa2FVQnpjR3N1Y25WY0lqNXphR0Z5YVhCdmRtUnBRSE53YXk1eWRUeGNMMkUrSm1kME96eGNMM053WVc0K1BHSnlQa1JoZEdVNklOQ3kwWUlzSURFMUlOQyswTHJSZ2k0Z01qQXlORngxTWpBeVp0Q3pMaURRc2lBeE5EbzFNVHhpY2o1VGRXSnFaV04wT2lCR1Z6b2cwTGZRc05HUDBMTFF1dEN3UEdKeVBsUnZPaUJFYldsMGNtbDVJRXRoY21GcmRXeHZkaUFtYkhRN1BHRWdhSEpsWmoxY0ltMWhhV3gwYnpwcllYSmhhMkZyZFd4dlptWkFaMjFoYVd3dVkyOXRYQ0krYTJGeVlXdGhhM1ZzYjJabVFHZHRZV2xzTG1OdmJUeGNMMkUrSm1kME96eGljajQ4WEM5a2FYWStQR0p5UGp4aWNqNDhaR2wySUdOc1lYTnpQVndpYlhObk9EWTVOelV4T1RZMk9ETXdNVGcyT1RZeE5Gd2lQbHh5WEc1Y2NseHVYSEpjYmx4eVhHNWNjbHh1WEhKY2JqeGthWFlnYkdGdVp6MWNJbEpWWENJZ2JHbHVhejFjSW1Kc2RXVmNJaUIyYkdsdWF6MWNJbkIxY25Cc1pWd2lQbHh5WEc0OFpHbDJJR05zWVhOelBWd2liVjg0TmprM05URTVOalk0TXpBeE9EWTVOakUwVjI5eVpGTmxZM1JwYjI0eFhDSStYSEpjYmp4d0lHTnNZWE56UFZ3aVRYTnZUbTl5YldGc1hDSSswSlRRdnRDeDBZRFF2dEMxSU5HRDBZTFJnTkMrTGlBOGRUNDhYQzkxUGp4MVBqeGNMM1UrUEZ3dmNENWNjbHh1UEdScGRqNWNjbHh1UEhBZ1kyeGhjM005WENKTmMyOU9iM0p0WVd4Y0lqN0NvRHgxUGp4Y0wzVStQSFUrUEZ3dmRUNDhYQzl3UGx4eVhHNDhkR0ZpYkdVZ1ltOXlaR1Z5UFZ3aU1Gd2lJR05sYkd4emNHRmphVzVuUFZ3aU1Gd2lJR05sYkd4d1lXUmthVzVuUFZ3aU1Gd2lJSGRwWkhSb1BWd2lNRndpSUhOMGVXeGxQVndpZDJsa2RHZzZOREF3TGpWd2RGd2lQbHh5WEc0OGRHSnZaSGsrWEhKY2JqeDBjaUJ6ZEhsc1pUMWNJbWhsYVdkb2REb3hOUzR3Y0hSY0lqNWNjbHh1UEhSa0lIZHBaSFJvUFZ3aU16VTFYQ0lnYzNSNWJHVTlYQ0ozYVdSMGFEb3lOall1TUhCME8zQmhaR1JwYm1jNk1HTnRJREJqYlNBd1kyMGdNR050TzJobGFXZG9kRG94TlM0d2NIUmNJajVjY2x4dVBIQWdZMnhoYzNNOVhDSk5jMjlPYjNKdFlXeGNJajdRdTlDNDBZSFJnaUF6SUNneE1qVXcwWVV5TlRBd0tTRFJnZEdDMExEUXU5R01JREE0UEhVK1BGd3ZkVDQ4ZFQ0OFhDOTFQanhjTDNBK1hISmNianhjTDNSa1BseHlYRzQ4ZEdRZ2QybGtkR2c5WENJNU5Wd2lJSE4wZVd4bFBWd2lkMmxrZEdnNk56RXVNSEIwTzNCaFpHUnBibWM2TUdOdElEQmpiU0F3WTIwZ01HTnRPMmhsYVdkb2REb3hOUzR3Y0hSY0lqNWNjbHh1UEhBZ1kyeGhjM005WENKTmMyOU9iM0p0WVd4Y0lpQmhiR2xuYmoxY0ltTmxiblJsY2x3aUlITjBlV3hsUFZ3aWRHVjRkQzFoYkdsbmJqcGpaVzUwWlhKY0lqN1F2OUN3MFlmUXV0Q3dQSFUrUEZ3dmRUNDhkVDQ4WEM5MVBqeGNMM0ErWEhKY2JqeGNMM1JrUGx4eVhHNDhkR1FnZDJsa2RHZzlYQ0k0TkZ3aUlITjBlV3hsUFZ3aWQybGtkR2c2TmpNdU1IQjBPM0JoWkdScGJtYzZNR050SURCamJTQXdZMjBnTUdOdE8yaGxhV2RvZERveE5TNHdjSFJjSWo1Y2NseHVQSEFnWTJ4aGMzTTlYQ0pOYzI5T2IzSnRZV3hjSWlCaGJHbG5iajFjSW1ObGJuUmxjbHdpSUhOMGVXeGxQVndpZEdWNGRDMWhiR2xuYmpwalpXNTBaWEpjSWo0eFBIVStQRnd2ZFQ0OGRUNDhYQzkxUGp4Y0wzQStYSEpjYmp4Y0wzUmtQbHh5WEc0OFhDOTBjajVjY2x4dVBIUnlJSE4wZVd4bFBWd2lhR1ZwWjJoME9qRTFMakJ3ZEZ3aVBseHlYRzQ4ZEdRZ2MzUjViR1U5WENKd1lXUmthVzVuT2pCamJTQXdZMjBnTUdOdElEQmpiVHRvWldsbmFIUTZNVFV1TUhCMFhDSStQRnd2ZEdRK1hISmNiangwWkNCemRIbHNaVDFjSW5CaFpHUnBibWM2TUdOdElEQmpiU0F3WTIwZ01HTnRPMmhsYVdkb2REb3hOUzR3Y0hSY0lqNDhYQzkwWkQ1Y2NseHVQSFJrSUhOMGVXeGxQVndpY0dGa1pHbHVaem93WTIwZ01HTnRJREJqYlNBd1kyMDdhR1ZwWjJoME9qRTFMakJ3ZEZ3aVBqeGNMM1JrUGx4eVhHNDhYQzkwY2o1Y2NseHVQSFJ5SUhOMGVXeGxQVndpYUdWcFoyaDBPakUxTGpCd2RGd2lQbHh5WEc0OGRHUWdjM1I1YkdVOVhDSndZV1JrYVc1bk9qQmpiU0F3WTIwZ01HTnRJREJqYlR0b1pXbG5hSFE2TVRVdU1IQjBYQ0krWEhKY2JqeHdJR05zWVhOelBWd2lUWE52VG05eWJXRnNYQ0krMEx2UXVOR0IwWUlnTlNBb01UVXdNTkdGTmpBd01Da2cwWUhSZ3RDdzBMdlJqQ0F6UEhVK1BGd3ZkVDQ4ZFQ0OFhDOTFQanhjTDNBK1hISmNianhjTDNSa1BseHlYRzQ4ZEdRZ2MzUjViR1U5WENKd1lXUmthVzVuT2pCamJTQXdZMjBnTUdOdElEQmpiVHRvWldsbmFIUTZNVFV1TUhCMFhDSStYSEpjYmp4d0lHTnNZWE56UFZ3aVRYTnZUbTl5YldGc1hDSWdZV3hwWjI0OVhDSmpaVzUwWlhKY0lpQnpkSGxzWlQxY0luUmxlSFF0WVd4cFoyNDZZMlZ1ZEdWeVhDSSswWWpSZ2p4MVBqeGNMM1UrUEhVK1BGd3ZkVDQ4WEM5d1BseHlYRzQ4WEM5MFpENWNjbHh1UEhSa0lITjBlV3hsUFZ3aWNHRmtaR2x1Wnpvd1kyMGdNR050SURCamJTQXdZMjA3YUdWcFoyaDBPakUxTGpCd2RGd2lQbHh5WEc0OGNDQmpiR0Z6Y3oxY0lrMXpiMDV2Y20xaGJGd2lJR0ZzYVdkdVBWd2lZMlZ1ZEdWeVhDSWdjM1I1YkdVOVhDSjBaWGgwTFdGc2FXZHVPbU5sYm5SbGNsd2lQak04ZFQ0OFhDOTFQangxUGp4Y0wzVStQRnd2Y0Q1Y2NseHVQRnd2ZEdRK1hISmNianhjTDNSeVBseHlYRzQ4ZEhJZ2MzUjViR1U5WENKb1pXbG5hSFE2TVRVdU1IQjBYQ0krWEhKY2JqeDBaQ0J6ZEhsc1pUMWNJbkJoWkdScGJtYzZNR050SURCamJTQXdZMjBnTUdOdE8yaGxhV2RvZERveE5TNHdjSFJjSWo0OFhDOTBaRDVjY2x4dVBIUmtJSE4wZVd4bFBWd2ljR0ZrWkdsdVp6b3dZMjBnTUdOdElEQmpiU0F3WTIwN2FHVnBaMmgwT2pFMUxqQndkRndpUGp4Y0wzUmtQbHh5WEc0OGRHUWdjM1I1YkdVOVhDSndZV1JrYVc1bk9qQmpiU0F3WTIwZ01HTnRJREJqYlR0b1pXbG5hSFE2TVRVdU1IQjBYQ0krUEZ3dmRHUStYSEpjYmp4Y0wzUnlQbHh5WEc0OGRISWdjM1I1YkdVOVhDSm9aV2xuYUhRNk1UVXVNSEIwWENJK1hISmNiangwWkNCemRIbHNaVDFjSW5CaFpHUnBibWM2TUdOdElEQmpiU0F3WTIwZ01HTnRPMmhsYVdkb2REb3hOUzR3Y0hSY0lqNWNjbHh1UEhBZ1kyeGhjM005WENKTmMyOU9iM0p0WVd4Y0lqN1F1OUM0MFlIUmdpQTJJQ2d4TlRBdzBZVTJNREF3S1NEUmdkR0MwTERRdTlHTUlETThkVDQ4WEM5MVBqeDFQanhjTDNVK1BGd3ZjRDVjY2x4dVBGd3ZkR1ErWEhKY2JqeDBaQ0J6ZEhsc1pUMWNJbkJoWkdScGJtYzZNR050SURCamJTQXdZMjBnTUdOdE8yaGxhV2RvZERveE5TNHdjSFJjSWo1Y2NseHVQSEFnWTJ4aGMzTTlYQ0pOYzI5T2IzSnRZV3hjSWlCaGJHbG5iajFjSW1ObGJuUmxjbHdpSUhOMGVXeGxQVndpZEdWNGRDMWhiR2xuYmpwalpXNTBaWEpjSWo3UmlOR0NQSFUrUEZ3dmRUNDhkVDQ4WEM5MVBqeGNMM0ErWEhKY2JqeGNMM1JrUGx4eVhHNDhkR1FnYzNSNWJHVTlYQ0p3WVdSa2FXNW5PakJqYlNBd1kyMGdNR050SURCamJUdG9aV2xuYUhRNk1UVXVNSEIwWENJK1hISmNianh3SUdOc1lYTnpQVndpVFhOdlRtOXliV0ZzWENJZ1lXeHBaMjQ5WENKalpXNTBaWEpjSWlCemRIbHNaVDFjSW5SbGVIUXRZV3hwWjI0NlkyVnVkR1Z5WENJK01UeDFQanhjTDNVK1BIVStQRnd2ZFQ0OFhDOXdQbHh5WEc0OFhDOTBaRDVjY2x4dVBGd3ZkSEkrWEhKY2JqeDBjaUJ6ZEhsc1pUMWNJbWhsYVdkb2REb3hOUzR3Y0hSY0lqNWNjbHh1UEhSa0lITjBlV3hsUFZ3aWNHRmtaR2x1Wnpvd1kyMGdNR050SURCamJTQXdZMjA3YUdWcFoyaDBPakUxTGpCd2RGd2lQanhjTDNSa1BseHlYRzQ4ZEdRZ2MzUjViR1U5WENKd1lXUmthVzVuT2pCamJTQXdZMjBnTUdOdElEQmpiVHRvWldsbmFIUTZNVFV1TUhCMFhDSStQRnd2ZEdRK1hISmNiangwWkNCemRIbHNaVDFjSW5CaFpHUnBibWM2TUdOdElEQmpiU0F3WTIwZ01HTnRPMmhsYVdkb2REb3hOUzR3Y0hSY0lqNDhYQzkwWkQ1Y2NseHVQRnd2ZEhJK1hISmNiangwY2lCemRIbHNaVDFjSW1obGFXZG9kRG94TlM0d2NIUmNJajVjY2x4dVBIUmtJSE4wZVd4bFBWd2ljR0ZrWkdsdVp6b3dZMjBnTUdOdElEQmpiU0F3WTIwN2FHVnBaMmgwT2pFMUxqQndkRndpUGx4eVhHNDhjQ0JqYkdGemN6MWNJazF6YjA1dmNtMWhiRndpUHRDNzBMalJnZEdDSURFd0lDZ3hOVEF3MFlVMk1EQXdLU0RSZ2RHQzBMRFF1OUdNSURNOGRUNDhYQzkxUGp4MVBqeGNMM1UrUEZ3dmNENWNjbHh1UEZ3dmRHUStYSEpjYmp4MFpDQnpkSGxzWlQxY0luQmhaR1JwYm1jNk1HTnRJREJqYlNBd1kyMGdNR050TzJobGFXZG9kRG94TlM0d2NIUmNJajVjY2x4dVBIQWdZMnhoYzNNOVhDSk5jMjlPYjNKdFlXeGNJaUJoYkdsbmJqMWNJbU5sYm5SbGNsd2lJSE4wZVd4bFBWd2lkR1Y0ZEMxaGJHbG5ianBqWlc1MFpYSmNJajdSaU5HQ1BIVStQRnd2ZFQ0OGRUNDhYQzkxUGp4Y0wzQStYSEpjYmp4Y0wzUmtQbHh5WEc0OGRHUWdjM1I1YkdVOVhDSndZV1JrYVc1bk9qQmpiU0F3WTIwZ01HTnRJREJqYlR0b1pXbG5hSFE2TVRVdU1IQjBYQ0krWEhKY2JqeHdJR05zWVhOelBWd2lUWE52VG05eWJXRnNYQ0lnWVd4cFoyNDlYQ0pqWlc1MFpYSmNJaUJ6ZEhsc1pUMWNJblJsZUhRdFlXeHBaMjQ2WTJWdWRHVnlYQ0krTWp4MVBqeGNMM1UrUEhVK1BGd3ZkVDQ4WEM5d1BseHlYRzQ4WEM5MFpENWNjbHh1UEZ3dmRISStYSEpjYmp4MGNpQnpkSGxzWlQxY0ltaGxhV2RvZERveE5TNHdjSFJjSWo1Y2NseHVQSFJrSUhOMGVXeGxQVndpY0dGa1pHbHVaem93WTIwZ01HTnRJREJqYlNBd1kyMDdhR1ZwWjJoME9qRTFMakJ3ZEZ3aVBqeGNMM1JrUGx4eVhHNDhkR1FnYzNSNWJHVTlYQ0p3WVdSa2FXNW5PakJqYlNBd1kyMGdNR050SURCamJUdG9aV2xuYUhRNk1UVXVNSEIwWENJK1BGd3ZkR1ErWEhKY2JqeDBaQ0J6ZEhsc1pUMWNJbkJoWkdScGJtYzZNR050SURCamJTQXdZMjBnTUdOdE8yaGxhV2RvZERveE5TNHdjSFJjSWo0OFhDOTBaRDVjY2x4dVBGd3ZkSEkrWEhKY2JqeDBjaUJ6ZEhsc1pUMWNJbWhsYVdkb2REb3hOUzR3Y0hSY0lqNWNjbHh1UEhSa0lITjBlV3hsUFZ3aWNHRmtaR2x1Wnpvd1kyMGdNR050SURCamJTQXdZMjA3YUdWcFoyaDBPakUxTGpCd2RGd2lQbHh5WEc0OGNDQmpiR0Z6Y3oxY0lrMXpiMDV2Y20xaGJGd2lQdEM3MExqUmdkR0NJREV5SUNneE5UQXcwWVUyTURBd0tTRFJnZEdDMExEUXU5R01JRE04ZFQ0OFhDOTFQangxUGp4Y0wzVStQRnd2Y0Q1Y2NseHVQRnd2ZEdRK1hISmNiangwWkNCemRIbHNaVDFjSW5CaFpHUnBibWM2TUdOdElEQmpiU0F3WTIwZ01HTnRPMmhsYVdkb2REb3hOUzR3Y0hSY0lqNWNjbHh1UEhBZ1kyeGhjM005WENKTmMyOU9iM0p0WVd4Y0lpQmhiR2xuYmoxY0ltTmxiblJsY2x3aUlITjBlV3hsUFZ3aWRHVjRkQzFoYkdsbmJqcGpaVzUwWlhKY0lqN1JpTkdDUEhVK1BGd3ZkVDQ4ZFQ0OFhDOTFQanhjTDNBK1hISmNianhjTDNSa1BseHlYRzQ4ZEdRZ2MzUjViR1U5WENKd1lXUmthVzVuT2pCamJTQXdZMjBnTUdOdElEQmpiVHRvWldsbmFIUTZNVFV1TUhCMFhDSStYSEpjYmp4d0lHTnNZWE56UFZ3aVRYTnZUbTl5YldGc1hDSWdZV3hwWjI0OVhDSmpaVzUwWlhKY0lpQnpkSGxzWlQxY0luUmxlSFF0WVd4cFoyNDZZMlZ1ZEdWeVhDSStNangxUGp4Y0wzVStQSFUrUEZ3dmRUNDhYQzl3UGx4eVhHNDhYQzkwWkQ1Y2NseHVQRnd2ZEhJK1hISmNiangwY2lCemRIbHNaVDFjSW1obGFXZG9kRG94TlM0d2NIUmNJajVjY2x4dVBIUmtJSE4wZVd4bFBWd2ljR0ZrWkdsdVp6b3dZMjBnTUdOdElEQmpiU0F3WTIwN2FHVnBaMmgwT2pFMUxqQndkRndpUGp4Y0wzUmtQbHh5WEc0OGRHUWdjM1I1YkdVOVhDSndZV1JrYVc1bk9qQmpiU0F3WTIwZ01HTnRJREJqYlR0b1pXbG5hSFE2TVRVdU1IQjBYQ0krUEZ3dmRHUStYSEpjYmp4MFpDQnpkSGxzWlQxY0luQmhaR1JwYm1jNk1HTnRJREJqYlNBd1kyMGdNR050TzJobGFXZG9kRG94TlM0d2NIUmNJajQ4WEM5MFpENWNjbHh1UEZ3dmRISStYSEpjYmp4MGNpQnpkSGxzWlQxY0ltaGxhV2RvZERveE5TNHdjSFJjSWo1Y2NseHVQSFJrSUhkcFpIUm9QVndpTXpVMVhDSWdjM1I1YkdVOVhDSjNhV1IwYURveU5qWXVNSEIwTzNCaFpHUnBibWM2TUdOdElEQmpiU0F3WTIwZ01HTnRPMmhsYVdkb2REb3hOUzR3Y0hSY0lqNWNjbHh1UEhBZ1kyeGhjM005WENKTmMyOU9iM0p0WVd4Y0lqN1JpTkN5MExYUXU5QzcwTFhSZ0NBeE10Q2ZJTkdCMFlMUXNOQzcwWXdnTXp4MVBqeGNMM1UrUEhVK1BGd3ZkVDQ4WEM5d1BseHlYRzQ4WEM5MFpENWNjbHh1UEhSa0lITjBlV3hsUFZ3aWNHRmtaR2x1Wnpvd1kyMGdNR050SURCamJTQXdZMjA3YUdWcFoyaDBPakUxTGpCd2RGd2lQbHh5WEc0OGNDQmpiR0Z6Y3oxY0lrMXpiMDV2Y20xaGJGd2lJR0ZzYVdkdVBWd2lZMlZ1ZEdWeVhDSWdjM1I1YkdVOVhDSjBaWGgwTFdGc2FXZHVPbU5sYm5SbGNsd2lQdEM2MExNOGRUNDhYQzkxUGp4MVBqeGNMM1UrUEZ3dmNENWNjbHh1UEZ3dmRHUStYSEpjYmp4MFpDQnpkSGxzWlQxY0luQmhaR1JwYm1jNk1HTnRJREJqYlNBd1kyMGdNR050TzJobGFXZG9kRG94TlM0d2NIUmNJajVjY2x4dVBIQWdZMnhoYzNNOVhDSk5jMjlPYjNKdFlXeGNJaUJoYkdsbmJqMWNJbU5sYm5SbGNsd2lJSE4wZVd4bFBWd2lkR1Y0ZEMxaGJHbG5ianBqWlc1MFpYSmNJajR5TURBd1BIVStQRnd2ZFQ0OGRUNDhYQzkxUGp4Y0wzQStYSEpjYmp4Y0wzUmtQbHh5WEc0OFhDOTBjajVjY2x4dVBIUnlJSE4wZVd4bFBWd2lhR1ZwWjJoME9qRTFMakJ3ZEZ3aVBseHlYRzQ4ZEdRZ2QybGtkR2c5WENJek5UVmNJaUJ6ZEhsc1pUMWNJbmRwWkhSb09qSTJOaTR3Y0hRN2NHRmtaR2x1Wnpvd1kyMGdNR050SURCamJTQXdZMjA3YUdWcFoyaDBPakUxTGpCd2RGd2lQanhjTDNSa1BseHlYRzQ4ZEdRZ2MzUjViR1U5WENKd1lXUmthVzVuT2pCamJTQXdZMjBnTUdOdElEQmpiVHRvWldsbmFIUTZNVFV1TUhCMFhDSStQRnd2ZEdRK1hISmNiangwWkNCemRIbHNaVDFjSW5CaFpHUnBibWM2TUdOdElEQmpiU0F3WTIwZ01HTnRPMmhsYVdkb2REb3hOUzR3Y0hSY0lqNDhYQzkwWkQ1Y2NseHVQRnd2ZEhJK1hISmNiangwY2lCemRIbHNaVDFjSW1obGFXZG9kRG94TlM0d2NIUmNJajVjY2x4dVBIUmtJSE4wZVd4bFBWd2ljR0ZrWkdsdVp6b3dZMjBnTUdOdElEQmpiU0F3WTIwN2FHVnBaMmgwT2pFMUxqQndkRndpUGx4eVhHNDhjQ0JqYkdGemN6MWNJazF6YjA1dmNtMWhiRndpUHRHQzBZRFJnOUN4MExBZzBML1JnTkMrMFlUUXVOQzcwWXpRdmRDdzBZOGdORERSaFRRdzBZVXlJTkdCMFlMUXNOQzcwWXdnTXp4MVBqeGNMM1UrUEhVK1BGd3ZkVDQ4WEM5d1BseHlYRzQ4WEM5MFpENWNjbHh1UEhSa0lITjBlV3hsUFZ3aWNHRmtaR2x1Wnpvd1kyMGdNR050SURCamJTQXdZMjA3YUdWcFoyaDBPakUxTGpCd2RGd2lQbHh5WEc0OGNDQmpiR0Z6Y3oxY0lrMXpiMDV2Y20xaGJGd2lJR0ZzYVdkdVBWd2lZMlZ1ZEdWeVhDSWdjM1I1YkdVOVhDSjBaWGgwTFdGc2FXZHVPbU5sYm5SbGNsd2lQdEM2MExNOGRUNDhYQzkxUGp4MVBqeGNMM1UrUEZ3dmNENWNjbHh1UEZ3dmRHUStYSEpjYmp4MFpDQnpkSGxzWlQxY0luQmhaR1JwYm1jNk1HTnRJREJqYlNBd1kyMGdNR050TzJobGFXZG9kRG94TlM0d2NIUmNJajVjY2x4dVBIQWdZMnhoYzNNOVhDSk5jMjlPYjNKdFlXeGNJaUJoYkdsbmJqMWNJbU5sYm5SbGNsd2lJSE4wZVd4bFBWd2lkR1Y0ZEMxaGJHbG5ianBqWlc1MFpYSmNJajQxTURBOGRUNDhYQzkxUGp4MVBqeGNMM1UrUEZ3dmNENWNjbHh1UEZ3dmRHUStYSEpjYmp4Y0wzUnlQbHh5WEc0OGRISWdjM1I1YkdVOVhDSm9aV2xuYUhRNk1UVXVNSEIwWENJK1hISmNiangwWkNCemRIbHNaVDFjSW5CaFpHUnBibWM2TUdOdElEQmpiU0F3WTIwZ01HTnRPMmhsYVdkb2REb3hOUzR3Y0hSY0lqNDhYQzkwWkQ1Y2NseHVQSFJrSUhOMGVXeGxQVndpY0dGa1pHbHVaem93WTIwZ01HTnRJREJqYlNBd1kyMDdhR1ZwWjJoME9qRTFMakJ3ZEZ3aVBqeGNMM1JrUGx4eVhHNDhkR1FnYzNSNWJHVTlYQ0p3WVdSa2FXNW5PakJqYlNBd1kyMGdNR050SURCamJUdG9aV2xuYUhRNk1UVXVNSEIwWENJK1BGd3ZkR1ErWEhKY2JqeGNMM1J5UGx4eVhHNDhkSElnYzNSNWJHVTlYQ0pvWldsbmFIUTZNVFV1TUhCMFhDSStYSEpjYmp4MFpDQnpkSGxzWlQxY0luQmhaR1JwYm1jNk1HTnRJREJqYlNBd1kyMGdNR050TzJobGFXZG9kRG94TlM0d2NIUmNJajVjY2x4dVBIQWdZMnhoYzNNOVhDSk5jMjlPYjNKdFlXeGNJajdSZ3RHQTBZUFFzZEN3SU5DLzBZRFF2dEdFMExqUXU5R00wTDNRc05HUElEVXcwWVUxTU5HRk15RFJnZEdDMExEUXU5R01JRE04ZFQ0OFhDOTFQangxUGp4Y0wzVStQRnd2Y0Q1Y2NseHVQRnd2ZEdRK1hISmNiangwWkNCemRIbHNaVDFjSW5CaFpHUnBibWM2TUdOdElEQmpiU0F3WTIwZ01HTnRPMmhsYVdkb2REb3hOUzR3Y0hSY0lqNWNjbHh1UEhBZ1kyeGhjM005WENKTmMyOU9iM0p0WVd4Y0lpQmhiR2xuYmoxY0ltTmxiblJsY2x3aUlITjBlV3hsUFZ3aWRHVjRkQzFoYkdsbmJqcGpaVzUwWlhKY0lqN1F1dEN6UEhVK1BGd3ZkVDQ4ZFQ0OFhDOTFQanhjTDNBK1hISmNianhjTDNSa1BseHlYRzQ4ZEdRZ2MzUjViR1U5WENKd1lXUmthVzVuT2pCamJTQXdZMjBnTUdOdElEQmpiVHRvWldsbmFIUTZNVFV1TUhCMFhDSStYSEpjYmp4d0lHTnNZWE56UFZ3aVRYTnZUbTl5YldGc1hDSWdZV3hwWjI0OVhDSmpaVzUwWlhKY0lpQnpkSGxzWlQxY0luUmxlSFF0WVd4cFoyNDZZMlZ1ZEdWeVhDSStOVEF3UEhVK1BGd3ZkVDQ4ZFQ0OFhDOTFQanhjTDNBK1hISmNianhjTDNSa1BseHlYRzQ4WEM5MGNqNWNjbHh1UEhSeUlITjBlV3hsUFZ3aWFHVnBaMmgwT2pFMUxqQndkRndpUGx4eVhHNDhkR1FnYzNSNWJHVTlYQ0p3WVdSa2FXNW5PakJqYlNBd1kyMGdNR050SURCamJUdG9aV2xuYUhRNk1UVXVNSEIwWENJK1BGd3ZkR1ErWEhKY2JqeDBaQ0J6ZEhsc1pUMWNJbkJoWkdScGJtYzZNR050SURCamJTQXdZMjBnTUdOdE8yaGxhV2RvZERveE5TNHdjSFJjSWo0OFhDOTBaRDVjY2x4dVBIUmtJSE4wZVd4bFBWd2ljR0ZrWkdsdVp6b3dZMjBnTUdOdElEQmpiU0F3WTIwN2FHVnBaMmgwT2pFMUxqQndkRndpUGp4Y0wzUmtQbHh5WEc0OFhDOTBjajVjY2x4dVBIUnlJSE4wZVd4bFBWd2lhR1ZwWjJoME9qRTFMakJ3ZEZ3aVBseHlYRzQ4ZEdRZ2MzUjViR1U5WENKd1lXUmthVzVuT2pCamJTQXdZMjBnTUdOdElEQmpiVHRvWldsbmFIUTZNVFV1TUhCMFhDSStYSEpjYmp4d0lHTnNZWE56UFZ3aVRYTnZUbTl5YldGc1hDSSswWVBRczlDKzBMdlF2dEM2SURRMTBZVTBOZEdGTkNEUmdkR0MwTERRdTlHTUlETThkVDQ4WEM5MVBqeDFQanhjTDNVK1BGd3ZjRDVjY2x4dVBGd3ZkR1ErWEhKY2JqeDBaQ0J6ZEhsc1pUMWNJbkJoWkdScGJtYzZNR050SURCamJTQXdZMjBnTUdOdE8yaGxhV2RvZERveE5TNHdjSFJjSWo1Y2NseHVQSEFnWTJ4aGMzTTlYQ0pOYzI5T2IzSnRZV3hjSWlCaGJHbG5iajFjSW1ObGJuUmxjbHdpSUhOMGVXeGxQVndpZEdWNGRDMWhiR2xuYmpwalpXNTBaWEpjSWo3UXV0Q3pQSFUrUEZ3dmRUNDhkVDQ4WEM5MVBqeGNMM0ErWEhKY2JqeGNMM1JrUGx4eVhHNDhkR1FnYzNSNWJHVTlYQ0p3WVdSa2FXNW5PakJqYlNBd1kyMGdNR050SURCamJUdG9aV2xuYUhRNk1UVXVNSEIwWENJK1hISmNianh3SUdOc1lYTnpQVndpVFhOdlRtOXliV0ZzWENJZ1lXeHBaMjQ5WENKalpXNTBaWEpjSWlCemRIbHNaVDFjSW5SbGVIUXRZV3hwWjI0NlkyVnVkR1Z5WENJK05UQXdQSFUrUEZ3dmRUNDhkVDQ4WEM5MVBqeGNMM0ErWEhKY2JqeGNMM1JrUGx4eVhHNDhYQzkwY2o1Y2NseHVQSFJ5SUhOMGVXeGxQVndpYUdWcFoyaDBPakUxTGpCd2RGd2lQbHh5WEc0OGRHUWdjM1I1YkdVOVhDSndZV1JrYVc1bk9qQmpiU0F3WTIwZ01HTnRJREJqYlR0b1pXbG5hSFE2TVRVdU1IQjBYQ0krUEZ3dmRHUStYSEpjYmp4MFpDQnpkSGxzWlQxY0luQmhaR1JwYm1jNk1HTnRJREJqYlNBd1kyMGdNR050TzJobGFXZG9kRG94TlM0d2NIUmNJajQ4WEM5MFpENWNjbHh1UEhSa0lITjBlV3hsUFZ3aWNHRmtaR2x1Wnpvd1kyMGdNR050SURCamJTQXdZMjA3YUdWcFoyaDBPakUxTGpCd2RGd2lQanhjTDNSa1BseHlYRzQ4WEM5MGNqNWNjbHh1UEhSeUlITjBlV3hsUFZ3aWFHVnBaMmgwT2pFMUxqQndkRndpUGx4eVhHNDhkR1FnYzNSNWJHVTlYQ0p3WVdSa2FXNW5PakJqYlNBd1kyMGdNR050SURCamJUdG9aV2xuYUhRNk1UVXVNSEIwWENJK1hISmNianh3SUdOc1lYTnpQVndpVFhOdlRtOXliV0ZzWENJKzBZUFFzOUMrMEx2UXZ0QzZJRFV3MFlVMU1OR0ZOU0RSZ2RHQzBMRFF1OUdNSURNOGRUNDhYQzkxUGp4MVBqeGNMM1UrUEZ3dmNENWNjbHh1UEZ3dmRHUStYSEpjYmp4MFpDQnpkSGxzWlQxY0luQmhaR1JwYm1jNk1HTnRJREJqYlNBd1kyMGdNR050TzJobGFXZG9kRG94TlM0d2NIUmNJajVjY2x4dVBIQWdZMnhoYzNNOVhDSk5jMjlPYjNKdFlXeGNJaUJoYkdsbmJqMWNJbU5sYm5SbGNsd2lJSE4wZVd4bFBWd2lkR1Y0ZEMxaGJHbG5ianBqWlc1MFpYSmNJajdRdXRDelBIVStQRnd2ZFQ0OGRUNDhYQzkxUGp4Y0wzQStYSEpjYmp4Y0wzUmtQbHh5WEc0OGRHUWdjM1I1YkdVOVhDSndZV1JrYVc1bk9qQmpiU0F3WTIwZ01HTnRJREJqYlR0b1pXbG5hSFE2TVRVdU1IQjBYQ0krWEhKY2JqeHdJR05zWVhOelBWd2lUWE52VG05eWJXRnNYQ0lnWVd4cFoyNDlYQ0pqWlc1MFpYSmNJaUJ6ZEhsc1pUMWNJblJsZUhRdFlXeHBaMjQ2WTJWdWRHVnlYQ0krTlRBd1BIVStQRnd2ZFQ0OGRUNDhYQzkxUGp4Y0wzQStYSEpjYmp4Y0wzUmtQbHh5WEc0OFhDOTBjajVjY2x4dVBIUnlJSE4wZVd4bFBWd2lhR1ZwWjJoME9qRTFMakJ3ZEZ3aVBseHlYRzQ4ZEdRZ2MzUjViR1U5WENKd1lXUmthVzVuT2pCamJTQXdZMjBnTUdOdElEQmpiVHRvWldsbmFIUTZNVFV1TUhCMFhDSStQRnd2ZEdRK1hISmNiangwWkNCemRIbHNaVDFjSW5CaFpHUnBibWM2TUdOdElEQmpiU0F3WTIwZ01HTnRPMmhsYVdkb2REb3hOUzR3Y0hSY0lqNDhYQzkwWkQ1Y2NseHVQSFJrSUhOMGVXeGxQVndpY0dGa1pHbHVaem93WTIwZ01HTnRJREJqYlNBd1kyMDdhR1ZwWjJoME9qRTFMakJ3ZEZ3aVBqeGNMM1JrUGx4eVhHNDhYQzkwY2o1Y2NseHVQSFJ5SUhOMGVXeGxQVndpYUdWcFoyaDBPakUxTGpCd2RGd2lQbHh5WEc0OGRHUWdjM1I1YkdVOVhDSndZV1JrYVc1bk9qQmpiU0F3WTIwZ01HTnRJREJqYlR0b1pXbG5hSFE2TVRVdU1IQjBYQ0krWEhKY2JqeHdJR05zWVhOelBWd2lUWE52VG05eWJXRnNYQ0krMEovUmdOQyswTExRdnRDNzBMN1F1dEN3SU5DUzBZQXRNU3dnMFlRMUxDRFFzZEdEMEwzUmd0R0xMQ0RRazlDZTBLSFFvaUEyTnpJM0xUZ3dQSFUrUEZ3dmRUNDhkVDQ4WEM5MVBqeGNMM0ErWEhKY2JqeGNMM1JrUGx4eVhHNDhkR1FnYzNSNWJHVTlYQ0p3WVdSa2FXNW5PakJqYlNBd1kyMGdNR050SURCamJUdG9aV2xuYUhRNk1UVXVNSEIwWENJK1hISmNianh3SUdOc1lYTnpQVndpVFhOdlRtOXliV0ZzWENJZ1lXeHBaMjQ5WENKalpXNTBaWEpjSWlCemRIbHNaVDFjSW5SbGVIUXRZV3hwWjI0NlkyVnVkR1Z5WENJKzBMSFJnOUdGMFlMUXNEeDFQanhjTDNVK1BIVStQRnd2ZFQ0OFhDOXdQbHh5WEc0OFhDOTBaRDVjY2x4dVBIUmtJSE4wZVd4bFBWd2ljR0ZrWkdsdVp6b3dZMjBnTUdOdElEQmpiU0F3WTIwN2FHVnBaMmgwT2pFMUxqQndkRndpUGx4eVhHNDhjQ0JqYkdGemN6MWNJazF6YjA1dmNtMWhiRndpSUdGc2FXZHVQVndpWTJWdWRHVnlYQ0lnYzNSNWJHVTlYQ0owWlhoMExXRnNhV2R1T21ObGJuUmxjbHdpUGpFOGRUNDhYQzkxUGp4MVBqeGNMM1UrUEZ3dmNENWNjbHh1UEZ3dmRHUStYSEpjYmp4Y0wzUnlQbHh5WEc0OGRISWdjM1I1YkdVOVhDSm9aV2xuYUhRNk1UVXVNSEIwWENJK1hISmNiangwWkNCemRIbHNaVDFjSW5CaFpHUnBibWM2TUdOdElEQmpiU0F3WTIwZ01HTnRPMmhsYVdkb2REb3hOUzR3Y0hSY0lqNDhYQzkwWkQ1Y2NseHVQSFJrSUhOMGVXeGxQVndpY0dGa1pHbHVaem93WTIwZ01HTnRJREJqYlNBd1kyMDdhR1ZwWjJoME9qRTFMakJ3ZEZ3aVBqeGNMM1JrUGx4eVhHNDhkR1FnYzNSNWJHVTlYQ0p3WVdSa2FXNW5PakJqYlNBd1kyMGdNR050SURCamJUdG9aV2xuYUhRNk1UVXVNSEIwWENJK1BGd3ZkR1ErWEhKY2JqeGNMM1J5UGx4eVhHNDhkSElnYzNSNWJHVTlYQ0pvWldsbmFIUTZNVFV1TUhCMFhDSStYSEpjYmp4MFpDQnpkSGxzWlQxY0luQmhaR1JwYm1jNk1HTnRJREJqYlNBd1kyMGdNR050TzJobGFXZG9kRG94TlM0d2NIUmNJajVjY2x4dVBIQWdZMnhoYzNNOVhDSk5jMjlPYjNKdFlXeGNJajdRdjlDKzBMdlF2dEdCMExBZ05OR0ZOREFnMFlIUmd0Q3cwTHZSakNBelBIVStQRnd2ZFQ0OGRUNDhYQzkxUGp4Y0wzQStYSEpjYmp4Y0wzUmtQbHh5WEc0OGRHUWdjM1I1YkdVOVhDSndZV1JrYVc1bk9qQmpiU0F3WTIwZ01HTnRJREJqYlR0b1pXbG5hSFE2TVRVdU1IQjBYQ0krWEhKY2JqeHdJR05zWVhOelBWd2lUWE52VG05eWJXRnNYQ0lnWVd4cFoyNDlYQ0pqWlc1MFpYSmNJaUJ6ZEhsc1pUMWNJblJsZUhRdFlXeHBaMjQ2WTJWdWRHVnlYQ0krMExyUXN6eDFQanhjTDNVK1BIVStQRnd2ZFQ0OFhDOXdQbHh5WEc0OFhDOTBaRDVjY2x4dVBIUmtJSE4wZVd4bFBWd2ljR0ZrWkdsdVp6b3dZMjBnTUdOdElEQmpiU0F3WTIwN2FHVnBaMmgwT2pFMUxqQndkRndpUGx4eVhHNDhjQ0JqYkdGemN6MWNJazF6YjA1dmNtMWhiRndpSUdGc2FXZHVQVndpWTJWdWRHVnlYQ0lnYzNSNWJHVTlYQ0owWlhoMExXRnNhV2R1T21ObGJuUmxjbHdpUGpJd01EeDFQanhjTDNVK1BIVStQRnd2ZFQ0OFhDOXdQbHh5WEc0OFhDOTBaRDVjY2x4dVBGd3ZkSEkrWEhKY2JqeGNMM1JpYjJSNVBseHlYRzQ4WEM5MFlXSnNaVDVjY2x4dVBIQWdZMnhoYzNNOVhDSk5jMjlPYjNKdFlXeGNJaUJ6ZEhsc1pUMWNJbTFoY21kcGJpMWliM1IwYjIwNk1USXVNSEIwWENJK1BHSnlQbHh5WEc0OFluSStYSEpjYmp4aWNqNWNjbHh1UEdKeVBseHlYRzQ4ZFQ0OFhDOTFQangxUGp4Y0wzVStQRnd2Y0Q1Y2NseHVQSEJ5WlQ0dExTQThkVDQ4WEM5MVBqeDFQanhjTDNVK1BGd3ZjSEpsUGx4eVhHNDhjSEpsUHRDaElOR0QwTExRc05DMjBMWFF2ZEM0MExYUXZDdzhkVDQ4WEM5MVBqeDFQanhjTDNVK1BGd3ZjSEpsUGx4eVhHNDhjSEpsUHRDUTBMdlF0ZEM2MFlIUXNOQzkwTFRSZ0R4MVBqeGNMM1UrUEhVK1BGd3ZkVDQ4WEM5d2NtVStYSEpjYmp4d2NtVSswSjdRbnRDZUlDWnhkVzkwTzlDYjBMN1FzOUM0MEwzUXY5R0EwTDdRdkNaeGRXOTBPeUFvMExNdUlOQ2kwTERRczlDdzBMM1JnTkMrMExNcFBIVStQRnd2ZFQ0OGRUNDhYQzkxUGp4Y0wzQnlaVDVjY2x4dVBIQnlaVDdSZ3RDMTBMc3VPaUFyTnpnMk16UXpOREEyTWpBOGRUNDhYQzkxUGp4MVBqeGNMM1UrUEZ3dmNISmxQbHh5WEc0OGNISmxQanhoSUdoeVpXWTlYQ0p0WVdsc2RHODZjR3hoYUc5MGJtbHJiM1pBYkc5bmFXNXdjbTl0TG5KMVhDSWdkR0Z5WjJWMFBWd2lYMkpzWVc1clhDSStjR3hoYUc5MGJtbHJiM1pBYkc5bmFXNXdjbTl0TG5KMVBGd3ZZVDQ4ZFQ0OFhDOTFQangxUGp4Y0wzVStQRnd2Y0hKbFBseHlYRzQ4WEM5a2FYWStYSEpjYmp4d1BqeHpjR0Z1SUhOMGVXeGxQVndpWm05dWRDMXphWHBsT2prdU1IQjBPMlp2Ym5RdFptRnRhV3g1T2laeGRXOTBPMEZ5YVdGc0puRjFiM1E3TEhOaGJuTXRjMlZ5YVdZN1kyOXNiM0k2SXpOaE56VmpORndpUHRDajBMTFFzTkMyMExEUXRkQzgwWXZRdFNEUXV0QyswTHZRdTlDMTBMUFF1Q0RRdUNEUXY5Q3cwWURSZ3RDOTBMWFJnTkdMTER4MVBqeGNMM1UrUEhVK1BGd3ZkVDQ4WEM5emNHRnVQanhjTDNBK1hISmNianh3UGp4emNHRnVJSE4wZVd4bFBWd2labTl1ZEMxemFYcGxPamt1TUhCME8yWnZiblF0Wm1GdGFXeDVPaVp4ZFc5ME8wRnlhV0ZzSm5GMWIzUTdMSE5oYm5NdGMyVnlhV1k3WTI5c2IzSTZJek5oTnpWak5Gd2lQdENkMExEUmlOQ3dJTkNhMEw3UXZOQy8wTERRdmRDNDBZOGcwTC9SZ05DNDBMVFF0ZEdBMExiUXVOQ3kwTERRdGRHQzBZSFJqeURSamRHQzBMalJoOUMxMFlIUXV0QzQwWVVnMEwvUmdOQzQwTDNSaHRDNDBML1F2dEN5SU5DeTBMWFF0TkMxMEwzUXVOR1BJTkN4MExqUXQ5QzkwTFhSZ2RDd0lOQzRJTkMwMExYUXU5Q3cwTFhSZ2lEUXN0R0IwTFVnMExUUXU5R1BJTkdDMEw3UXM5QytMQ0RSaDlHQzBMN1FzZEdMSU5DeTBMZlFzTkM0MEx6UXZ0QyswWUxRdmRDKzBZalF0ZEM5MExqUmp5RFJnU0RRdmRDdzBZalF1TkM4MExnZzBML1FzTkdBMFlMUXZkQzEwWURRc05DODBMZ2cwWUhSZ3RHQTBMN1F1TkM3MExqUmdkR01JTkM5MExBZzBML1JnTkM0MEwzUmh0QzQwTC9Rc05HRklOQyswWUxRdXRHQTBZdlJndEMrMFlIUmd0QzRJTkM0SU5DLzBZRFF2dEMzMFlEUXNOR0gwTDNRdnRHQjBZTFF1QzVjY2x4dUlOQ2YwTDdSamRHQzBMN1F2TkdESU5DLzBZRFF2dEdCMExqUXZDRFFrdEN3MFlFZzBZSFF2dEMrMExIUmlkQ3cwWUxSakNEUXZkQ3cwTHdnMEw3UXNkQytJTkN5MFlIUXRkR0ZJTkM5MExYUXM5Q3cwWUxRdU5DeTBMM1JpOUdGSU5HRTBMRFF1dEdDMExEUmhTRFFzdEMrSU5DeTBMZlFzTkM0MEx6UXZ0QyswWUxRdmRDKzBZalF0ZEM5MExqUmo5R0ZJTkdCSU5DOTBMRFJpTkMxMExrZzBMclF2dEM4MEwvUXNOQzkwTGpRdGRDNUlOQy8wTDRnMExEUXROR0EwTFhSZ2RHRFhISmNianhoSUdoeVpXWTlYQ0p0WVdsc2RHODZaRzkyWlhKcFpVQnpZMjB1Y25WY0lpQjBZWEpuWlhROVhDSmZZbXhoYm10Y0lqNDhjM0JoYmlCemRIbHNaVDFjSW1OdmJHOXlPaU16WVRjMVl6UmNJajVrYjNabGNtbGxRSE5qYlM1eWRUeGNMM053WVc0K1BGd3ZZVDR1SU5DUzBZSFJqeURRdU5DOTBZVFF2dEdBMEx6UXNOR0cwTGpSanlEUXY5QyswWUhSZ3RHRDBML1FzTkMxMFlJZzBMSWcwTDNRdGRDMzBMRFFzdEM0MFlIUXVOQzgwWVBSamlEUmdkQzcwWVBRdHRDeDBZTWcwTExRdmRHRDBZTFJnTkMxMEwzUXZkQzEwTFBRdmlEUXNOR0QwTFRRdU5HQzBMQXVQSFUrUEZ3dmRUNDhkVDQ4WEM5MVBqeGNMM053WVc0K1BGd3ZjRDVjY2x4dVBIQStQSE53WVc0Z2MzUjViR1U5WENKbWIyNTBMWE5wZW1VNk9TNHdjSFE3Wm05dWRDMW1ZVzFwYkhrNkpuRjFiM1E3UVhKcFlXd21jWFZ2ZERzc2MyRnVjeTF6WlhKcFpqdGpiMnh2Y2pvak0yRTNOV00wWENJKzBKL1JnTkMxMFlMUXRkQzkwTGZRdU5DNElOQy8wTDRnMExyUXNOR0gwTFhSZ2RHQzBMTFJneURRdnRDeDBZSFF1OUdEMExiUXVOQ3kwTERRdmRDNDBZOGcwTGpRdTlDNElOR0MwTDdRc3RDdzBZRFFzQ0RRdjlHQTBMalF2ZEM0MEx6UXNOR08wWUxSZ2RHUElOQzkwTEFnMFlMUXRkQzcwTFhSaE5DKzBMMGcwTFBRdnRHQTBZL1JoOUMxMExrZzBMdlF1TkM5MExqUXVGeHlYRzQ4ZFQ0NExUZ3dNQzAzTURBd0xURXlNenhjTDNVK0xpRFFsOUN5MEw3UXZkQzYwTGdnMEwvUXZpRFFvTkMrMFlIUmdkQzQwTGdnMExIUXRkR0IwTC9RdTlDdzBZTFF2ZEMrUEhVK1BGd3ZkVDQ4ZFQ0OFhDOTFQanhjTDNOd1lXNCtQRnd2Y0Q1Y2NseHVQSEFnWTJ4aGMzTTlYQ0pOYzI5T2IzSnRZV3hjSWlCemRIbHNaVDFjSW0xaGNtZHBiaTFpYjNSMGIyMDZNVEl1TUhCMFhDSStQSFUrUEZ3dmRUN0NvRHgxUGp4Y0wzVStQRnd2Y0Q1Y2NseHVQSEJ5WlQ0dExTQThkVDQ4WEM5MVBqeDFQanhjTDNVK1BGd3ZjSEpsUGx4eVhHNDhjSEpsUHRDaElOR0QwTExRc05DMjBMWFF2ZEM0MExYUXZDdzhkVDQ4WEM5MVBqeDFQanhjTDNVK1BGd3ZjSEpsUGx4eVhHNDhjSEpsUHRDUTBMdlF0ZEM2MFlIUXNOQzkwTFRSZ0R4MVBqeGNMM1UrUEhVK1BGd3ZkVDQ4WEM5d2NtVStYSEpjYmp4d2NtVSswSjdRbnRDZUlDWnhkVzkwTzlDYjBMN1FzOUM0MEwzUXY5R0EwTDdRdkNaeGRXOTBPeUFvMExNdUlOQ2kwTERRczlDdzBMM1JnTkMrMExNcFBIVStQRnd2ZFQ0OGRUNDhYQzkxUGp4Y0wzQnlaVDVjY2x4dVBIQnlaVDdSZ3RDMTBMc3VPaUFyTnpnMk16UXpOREEyTWpBOGRUNDhYQzkxUGp4MVBqeGNMM1UrUEZ3dmNISmxQbHh5WEc0OGNISmxQanhoSUdoeVpXWTlYQ0p0WVdsc2RHODZjR3hoYUc5MGJtbHJiM1pBYkc5bmFXNXdjbTl0TG5KMVhDSWdkR0Z5WjJWMFBWd2lYMkpzWVc1clhDSStjR3hoYUc5MGJtbHJiM1pBYkc5bmFXNXdjbTl0TG5KMVBGd3ZZVDQ4ZFQ0OFhDOTFQangxUGp4Y0wzVStQRnd2Y0hKbFBseHlYRzQ4WEM5a2FYWStYSEpjYmp4Y0wyUnBkajVjY2x4dVhISmNianhjTDJScGRqNDhYQzlrYVhZK1BGd3ZaR2wyUGx4eVhHNGlmUT09')
    # order_rec.save_truth_test(content="{'req_number': '187ca897-4b2c-4b07-aa75-4f0d9dff8fc5', 'mail_code': '0057653611', 'user': 'SHARIPOVDI', 'positions': [{'position_id': '4', 'true_material': '000000000000083739', 'true_ei': 'ШТ', 'true_value': '15.000', 'spec_mat': ''}]}".replace("'", '"'))