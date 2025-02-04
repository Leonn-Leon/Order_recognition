import xml.etree.ElementTree as ET
import re
import os
import asyncio
import aio_pika
import base64
import json
import time
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

        start_time = time.time()
        ygpt = custom_yandex_gpt()
        
        my_thread = Thread(target=self.test_analize_email, args=[ygpt, content])
        my_thread.start()
        
        my_thread.join()
        elapsed_time = time.time() - start_time
        print(f"Время обработки письма: {elapsed_time:.2f} секунд")

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
        hash = "UEQ5NGJXd2dkbVZ5YzJsdmJqMG5NUzR3SnlCbGJtTnZaR2x1WnowbmRYUm1MVGduUHo0OGMyOWhjR1Z1ZGpwRmJuWmxiRzl3WlNCNGJXeHVjenB6YjJGd1pXNTJQU0pvZEhSd09pOHZjMk5vWlcxaGN5NTRiV3h6YjJGd0xtOXlaeTl6YjJGd0wyVnVkbVZzYjNCbEx5SStQSE52WVhCbGJuWTZRbTlrZVQ0OGFuTnZiazlpYW1WamRENDhiMkpxWldOMFRtRnRaVDV0YzJkZk16SmhaRFZtT1dGaE5UVmpNekkyWVRNeVpXTmtNalpsT0RZNE1XVm1NR004TDI5aWFtVmpkRTVoYldVK1BHSjFZMnRsZEU1aGJXVStZM0p0TFdWdFlXbHNQQzlpZFdOclpYUk9ZVzFsUGp4bWFXeGxRMjl1ZEdWdWRENG1iSFE3YUhSdGJENG1JM2hrT3dvbWJIUTdhR1ZoWkQ0bUkzaGtPd29tYkhRN2JXVjBZU0JvZEhSd0xXVnhkV2wyUFNKRGIyNTBaVzUwTFZSNWNHVWlJR052Ym5SbGJuUTlJblJsZUhRdmFIUnRiRHNnWTJoaGNuTmxkRDExZEdZdE9DSStKaU40WkRzS0pteDBPeTlvWldGa1BpWWplR1E3Q2lac2REdGliMlI1UGlZamVHUTdDaVpzZER0d0lITjBlV3hsUFNKbWIyNTBMWE5wZW1VNk1UQndkRHNnWTI5c2IzSTZJekF3TURCbVppSStKbXgwTzJrKzBKTFFuZENWMEtqUW5kQ3YwSzhnMEovUW50Q24wS0xRa0RvZzBKWFJnZEM3MExnZzBMN1JndEMvMFlEUXNOQ3kwTGpSZ3RDMTBMdlJqQ0RRdmRDMTBMalF0OUN5MExYUmdkR0MwTFhRdlN3ZzBMM1F0U0RRdjlDMTBZRFF0ZEdGMEw3UXROQzQwWUxRdFNEUXY5QytJTkdCMFlIUmk5QzcwTHJRc05DOExDRFF2ZEMxSU5DKzBZTFF2OUdBMExEUXN0QzcwWS9RdWRHQzBMVWcwTC9Rc05HQTBMN1F1OUM0TENEUmdTRFF2dEdCMFlMUXZ0R0EwTDdRdHRDOTBMN1JnZEdDMFl6UmppRFF2dEdDMExyUmdOR0wwTExRc05DNTBZTFF0U0RRc3RDNzBMN1F0dEMxMEwzUXVOR1BMaVpzZERzdmFUNG1iSFE3TDNBK0ppTjRaRHNLSm14ME8ySnlQaVlqZUdRN0NpWnNkRHRpY2o0bUkzaGtPd29tYkhRN1luSStKaU40WkRzS0pteDBPMkp5UGlZamVHUTdDaVpzZER0a2FYWStKaU40WkRzS0pteDBPM0FnYzNSNWJHVTlJbTFoY21kcGJpMTBiM0E2SURCd2VEc2lJR1JwY2owaWJIUnlJajRtYkhRN0wzQStKaU40WkRzS0pteDBPMlJwZGlCcFpEMGliV0ZwYkMxaGNIQXRZWFYwYnkxa1pXWmhkV3gwTFhOcFoyNWhkSFZ5WlNJK0ppTjRaRHNLSm14ME8zQWdaR2x5UFNKc2RISWlQaTB0Sm14ME8ySnlQaVlqZUdRN0N0Q2UwWUxRdjlHQTBMRFFzdEM3MExYUXZkQytJTkM0MExjZ1RXRnBiQzV5ZFNEUXROQzcwWThnUVc1a2NtOXBaQ1pzZERzdmNENG1JM2hrT3dvbWJIUTdMMlJwZGo0bUkzaGtPd290TFMwdExTMHRMU0RRbjlDMTBZRFF0ZEdCMEx2UXNOQzkwTDNRdnRDMUlOQy8wTGpSZ2RHTTBMelF2aUF0TFMwdExTMHRMU1pzZER0aWNqNG1JM2hrT3dyUW50R0NPaURRcU5DdzBZRFF1TkMvMEw3UXNpRFFsTkN3MEx6UXVOR0FJTkNZMFlEUXRkQzYwTDdRc3RDNDBZY2dKbXgwTzJFZ2FISmxaajBpYldGcGJIUnZPbk5vWVhKcGNHOTJaR2xBYzNCckxuSjFJajV6YUdGeWFYQnZkbVJwUUhOd2F5NXlkU1pzZERzdllUNG1iSFE3WW5JK0ppTjRaRHNLMEpyUXZ0QzgwWU02SUVSaGJXbHlJRk5vWVhKcGNHOTJJQ1pzZER0aElHaHlaV1k5SW0xaGFXeDBienBrWVcxcGNpNXphR0Z5YVhCdmRqSXpRRzFoYVd3dWNuVWlQbVJoYldseUxuTm9ZWEpwY0c5Mk1qTkFiV0ZwYkM1eWRTWnNkRHN2WVQ0bWJIUTdZbkkrSmlONFpEc0swSlRRc05HQzBMQTZJTkMvMFkvUmd0QzkwTGpSaHRDd0xDQXhNaURRdU5HTzBMdlJqeUF5TURJMDBMTXVMQ0F3T1RveE9TQW1ZVzF3T3lNME16c3dOVG93TUNac2REdGljajRtSTNoa093clFvdEMxMEx6UXNEb2cwSmZRa05HUDBMTFF1dEN3Sm14ME8ySnlQaVlqZUdRN0NpWnNkRHRpY2o0bUkzaGtPd29tYkhRN1lteHZZMnR4ZFc5MFpTQnBaRDBpYldGcGJDMWhjSEF0WVhWMGJ5MXhkVzkwWlNJZ1kybDBaVDBpTVRjeU1EYzFOemsyT1RBeE16ZzFOekF3TmpNaUlITjBlV3hsUFNKaWIzSmtaWEl0YkdWbWREb3hjSGdnYzI5c2FXUWdJekF3TlVaR09Uc2diV0Z5WjJsdU9qQndlQ0F3Y0hnZ01IQjRJREV3Y0hnN0lIQmhaR1JwYm1jNk1IQjRJREJ3ZUNBd2NIZ2dNVEJ3ZURzaVBpWWplR1E3Q2lac2REdGthWFlnWTJ4aGMzTTlJbXB6TFdobGJIQmxjaUJxY3kxeVpXRmtiWE5uTFcxelp5SStKbXgwTzNOMGVXeGxJSFI1Y0dVOUluUmxlSFF2WTNOeklqNG1iSFE3TDNOMGVXeGxQaVpzZER0aVlYTmxJSFJoY21kbGREMGlYM05sYkdZaUlHaHlaV1k5SW1oMGRIQnpPaTh2WlM1dFlXbHNMbkoxTHlJK0ppTjRaRHNLSm14ME8yUnBkaUJwWkQwaWMzUjViR1ZmTVRjeU1EYzFOemsyT1RBeE16ZzFOekF3TmpNaVBpWWplR1E3Q2lac2REdGthWFlnYVdROUluTjBlV3hsWHpFM01qQTNOVGM1Tmprd01UTTROVGN3TURZelgwSlBSRmtpUGlZamVHUTdDaVpzZER0a2FYWWdZMnhoYzNNOUltTnNYemMzTnpFek9TSStKaU40WkRzS0pteDBPMlJwZGlCamJHRnpjejBpVjI5eVpGTmxZM1JwYjI0eFgyMXlYMk56YzE5aGRIUnlJajRtSTNoa093b21iSFE3Y0NCamJHRnpjejBpVFhOdlRtOXliV0ZzWDIxeVgyTnpjMTloZEhSeUlqNG1iSFE3WWo0bWJIUTdjM0JoYmlCemRIbHNaVDBpWm05dWRDMXphWHBsT2pFd0xqQndkRHRtYjI1MExXWmhiV2xzZVRvblFYSnBZV3duTEhOaGJuTXRjMlZ5YVdZN1kyOXNiM0k2WW14aFkyc2lQdENmMEw3UXU5QyswWUhRc0NBNElEVXdJTkdCMFlJejBML1JnUy9SZ2RDL0lDMGdPU0RSaU5HQ0pteDBPeTl6Y0dGdVBpWnNkRHN2WWo0bWJIUTdMM0ErSmlONFpEc0tKbXgwTzNBZ1kyeGhjM005SWsxemIwNXZjbTFoYkY5dGNsOWpjM05mWVhSMGNpSStKbXgwTzJJK0pteDBPM053WVc0Z2MzUjViR1U5SW1admJuUXRjMmw2WlRveE1DNHdjSFE3Wm05dWRDMW1ZVzFwYkhrNkowRnlhV0ZzSnl4ellXNXpMWE5sY21sbU8yTnZiRzl5T21Kc1lXTnJJajdRbzlDejBMN1F1OUMrMExvZzBMelF0ZEdDMExEUXU5QzcwTGpSaDlDMTBZSFF1dEM0MExrZ05UQjROVEI0TlNBMjBMd2cwWUhSZ2pQUXY5R0JOUy9SZ2RDL05TQXRJRFF5SU5HSTBZSW1iSFE3TDNOd1lXNCtKbXgwT3k5aVBpWnNkRHN2Y0Q0bUkzaGtPd29tYkhRN2NDQmpiR0Z6Y3owaVRYTnZUbTl5YldGc1gyMXlYMk56YzE5aGRIUnlJajRtYkhRN2MzQmhiaUJ6ZEhsc1pUMGlabTl1ZEMxemFYcGxPakV3TGpCd2REdG1iMjUwTFdaaGJXbHNlVG9uUVhKcFlXd25MSE5oYm5NdGMyVnlhV1k3WTI5c2IzSTZZbXhoWTJzaVB0Q2YwWURRdnRDeTBMN1F1OUMrMExyUXNDRFFzdEdQMExmUXNOQzcwWXpRdmRDdzBZOGdNOUM4MEx3ZzRvQ1RJREUxTUNEUXV0Q3pKbXgwT3k5emNHRnVQaVpzZERzdmNENG1JM2hrT3dvbWJIUTdjQ0JqYkdGemN6MGlUWE52VG05eWJXRnNYMjF5WDJOemMxOWhkSFJ5SWo0bWJIUTdjM0JoYmlCemRIbHNaVDBpWm05dWRDMXphWHBsT2pFeUxqQndkRHRqYjJ4dmNqcGliR0ZqYXp0dGMyOHRabUZ5WldGemRDMXNZVzVuZFdGblpUcFNWU0krMEpEUmdOQzgwTERSZ3RHRDBZRFFzQ0RRcENBeE50QzgwTHdnTlRFd0lOR0kwWUlnMEwvUXZpWmhiWEE3Ym1KemNEc2dNVExRdkNac2REc3ZjM0JoYmo0bWJIUTdMM0ErSmlONFpEc0tKbXgwTzNBZ1kyeGhjM005SWsxemIwNXZjbTFoYkY5dGNsOWpjM05mWVhSMGNpSStKbXgwTzNOd1lXNGdjM1I1YkdVOUltWnZiblF0YzJsNlpUb3hNaTR3Y0hRN1kyOXNiM0k2WW14aFkyczdiWE52TFdaaGNtVmhjM1F0YkdGdVozVmhaMlU2VWxVaVB0Q2YwWURRdnRDeTBMN1F1OUMrMExyUXNDRFFzdEdQMExmUXNOQzcwWXpRdmRDdzBZOG1ZVzF3TzI1aWMzQTdJQ1poYlhBN2JtSnpjRHNnSm1GdGNEdHVZbk53T3pFMU1OQzYwTE1tYkhRN0wzTndZVzQrSm14ME95OXdQaVlqZUdRN0NpWnNkRHR3SUdOc1lYTnpQU0pOYzI5T2IzSnRZV3hmYlhKZlkzTnpYMkYwZEhJaVBpWnNkRHR6Y0dGdUlITjBlV3hsUFNKbWIyNTBMWE5wZW1VNk1UTXVOWEIwTzJOdmJHOXlPbUpzWVdOcklqN1FxTkN5MExYUXU5QzcwTFhSZ0NEUXN5L1F1aUF5TU5DZklDMGdORFV3SU5DNjBMTW1iSFE3WW5JK0ppTjRaRHNLMEtqUXN0QzEwTHZRdTlDMTBZQWcwTE12MExvZ01URFFueTBnT0RBZzBMclFzeVpzZER0aWNqNG1JM2hrT3dyUXFOQ3kwTFhRdTlDNzBMWFJnQ0F4TnRDZklDMGdOelV3SU5DNjBMTW1iSFE3WW5JK0ppTjRaRHNLTkM3UW90R0EwWVBRc2RDd0lERXdNTkdGTVRBdzBZVTFJRGd3TUNEUXV0Q3pKbXgwT3k5emNHRnVQaVpzZERzdmNENG1JM2hrT3dvbWJIUTdjQ0JqYkdGemN6MGlUWE52VG05eWJXRnNYMjF5WDJOemMxOWhkSFJ5SWo0bWJIUTdjM0JoYmlCemRIbHNaVDBpWm05dWRDMXphWHBsT2pFekxqVndkRHRqYjJ4dmNqcGliR0ZqYXlJKzBLTFJnTkdEMExIUXNDQTBNTkNsTmpEUXBUUWdMU0EyTWpBZzBMclFzeVpzZER0aWNqNG1JM2hrT3dyUW90R0EwWVBRc2RDd0lEUXcwWVUwTU5HRk5DQXRJREV3TUNEUXV0Q3pKbXgwTzJKeVBpWWplR1E3Q3RDaTBZRFJnOUN4MExBZ01qRFJoVEl3MFlVeUlDMGdOVEFnMExyUXN5WnNkRHRpY2o0bUkzaGtPd3JRb3RHQTBZUFFzZEN3SURVdzBZVTFNTkdGTlNBdElETTFNREFnMExyUXN5WnNkRHRpY2o0bUkzaGtPd3JRbzlDejBMN1F1OUMrMExvZ05ERFJoVFF3MFlVMElDMGdNalV3SU5DNjBMTW1iSFE3WW5JK0ppTjRaRHNLMEtQUXM5QyswTHZRdnRDNklEVXcwWVUxTU5HRk5TQXRJRFV3SU5DNjBMTW1iSFE3WW5JK0ppTjRaRHNLMEtQUXM5QyswTHZRdnRDNklEVXcwWVUxTU5HRk5DQXRJREUxTUNEUXV0Q3pKbXgwT3k5emNHRnVQaVpzZERzdmNENG1JM2hrT3dvbWJIUTdjQ0JqYkdGemN6MGlUWE52VG05eWJXRnNYMjF5WDJOemMxOWhkSFJ5SWo0bWJIUTdjM0JoYmlCemRIbHNaVDBpWm05dWRDMXphWHBsT2pFekxqVndkRHRqYjJ4dmNqcGliR0ZqYXlJKzBMRFJnTkM4MExEUmd0R0QwWURRc0NEUWtEVXdNQ0F4TUNBdElERXpNQ0RRdXRDekpteDBPMkp5UGlZamVHUTdDdEN3MFlEUXZOQ3cwWUxSZzlHQTBMQWcwSkEwTURBZ01UQWdMU0EwTUNEUXV0Q3pKbXgwT3k5emNHRnVQaVpzZER0emNHRnVJSE4wZVd4bFBTSm1iMjUwTFhOcGVtVTZNVEl1TUhCME8yTnZiRzl5T21Kc1lXTnJPMjF6YnkxbVlYSmxZWE4wTFd4aGJtZDFZV2RsT2xKVklqNG1iSFE3TDNOd1lXNCtKbXgwT3k5d1BpWWplR1E3Q2lac2REdHdJR05zWVhOelBTSk5jMjlPYjNKdFlXeGZiWEpmWTNOelgyRjBkSElpUGlac2REdHpjR0Z1SUhOMGVXeGxQU0ptYjI1MExYTnBlbVU2TVRJdU1IQjBPMk52Ykc5eU9tSnNZV05yTzIxemJ5MW1ZWEpsWVhOMExXeGhibWQxWVdkbE9sSlZJajRtWVcxd08yNWljM0E3Sm14ME95OXpjR0Z1UGlac2REc3ZjRDRtSTNoa093b21iSFE3Y0NCamJHRnpjejBpVFhOdlRtOXliV0ZzWDIxeVgyTnpjMTloZEhSeUlqNG1ZVzF3TzI1aWMzQTdKbXgwT3k5d1BpWWplR1E3Q2lac2REc3ZaR2wyUGlZamVHUTdDaVpzZER0d0lITjBlV3hsUFNKamIyeHZjam9qTTJFM05XTTBPMlp2Ym5RNk9YQjBJRUZ5YVdGc0lqN1FvOUN5MExEUXR0Q3cwTFhRdk5HTDBMVWcwTHJRdnRDNzBMdlF0ZEN6MExnZzBMZ2cwTC9Rc05HQTBZTFF2ZEMxMFlEUml5d21iSFE3TDNBK0ppTjRaRHNLSm14ME8zQWdjM1I1YkdVOUltTnZiRzl5T2lNellUYzFZelE3Wm05dWREbzVjSFFnUVhKcFlXd2lQdENkMExEUmlOQ3dJTkNhMEw3UXZOQy8wTERRdmRDNDBZOGcwTC9SZ05DNDBMVFF0ZEdBMExiUXVOQ3kwTERRdGRHQzBZSFJqeURSamRHQzBMalJoOUMxMFlIUXV0QzQwWVVnMEwvUmdOQzQwTDNSaHRDNDBML1F2dEN5SU5DeTBMWFF0TkMxMEwzUXVOR1BJTkN4MExqUXQ5QzkwTFhSZ2RDd0lOQzRJTkMwMExYUXU5Q3cwTFhSZ2lEUXN0R0IwTFVnMExUUXU5R1BJTkdDMEw3UXM5QytMQ0RSaDlHQzBMN1FzZEdMSU5DeTBMZlFzTkM0MEx6UXZ0QyswWUxRdmRDKzBZalF0ZEM5MExqUmp5RFJnU0RRdmRDdzBZalF1TkM4MExnZzBML1FzTkdBMFlMUXZkQzEwWURRc05DODBMZ2cwWUhSZ3RHQTBMN1F1TkM3MExqUmdkR01JTkM5MExBZzBML1JnTkM0MEwzUmh0QzQwTC9Rc05HRklOQyswWUxRdXRHQTBZdlJndEMrMFlIUmd0QzRJTkM0SU5DLzBZRFF2dEMzMFlEUXNOR0gwTDNRdnRHQjBZTFF1QzRnMEovUXZ0R04wWUxRdnRDODBZTWcwTC9SZ05DKzBZSFF1TkM4SU5DUzBMRFJnU0RSZ2RDKzBMN1FzZEdKMExEUmd0R01JTkM5MExEUXZDRFF2dEN4MEw0ZzBMTFJnZEMxMFlVbUkzaGtPd29nMEwzUXRkQ3owTERSZ3RDNDBMTFF2ZEdMMFlVZzBZVFFzTkM2MFlMUXNOR0ZJTkN5MEw0ZzBMTFF0OUN3MExqUXZOQyswTDdSZ3RDOTBMN1JpTkMxMEwzUXVOR1AwWVVnMFlFZzBMM1FzTkdJMExYUXVTRFF1dEMrMEx6UXY5Q3cwTDNRdU5DMTBMa2cwTC9RdmlEUXNOQzAwWURRdGRHQjBZTWdKbXgwTzJFZ2MzUjViR1U5SW1OdmJHOXlPaU16WVRjMVl6UTdJaUJvY21WbVBTSXZMMlV1YldGcGJDNXlkUzlqYjIxd2IzTmxMejl0WVdsc2RHODliV0ZwYkhSdkpUTmhaRzkyWlhKcFpVQnpZMjB1Y25VaUlIUmhjbWRsZEQwaVgySnNZVzVySWlCeVpXdzlJaUJ1YjI5d1pXNWxjaUJ1YjNKbFptVnljbVZ5SWo0bUkzaGtPd3BrYjNabGNtbGxRSE5qYlM1eWRTWnNkRHN2WVQ0dUlOQ1MwWUhSanlEUXVOQzkwWVRRdnRHQTBMelFzTkdHMExqUmp5RFF2OUMrMFlIUmd0R0QwTC9Rc05DMTBZSWcwTElnMEwzUXRkQzMwTERRc3RDNDBZSFF1TkM4MFlQUmppRFJnZEM3MFlQUXR0Q3gwWU1nMExMUXZkR0QwWUxSZ05DMTBMM1F2ZEMxMExQUXZpRFFzTkdEMExUUXVOR0MwTEF1Sm14ME95OXdQaVlqZUdRN0NpWnNkRHR3SUhOMGVXeGxQU0pqYjJ4dmNqb2pNMkUzTldNME8yWnZiblE2T1hCMElFRnlhV0ZzSWo3UW45R0EwTFhSZ3RDMTBMM1F0OUM0MExnZzBML1F2aURRdXRDdzBZZlF0ZEdCMFlMUXN0R0RJTkMrMExIUmdkQzcwWVBRdHRDNDBMTFFzTkM5MExqUmp5RFF1TkM3MExnZzBZTFF2dEN5MExEUmdOQ3dJTkMvMFlEUXVOQzkwTGpRdk5DdzBZN1JndEdCMFk4ZzBMM1FzQ0RSZ3RDMTBMdlF0ZEdFMEw3UXZTRFFzOUMrMFlEUmo5R0gwTFhRdVNEUXU5QzQwTDNRdU5DNEppTjRaRHNLSm14ME8zVStKbXgwTzNOd1lXNGdZMnhoYzNNOUltcHpMWEJvYjI1bExXNTFiV0psY2lJK09DMDRNREF0TnpBd01DMHhNak1tYkhRN0wzTndZVzQrSm14ME95OTFQaTRnMEpmUXN0QyswTDNRdXRDNElOQy8wTDRnMEtEUXZ0R0IwWUhRdU5DNElOQ3gwTFhSZ2RDLzBMdlFzTkdDMEwzUXZpWnNkRHN2Y0Q0bUkzaGtPd29tYkhRN0wyUnBkajRtSTNoa093b21iSFE3TDJScGRqNG1JM2hrT3dvbWJIUTdMMlJwZGo0bUkzaGtPd29tYkhRN0wyUnBkajRtSTNoa093b21iSFE3TDJKc2IyTnJjWFZ2ZEdVK0ppTjRaRHNLSm14ME95OWthWFkrSmlONFpEc0tKbXgwT3k5aWIyUjVQaVlqZUdRN0NpWnNkRHN2YUhSdGJENG1JM2hrT3dvOEwyWnBiR1ZEYjI1MFpXNTBQand2YW5OdmJrOWlhbVZqZEQ0OEwzTnZZWEJsYm5ZNlFtOWtlVDQ4TDNOdllYQmxiblk2Ulc1MlpXeHZjR1Ur"
        # while True:    
        order_rec.consumer_test(hash=hash) # Выполняется паралельно но поставил заглушку
        # order_rec.consumer_test(content="крук 10 сталь 45 длина 3 метра - 26 штук")
        #     hash = input("Введи hash:\n")
    else:
        order_rec.start()