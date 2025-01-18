import xml.etree.ElementTree as ET
import re
import os
import asyncio
import aio_pika
import base64
import json
from distance import Find_materials
from functools import partial
from hash2text import text_from_hash
from order_recognition.confs import config as conf
from order_recognition.utils import logger
from order_recognition.core.yandexgpt import custom_yandex_gpt
from order_recognition.utils import data_text_processing as dp
from thread import Thread


class Order_recognition():

    def __init__(self):
        self.find_mats = Find_materials()

    def consumer_test(self, hash:str=None, content:str=None):
        if content is None:
            content = text_from_hash(hash)
        print('Text - ', content.split('\n'), flush=True)
        # self.test_analize_email(content)
        ygpt = custom_yandex_gpt()
        my_thread = Thread(target=self.test_analize_email, args=[ygpt, content])
        my_thread.start()
        # self.test_analize_email(ygpt, content)

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
                    self.find_mats.models.fit(request_text, true_first, true_zero)
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
            self.find_mats.method2.to_csv('data/method2.csv', index=False)
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
                self.find_mats.method2.to_csv('data/method2.csv', index=False)
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
    order_rec = Order_recognition()
    print("ХЭШ:", conf.connection_url, "|")
    if conf.connection_url == "":
        hash = "ZXlKaWRXTnJaWFJPWVcxbElqb2lZM0p0TFdWdFlXbHNJaXdpYjJKcVpXTjBUbUZ0WlNJNkltMXpaMTloTkRrMVpXTTVPVFExWkRjd04yWTBNV1ZoTm1FNU56VTRNbVZtTmpoaVppSXNJbVpwYkdWRGIyNTBaVzUwSWpvaVhHNDhTRlJOVEQ0OFFrOUVXVDQ4WkdsMlB0Q1UwTDdRc2RHQTBZdlF1U0RRdE5DMTBMM1JqQ3dnMEsvUXZkQ3dMQ0RRc3RHTDBZSFJndEN3MExMUmpOR0MwTFVnMFlIUmg5QzEwWUlnMEwzUXNDRFF0TkN3MEwzUXZkR0wwTFVnMEwvUXZ0QzMwTGpSaHRDNDBMZzZQRnd2WkdsMlBqeGthWFkrSm01aWMzQTdQRnd2WkdsMlBqeGthWFkrMEtMUmdOR0QwTEhRc0NEUXV0Q3kwTERRdE5HQUxpQTJNTkdGTmpEUmhUSWcwWUhSZ2k0Z015RFFrOUNlMEtIUW9pQTROak01TFRneUlFdzlOdEM4SUZ4MU1qQXhOQ1p1WW5Od096UXdJTkdJMFlJOFhDOWthWFkrUEdScGRqN1FvdEdBMFlQUXNkQ3dJTkM2MExMUXNOQzAwWUF1SURRdzBZVTBNTkdGTWlEUmdkR0NMaUF6SU5DVDBKN1FvZENpSURnMk16a3RPRElnVEQwMjBMd2dYSFV5TURFMEptNWljM0E3TVRnZzBZalJnanhjTDJScGRqNDhaR2wyUHRDaTBZRFJnOUN4MExBZzBML1JnTkdQMEx3dUlEVXcwWVV6TU5HRk1pRFJnZEdDTGlBeklOQ1QwSjdRb2RDaUlEZzJNemt0T0RJZ1REMDIwTHdnWEhVeU1ERTBKbTVpYzNBN05DRFJpTkdDUEZ3dlpHbDJQanhrYVhZKzBLTFJnTkdEMExIUXNDRFF1dEN5MExEUXROR0FMaUF6TU5HRk16RFJoVElnMFlIUmdpNGdNeURRazlDZTBLSFFvaUE0TmpNNUxUZ3lJRXc5TnRDOElGeDFNakF4TkNadVluTndPelFtYm1KemNEdlJpTkdDUEZ3dlpHbDJQanhrYVhZK0ptNWljM0E3UEZ3dlpHbDJQanhrYVhZZ1pHRjBZUzF6YVdkdVlYUjFjbVV0ZDJsa1oyVjBQVndpWTI5dWRHRnBibVZ5WENJK1BHUnBkaUJrWVhSaExYTnBaMjVoZEhWeVpTMTNhV1JuWlhROVhDSmpiMjUwWlc1MFhDSStQR1JwZGo0dExUeGthWFlnYzNSNWJHVTlYQ0owWlhoMExXRnNhV2R1T25OMFlYSjBYQ0krUEhOd1lXNGdjM1I1YkdVOVhDSm1iMjUwTFhOcGVtVTZNVGh3ZUR0c2FXNWxMV2hsYVdkb2REb3lPSEI0TzF3aVBqeHpjR0Z1SUhOMGVXeGxQVndpWTI5c2IzSTZJekpqTW1ReVpWd2lQanh6Y0dGdUlITjBlV3hsUFZ3aVptOXVkQzFtWVcxcGJIazZRWEpwWVd3c0lGUmhhRzl0WVN3Z1ZtVnlaR0Z1WVN3Z2MyRnVjeTF6WlhKcFpsd2lQanh6Y0dGdUlITjBlV3hsUFZ3aVptOXVkQzF6ZEhsc1pUcHViM0p0WVd4Y0lqNDhjM0JoYmlCemRIbHNaVDFjSW1admJuUXRkbUZ5YVdGdWRDMXNhV2RoZEhWeVpYTTZibTl5YldGc1hDSStQSE53WVc0Z2MzUjViR1U5WENKbWIyNTBMWGRsYVdkb2REbzBNREJjSWo0OGMzQmhiaUJ6ZEhsc1pUMWNJbmRvYVhSbExYTndZV05sT201dmNtMWhiRndpUGp4emNHRnVJSE4wZVd4bFBWd2lkR1Y0ZEMxa1pXTnZjbUYwYVc5dUxYUm9hV05yYm1WemN6cHBibWwwYVdGc1hDSStQSE53WVc0Z2MzUjViR1U5WENKMFpYaDBMV1JsWTI5eVlYUnBiMjR0YzNSNWJHVTZhVzVwZEdsaGJGd2lQanh6Y0dGdUlITjBlV3hsUFZ3aWRHVjRkQzFrWldOdmNtRjBhVzl1TFdOdmJHOXlPbWx1YVhScFlXeGNJajQ4YzNCaGJpQnpkSGxzWlQxY0ltSmhZMnRuY205MWJtUXRZMjlzYjNJNkkyWm1abVptWmx3aVB0Q2hJTkdEMExMUXNOQzIwTFhRdmRDNDBMWFF2Q0RRdWlEUWt0Q3cwTHdzSU5DODBMWFF2ZEMxMExUUXR0QzEwWUFnMEw3Umd0QzAwTFhRdTlDd0lOQy8wWURRdnRDMDBMRFF0aURRazlDYUptNWljM0E3d3F2UW1OQzkwWUxRdGRHQTBZSFJndEM0MEx2UmdjSzdQRnd2YzNCaGJqNDhYQzl6Y0dGdVBqeGNMM053WVc0K1BGd3ZjM0JoYmo0OFhDOXpjR0Z1UGp4Y0wzTndZVzQrUEZ3dmMzQmhiajQ4WEM5emNHRnVQanhjTDNOd1lXNCtQRnd2YzNCaGJqNDhYQzl6Y0dGdVBqeGthWFlnYzNSNWJHVTlYQ0owWlhoMExXRnNhV2R1T25OMFlYSjBYQ0krUEhOd1lXNGdjM1I1YkdVOVhDSm1iMjUwTFhOcGVtVTZNVGh3ZUR0c2FXNWxMV2hsYVdkb2REb3lPSEI0TzF3aVBqeG1iMjUwSUdaaFkyVTlYQ0pCY21saGJDd2dWR0ZvYjIxaExDQldaWEprWVc1aExDQnpZVzV6TFhObGNtbG1YQ0lnWTI5c2IzSTlYQ0lqTW1NeVpESmxYQ0krUEdJKzBLSFF1TkM4MEw3UXZkQyswTElnMEp6UXVOR0EwTDdSZ2RDNzBMRFFzaURRa05DNzBMWFF1dEdCMExYUXRkQ3kwTGpSaHp4Y0wySStQRnd2Wm05dWRENDhYQzl6Y0dGdVBqeGNMMlJwZGo0OFpHbDJJSE4wZVd4bFBWd2lkR1Y0ZEMxaGJHbG5ianB6ZEdGeWRGd2lQanhrYVhZZ2MzUjViR1U5WENKMFpYaDBMV0ZzYVdkdU9uTjBZWEowWENJK1BHUnBkajQ4YzNCaGJpQnpkSGxzWlQxY0ltWnZiblF0YzJsNlpUb3hPSEI0TzJ4cGJtVXRhR1ZwWjJoME9qSTRjSGc3WENJK1BITndZVzRnYzNSNWJHVTlYQ0pqYjJ4dmNqb2pNbU15WkRKbFhDSStQSE53WVc0Z2MzUjViR1U5WENKbWIyNTBMV1poYldsc2VUcEJjbWxoYkN3Z1ZHRm9iMjFoTENCV1pYSmtZVzVoTENCellXNXpMWE5sY21sbVhDSStQSE53WVc0Z2MzUjViR1U5WENKbWIyNTBMWE4wZVd4bE9tNXZjbTFoYkZ3aVBqeHpjR0Z1SUhOMGVXeGxQVndpWm05dWRDMTJZWEpwWVc1MExXeHBaMkYwZFhKbGN6cHViM0p0WVd4Y0lqNDhjM0JoYmlCemRIbHNaVDFjSW1admJuUXRkMlZwWjJoME9qUXdNRndpUGp4emNHRnVJSE4wZVd4bFBWd2lkMmhwZEdVdGMzQmhZMlU2Ym05eWJXRnNYQ0krUEhOd1lXNGdjM1I1YkdVOVhDSjBaWGgwTFdSbFkyOXlZWFJwYjI0dGRHaHBZMnR1WlhOek9tbHVhWFJwWVd4Y0lqNDhjM0JoYmlCemRIbHNaVDFjSW5SbGVIUXRaR1ZqYjNKaGRHbHZiaTF6ZEhsc1pUcHBibWwwYVdGc1hDSStQSE53WVc0Z2MzUjViR1U5WENKMFpYaDBMV1JsWTI5eVlYUnBiMjR0WTI5c2IzSTZhVzVwZEdsaGJGd2lQanh6Y0dGdUlITjBlV3hsUFZ3aVltRmphMmR5YjNWdVpDMWpiMnh2Y2pvalptWm1abVptWENJK1BITndZVzRnYzNSNWJHVTlYQ0pqYjJ4dmNqb2pNbU15WkRKbFhDSStQSE53WVc0Z2MzUjViR1U5WENKbWIyNTBMV1poYldsc2VUcEJjbWxoYkN3Z1ZHRm9iMjFoTENCV1pYSmtZVzVoTENCellXNXpMWE5sY21sbVhDSStQSE53WVc0Z2MzUjViR1U5WENKbWIyNTBMWE4wZVd4bE9tNXZjbTFoYkZ3aVBqeHpjR0Z1SUhOMGVXeGxQVndpWm05dWRDMTJZWEpwWVc1MExXeHBaMkYwZFhKbGN6cHViM0p0WVd4Y0lqNDhjM0JoYmlCemRIbHNaVDFjSW1admJuUXRkMlZwWjJoME9qUXdNRndpUGp4emNHRnVJSE4wZVd4bFBWd2lkMmhwZEdVdGMzQmhZMlU2Ym05eWJXRnNYQ0krUEhOd1lXNGdjM1I1YkdVOVhDSmlZV05yWjNKdmRXNWtMV052Ykc5eU9pTm1abVptWm1aY0lqNDhjM0JoYmlCemRIbHNaVDFjSW5SbGVIUXRaR1ZqYjNKaGRHbHZiaTEwYUdsamEyNWxjM002YVc1cGRHbGhiRndpUGp4emNHRnVJSE4wZVd4bFBWd2lkR1Y0ZEMxa1pXTnZjbUYwYVc5dUxYTjBlV3hsT21sdWFYUnBZV3hjSWo0OGMzQmhiaUJ6ZEhsc1pUMWNJblJsZUhRdFpHVmpiM0poZEdsdmJpMWpiMnh2Y2pwcGJtbDBhV0ZzWENJK1BITndZVzRnYzNSNWJHVTlYQ0ppWVdOclozSnZkVzVrTFdOdmJHOXlPaU5tWm1abVptWmNJajQ4YzNCaGJpQnpkSGxzWlQxY0ltWnZiblF0YzNSNWJHVTZibTl5YldGc1hDSStQSE53WVc0Z2MzUjViR1U5WENKbWIyNTBMWFpoY21saGJuUXRiR2xuWVhSMWNtVnpPbTV2Y20xaGJGd2lQanh6Y0dGdUlITjBlV3hsUFZ3aVptOXVkQzEzWldsbmFIUTZOREF3WENJK1BITndZVzRnYzNSNWJHVTlYQ0owWlhoMExXUmxZMjl5WVhScGIyNHRZMjlzYjNJNmFXNXBkR2xoYkZ3aVBqeHpjR0Z1SUhOMGVXeGxQVndpZEdWNGRDMWtaV052Y21GMGFXOXVMWE4wZVd4bE9tbHVhWFJwWVd4Y0lqNDhjM0JoYmlCemRIbHNaVDFjSW5SbGVIUXRaR1ZqYjNKaGRHbHZiaTEwYUdsamEyNWxjM002YVc1cGRHbGhiRndpUGp4emNHRnVJSE4wZVd4bFBWd2lZbTk0TFhOcGVtbHVaenBwYm1obGNtbDBYQ0krUEdadmJuUWdabUZqWlQxY0lrRnlhV0ZzWENJK1BHWnZiblFnWTI5c2IzSTlYQ0lqTWpFeU1USXhYQ0krUEhOd1lXNGdjM1I1YkdVOVhDSjNhR2wwWlMxemNHRmpaVHB1YjNkeVlYQmNJajdRb3RDMTBMdlF0ZEdFMEw3UXZUb21ibUp6Y0RzOGMzQmhiajQ4YzNCaGJpQmpiR0Z6Y3oxY0ltcHpMWEJvYjI1bExXNTFiV0psY2x3aVBpczNJRGt3TWlBNU5ETWdOekl3T0R4Y0wzTndZVzQrUEZ3dmMzQmhiajQ4WEM5emNHRnVQanhjTDJadmJuUStQRnd2Wm05dWRENDhYQzl6Y0dGdVBqeGNMM053WVc0K1BGd3ZjM0JoYmo0OFhDOXpjR0Z1UGp4Y0wzTndZVzQrUEZ3dmMzQmhiajQ4WEM5emNHRnVQanhjTDNOd1lXNCtQRnd2YzNCaGJqNDhYQzl6Y0dGdVBqeGNMM053WVc0K1BGd3ZjM0JoYmo0OFhDOXpjR0Z1UGp4Y0wzTndZVzQrUEZ3dmMzQmhiajQ4WEM5emNHRnVQanhjTDNOd1lXNCtQRnd2YzNCaGJqNDhYQzl6Y0dGdVBqeGNMM053WVc0K1BGd3ZjM0JoYmo0OFhDOXpjR0Z1UGp4Y0wzTndZVzQrUEZ3dmMzQmhiajQ4WEM5emNHRnVQanhjTDNOd1lXNCtQRnd2YzNCaGJqNDhYQzl6Y0dGdVBqeGNMM053WVc0K1BGd3ZaR2wyUGp4a2FYWStQSE53WVc0Z2MzUjViR1U5WENKbWIyNTBMWE5wZW1VNk1UaHdlRHRzYVc1bExXaGxhV2RvZERveU9IQjRPMXdpUGp4bWIyNTBJR1poWTJVOVhDSkJjbWxoYkZ3aUlHTnZiRzl5UFZ3aUl6SXhNakV5TVZ3aVBqeHpjR0Z1SUhOMGVXeGxQVndpZEdWNGRDMTNjbUZ3T2lCdWIzZHlZWEE3WENJK1YyaGhkSE5CY0hBNkptNWljM0E3UEhOd1lXNCtQSE53WVc0Z1kyeGhjM005WENKcWN5MXdhRzl1WlMxdWRXMWlaWEpjSWo0ck55QTVNRElnT1RReklEY3lNRGc4WEM5emNHRnVQanhjTDNOd1lXNCtQRnd2YzNCaGJqNDhYQzltYjI1MFBqeGNMM053WVc0K1BGd3ZaR2wyUGp4a2FYWStQSE53WVc0Z2MzUjViR1U5WENKbWIyNTBMWE5wZW1VNk1UaHdlRHRzYVc1bExXaGxhV2RvZERveU9IQjRPMXdpUGp4emNHRnVJSE4wZVd4bFBWd2labTl1ZEMxemRIbHNaVG9nYm05eWJXRnNPMXdpUGp4emNHRnVJSE4wZVd4bFBWd2labTl1ZEMxMllYSnBZVzUwTFd4cFoyRjBkWEpsY3pvZ2JtOXliV0ZzTzF3aVBqeHpjR0Z1SUhOMGVXeGxQVndpZDJocGRHVXRjM0JoWTJVdFkyOXNiR0Z3YzJVNklHTnZiR3hoY0hObE8xd2lQanh6Y0dGdUlITjBlV3hsUFZ3aWRHVjRkQzFrWldOdmNtRjBhVzl1TFhSb2FXTnJibVZ6Y3pvZ2FXNXBkR2xoYkR0Y0lqNDhjM0JoYmlCemRIbHNaVDFjSW5SbGVIUXRaR1ZqYjNKaGRHbHZiaTF6ZEhsc1pUb2dhVzVwZEdsaGJEdGNJajQ4YzNCaGJpQnpkSGxzWlQxY0luUmxlSFF0WkdWamIzSmhkR2x2YmkxamIyeHZjam9nYVc1cGRHbGhiRHRjSWo0OGMzQmhiaUJ6ZEhsc1pUMWNJbVp2Ym5RdGMzUjViR1U2SUc1dmNtMWhiRHRjSWo0OGMzQmhiaUJ6ZEhsc1pUMWNJbVp2Ym5RdGRtRnlhV0Z1ZEMxc2FXZGhkSFZ5WlhNNklHNXZjbTFoYkR0Y0lqNDhjM0JoYmlCemRIbHNaVDFjSW5kb2FYUmxMWE53WVdObExXTnZiR3hoY0hObE9pQmpiMnhzWVhCelpUdGNJajQ4YzNCaGJpQnpkSGxzWlQxY0luUmxlSFF0WkdWamIzSmhkR2x2YmkxMGFHbGphMjVsYzNNNklHbHVhWFJwWVd3N1hDSStQSE53WVc0Z2MzUjViR1U5WENKMFpYaDBMV1JsWTI5eVlYUnBiMjR0YzNSNWJHVTZJR2x1YVhScFlXdzdYQ0krUEhOd1lXNGdjM1I1YkdVOVhDSjBaWGgwTFdSbFkyOXlZWFJwYjI0dFkyOXNiM0k2SUdsdWFYUnBZV3c3WENJK1BITndZVzRnYzNSNWJHVTlYQ0ptYjI1MExYTjBlV3hsT2lCdWIzSnRZV3c3WENJK1BITndZVzRnYzNSNWJHVTlYQ0ptYjI1MExYWmhjbWxoYm5RdGJHbG5ZWFIxY21Wek9pQnViM0p0WVd3N1hDSStQSE53WVc0Z2MzUjViR1U5WENKMFpYaDBMV1JsWTI5eVlYUnBiMjR0WTI5c2IzSTZJR2x1YVhScFlXdzdYQ0krUEhOd1lXNGdjM1I1YkdVOVhDSjBaWGgwTFdSbFkyOXlZWFJwYjI0dGMzUjViR1U2SUdsdWFYUnBZV3c3WENJK1BITndZVzRnYzNSNWJHVTlYQ0owWlhoMExXUmxZMjl5WVhScGIyNHRkR2hwWTJ0dVpYTnpPaUJwYm1sMGFXRnNPMXdpUGp4emNHRnVJSE4wZVd4bFBWd2lZbTk0TFhOcGVtbHVaem9nYVc1b1pYSnBkRHRjSWo0OGMzQmhiaUJ6ZEhsc1pUMWNJbU52Ykc5eU9pQnlaMklvTkRRc0lEUTFMQ0EwTmlrN1ptOXVkQzFtWVcxcGJIazZJRUZ5YVdGc0xDQlVZV2h2YldFc0lGWmxjbVJoYm1Fc0lITmhibk10YzJWeWFXWTdabTl1ZEMxM1pXbG5hSFE2SURRd01EdDNhR2wwWlMxemNHRmpaVG9nYm05M2NtRndPMkpoWTJ0bmNtOTFibVF0WTI5c2IzSTZJSEpuWWlneU5UVXNJREkxTlN3Z01qVTFLVHRjSWo3UW90QzEwTHZRdGRDejBZRFFzTkM4MEx3NkptNWljM0E3UEZ3dmMzQmhiajQ4WEM5emNHRnVQanhjTDNOd1lXNCtQRnd2YzNCaGJqNDhYQzl6Y0dGdVBqeGNMM053WVc0K1BGd3ZjM0JoYmo0OFhDOXpjR0Z1UGp4Y0wzTndZVzQrUEZ3dmMzQmhiajQ4WEM5emNHRnVQanhjTDNOd1lXNCtQRnd2YzNCaGJqNDhYQzl6Y0dGdVBqeGNMM053WVc0K1BGd3ZjM0JoYmo0OFhDOXpjR0Z1UGp4Y0wzTndZVzQrUEZ3dmMzQmhiajQ4WVNCb2NtVm1QVndpYUhSMGNITTZMeTkwTG0xbEwxTkpUVTlPVDFaZlNWTlVSVVZNVTF3aVBtaDBkSEJ6T2k4dmRDNXRaUzlUU1UxUFRrOVdYMGxUVkVWRlRGTThYQzloUGp4Y0wzTndZVzQrUEZ3dlpHbDJQanhjTDJScGRqNDhYQzlrYVhZK1BHUnBkajQ4YzNCaGJpQnpkSGxzWlQxY0ltWnZiblF0YzJsNlpUb3hPSEI0TzJ4cGJtVXRhR1ZwWjJoME9qSTRjSGc3WENJK1BITndZVzRnYzNSNWJHVTlYQ0pqYjJ4dmNqb2pNbU15WkRKbFhDSStQSE53WVc0Z2MzUjViR1U5WENKbWIyNTBMV1poYldsc2VUcEJjbWxoYkN3Z1ZHRm9iMjFoTENCV1pYSmtZVzVoTENCellXNXpMWE5sY21sbVhDSStQSE53WVc0Z2MzUjViR1U5WENKbWIyNTBMWE4wZVd4bE9tNXZjbTFoYkZ3aVBqeHpjR0Z1SUhOMGVXeGxQVndpWm05dWRDMTJZWEpwWVc1MExXeHBaMkYwZFhKbGN6cHViM0p0WVd4Y0lqNDhjM0JoYmlCemRIbHNaVDFjSW1admJuUXRkMlZwWjJoME9qUXdNRndpUGp4emNHRnVJSE4wZVd4bFBWd2lkMmhwZEdVdGMzQmhZMlU2Ym05eWJXRnNYQ0krUEhOd1lXNGdjM1I1YkdVOVhDSjBaWGgwTFdSbFkyOXlZWFJwYjI0dGRHaHBZMnR1WlhOek9tbHVhWFJwWVd4Y0lqNDhjM0JoYmlCemRIbHNaVDFjSW5SbGVIUXRaR1ZqYjNKaGRHbHZiaTF6ZEhsc1pUcHBibWwwYVdGc1hDSStQSE53WVc0Z2MzUjViR1U5WENKMFpYaDBMV1JsWTI5eVlYUnBiMjR0WTI5c2IzSTZhVzVwZEdsaGJGd2lQanh6Y0dGdUlITjBlV3hsUFZ3aVltRmphMmR5YjNWdVpDMWpiMnh2Y2pvalptWm1abVptWENJKzBML1F2dEdIMFlMUXNEb21ibUp6Y0RzOFlTQnpkSGxzWlQxY0ltTnZiRzl5T25aaGNpZ3RMWFpyZFdrdExXTnZiRzl5WDNSbGVIUmZiR2x1YXlrN2RHVjRkQzFrWldOdmNtRjBhVzl1T25WdVpHVnliR2x1WlZ3aUlHaHlaV1k5WENKb2RIUndjem92TDJVdWJXRnBiQzV5ZFM5amIyMXdiM05sTHo5dFlXbHNkRzg5YldGcGJIUnZKVE5oYTNJeE1FQnBjM1JsWld4ekxuSjFYQ0krYTNJeE0wQnBjM1JsWld4ekxuSjFQRnd2WVQ0OFhDOXpjR0Z1UGp4Y0wzTndZVzQrUEZ3dmMzQmhiajQ4WEM5emNHRnVQanhjTDNOd1lXNCtQRnd2YzNCaGJqNDhYQzl6Y0dGdVBqeGNMM053WVc0K1BGd3ZjM0JoYmo0OFhDOXpjR0Z1UGp4Y0wzTndZVzQrUEZ3dlpHbDJQanhrYVhZK1BITndZVzRnYzNSNWJHVTlYQ0ptYjI1MExYTnBlbVU2TVRod2VEdHNhVzVsTFdobGFXZG9kRG95T0hCNE8xd2lQanh6Y0dGdUlITjBlV3hsUFZ3aVkyOXNiM0k2SXpKak1tUXlaVndpUGp4emNHRnVJSE4wZVd4bFBWd2labTl1ZEMxbVlXMXBiSGs2UVhKcFlXd3NJRlJoYUc5dFlTd2dWbVZ5WkdGdVlTd2djMkZ1Y3kxelpYSnBabHdpUGp4emNHRnVJSE4wZVd4bFBWd2labTl1ZEMxemRIbHNaVHB1YjNKdFlXeGNJajQ4YzNCaGJpQnpkSGxzWlQxY0ltWnZiblF0ZG1GeWFXRnVkQzFzYVdkaGRIVnlaWE02Ym05eWJXRnNYQ0krUEhOd1lXNGdjM1I1YkdVOVhDSm1iMjUwTFhkbGFXZG9kRG8wTURCY0lqNDhjM0JoYmlCemRIbHNaVDFjSW5kb2FYUmxMWE53WVdObE9tNXZjbTFoYkZ3aVBqeHpjR0Z1SUhOMGVXeGxQVndpZEdWNGRDMWtaV052Y21GMGFXOXVMWFJvYVdOcmJtVnpjenBwYm1sMGFXRnNYQ0krUEhOd1lXNGdjM1I1YkdVOVhDSjBaWGgwTFdSbFkyOXlZWFJwYjI0dGMzUjViR1U2YVc1cGRHbGhiRndpUGp4emNHRnVJSE4wZVd4bFBWd2lkR1Y0ZEMxa1pXTnZjbUYwYVc5dUxXTnZiRzl5T21sdWFYUnBZV3hjSWo0OGMzQmhiaUJ6ZEhsc1pUMWNJbUpoWTJ0bmNtOTFibVF0WTI5c2IzSTZJMlptWm1abVpsd2lQaVp1WW5Od096eGNMM053WVc0K1BGd3ZjM0JoYmo0OFhDOXpjR0Z1UGp4Y0wzTndZVzQrUEZ3dmMzQmhiajQ4WEM5emNHRnVQanhjTDNOd1lXNCtQRnd2YzNCaGJqNDhYQzl6Y0dGdVBqeGNMM053WVc0K1BGd3ZjM0JoYmo0OFhDOWthWFkrUEdScGRqNDhjM0JoYmlCemRIbHNaVDFjSW1admJuUXRjMmw2WlRveE9IQjRPMnhwYm1VdGFHVnBaMmgwT2pJNGNIZzdYQ0krUEhOd1lXNGdjM1I1YkdVOVhDSmpiMnh2Y2pvak1tTXlaREpsWENJK1BITndZVzRnYzNSNWJHVTlYQ0ptYjI1MExXWmhiV2xzZVRwQmNtbGhiQ3dnVkdGb2IyMWhMQ0JXWlhKa1lXNWhMQ0J6WVc1ekxYTmxjbWxtWENJK1BITndZVzRnYzNSNWJHVTlYQ0ptYjI1MExYTjBlV3hsT201dmNtMWhiRndpUGp4emNHRnVJSE4wZVd4bFBWd2labTl1ZEMxMllYSnBZVzUwTFd4cFoyRjBkWEpsY3pwdWIzSnRZV3hjSWo0OGMzQmhiaUJ6ZEhsc1pUMWNJbVp2Ym5RdGQyVnBaMmgwT2pRd01Gd2lQanh6Y0dGdUlITjBlV3hsUFZ3aWQyaHBkR1V0YzNCaFkyVTZibTl5YldGc1hDSStQSE53WVc0Z2MzUjViR1U5WENKMFpYaDBMV1JsWTI5eVlYUnBiMjR0ZEdocFkydHVaWE56T21sdWFYUnBZV3hjSWo0OGMzQmhiaUJ6ZEhsc1pUMWNJblJsZUhRdFpHVmpiM0poZEdsdmJpMXpkSGxzWlRwcGJtbDBhV0ZzWENJK1BITndZVzRnYzNSNWJHVTlYQ0owWlhoMExXUmxZMjl5WVhScGIyNHRZMjlzYjNJNmFXNXBkR2xoYkZ3aVBqeHpjR0Z1SUhOMGVXeGxQVndpWW1GamEyZHliM1Z1WkMxamIyeHZjam9qWm1abVptWm1YQ0krMEtEUXNOQ3gwTDdSZ3RDdzBMWFF2Q0RSZ1NEUWs5QyswWUhRdnRDeDBMN1JnTkMrMEwzUXQ5Q3cwTHJRc05DMzBMRFF2TkM0TGladVluTndPenhjTDNOd1lXNCtQRnd2YzNCaGJqNDhYQzl6Y0dGdVBqeGNMM053WVc0K1BGd3ZjM0JoYmo0OFhDOXpjR0Z1UGp4Y0wzTndZVzQrUEZ3dmMzQmhiajQ4WEM5emNHRnVQanhjTDNOd1lXNCtQRnd2YzNCaGJqNDhYQzlrYVhZK1BGd3ZaR2wyUGp4a2FYWWdjM1I1YkdVOVhDSjBaWGgwTFdGc2FXZHVPbk4wWVhKMFhDSStQSE53WVc0Z2MzUjViR1U5WENKbWIyNTBMWE5wZW1VNk1UaHdlRHRzYVc1bExXaGxhV2RvZERveU9IQjRPMXdpUGp4emNHRnVJSE4wZVd4bFBWd2lZMjlzYjNJNkl6SmpNbVF5WlZ3aVBqeHpjR0Z1SUhOMGVXeGxQVndpWm05dWRDMW1ZVzFwYkhrNlFYSnBZV3dzSUZSaGFHOXRZU3dnVm1WeVpHRnVZU3dnYzJGdWN5MXpaWEpwWmx3aVBqeHpjR0Z1SUhOMGVXeGxQVndpWm05dWRDMXpkSGxzWlRwdWIzSnRZV3hjSWo0OGMzQmhiaUJ6ZEhsc1pUMWNJbVp2Ym5RdGRtRnlhV0Z1ZEMxc2FXZGhkSFZ5WlhNNmJtOXliV0ZzWENJK1BITndZVzRnYzNSNWJHVTlYQ0ptYjI1MExYZGxhV2RvZERvME1EQmNJajQ4YzNCaGJpQnpkSGxzWlQxY0luZG9hWFJsTFhOd1lXTmxPbTV2Y20xaGJGd2lQanh6Y0dGdUlITjBlV3hsUFZ3aWRHVjRkQzFrWldOdmNtRjBhVzl1TFhSb2FXTnJibVZ6Y3pwcGJtbDBhV0ZzWENJK1BITndZVzRnYzNSNWJHVTlYQ0owWlhoMExXUmxZMjl5WVhScGIyNHRjM1I1YkdVNmFXNXBkR2xoYkZ3aVBqeHpjR0Z1SUhOMGVXeGxQVndpZEdWNGRDMWtaV052Y21GMGFXOXVMV052Ykc5eU9tbHVhWFJwWVd4Y0lqNDhjM0JoYmlCemRIbHNaVDFjSW1KaFkydG5jbTkxYm1RdFkyOXNiM0k2STJabVptWm1abHdpUGp4cGJXY2djM1I1YkdVOVhDSjNhV1IwYURveU5EQndlRndpSUhOeVl6MWNJbU5wWkRwb1RESllNbE5vV1c1YVEyUXdSV2wxWENJK1BGd3ZjM0JoYmo0OFhDOXpjR0Z1UGp4Y0wzTndZVzQrUEZ3dmMzQmhiajQ4WEM5emNHRnVQanhjTDNOd1lXNCtQRnd2YzNCaGJqNDhYQzl6Y0dGdVBqeGNMM053WVc0K1BGd3ZjM0JoYmo0OFhDOXpjR0Z1UGp4Y0wyUnBkajQ4WEM5a2FYWStQRnd2WkdsMlBqeGNMMlJwZGo0OFhDOUNUMFJaUGp4Y0wwaFVUVXcrWEc0aWZRPT0="
        while True:    
            order_rec.consumer_test(hash=hash)
            hash = input("Введи hash:\n")
    else:
        order_rec.start()
    '''
    order_rec.save_truth_test(content="""{
        "req_number": "961bb78f-5abd-4deb-98e8-d2e520e923db",
        "positions": [
            {
            "position_id": 0,
            "true_material": 5832,
            "true_ei": "шт",
            "true_value": 1
            }
        ]
    }""")
    '''
    # order_rec.consumer_test(content="""Б НЛГ 30Б1 шт""")
    # TO DO: HARD
    # order_rec.consumer_test(hash='ZX...')