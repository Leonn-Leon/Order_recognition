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
    order_rec.start()
    # order_rec.consumer_test(hash="ZXlKaWRXTnJaWFJPWVcxbElqb2lZM0p0TFdWdFlXbHNJaXdpYjJKcVpXTjBUbUZ0WlNJNkltMXpaMTgwTXpFM05EVmtPV1prWmpnelpHWTNOMkl6TUdOaFpEZ3pOemRrTm1Nd05pSXNJbVpwYkdWRGIyNTBaVzUwSWpvaVhHNDhTRlJOVEQ0OFFrOUVXVDQ4Y0NCemRIbHNaVDFjSW0xaGNtZHBiaTEwYjNBNklEQndlRHRjSWlCa2FYSTlYQ0pzZEhKY0lqNDhZbkkrWEc0Z0lERXVJTkNhMFlEUmc5Q3pJREV3MEx6UXZDRFJnZEdDTXlBdElEYzNNTkM2MExNZ01pNGcwSnJSZ05HRDBMTWdNVExRdk5DOElOR0IwWUl6SUMwZ09EQXcwTHJRc3lBekxpRFFtdEdBMFlQUXN5QXhOdEM4MEx3ZzBZSFJnak1nTFNBeE16SXcwTHJRc3lBMExpRFFtdEdBMFlQUXN5QXhPTkM4MEx3ZzBZSFJnak1nTFNBNE1qRFF1dEN6SURVdUlOQ2EwWURSZzlDeklESXkwTHpRdkNEUmdkR0NNeUF0SURNdzBMclFzeUEyTGlEUW10Q3cwWUxRc05DOTBMclFzQ0EyTERYUXZOQzhJTkdCMFlJeklDMGdNVFEyTU5DNjBMTWdOeTRnMEpyUXNOR0MwTERRdmRDNjBMQWdPTkM4MEx3ZzBZSFJnak1nTFNBMk5OQzYwTE1nT0M0ZzBKclJnTkdEMExNZ01UVFF2TkM4SU5HQjBZSTBOU0F0SURJdzBMclFzeUE1TGlEUW45QyswTHZRdnRHQjBMQWdOZEdGTlRBZzBZSFJnak1nTFNBeE1ERFF1dEN6SURFd0xpRFFxTkN5MExYUXU5QzcwTFhSZ0NBNDBKOGcwWUhSZ2pNZ0xTQTFNTkM2MExNZ01URXVJTkNvMExMUXRkQzcwTHZRdGRHQUlEalFveURSZ2RHQ01EblFrekxRb1NBdElEa3cwTHJRc3lBeE1pNGcwS1BRczlDKzBMdlF2dEM2SURJMTBZVXpJTkdCMFlJeklDMGdOakRRdXRDeklERXpMaURRbzlDejBMN1F1OUMrMExvZ01qWFJoVFFnMFlIUmdqTWdMU0EzTjlDNjBMTWdNVFF1SU5DajBMUFF2dEM3MEw3UXVpQXpNdEdGTkNEUmdkR0NNeUF0SURnMTBMclFzeUF4TlM0ZzBLUFFzOUMrMEx2UXZ0QzZJRE0xMFlVMElOR0IwWUl6SUMwZ05URFF1dEN6SURFMkxpRFFvOUN6MEw3UXU5QyswTG9nTkREUmhUUWcwWUhSZ2pNZ0xTQXlNakRRdXRDeklERTNMaURRbzlDejBMN1F1OUMrMExvZ05EWFJoVFVnMFlIUmdqTWdMU0ExTmRDNjBMTWdNVGd1SU5DajBMUFF2dEM3MEw3UXVpQTFNTkdGTlNEUmdkR0NNeUF0SURJM045QzYwTE1nTVRrdUlOQ2owTFBRdnRDNzBMN1F1aUExTnRHRk5TRFJnZEdDTXlBdElETXcwTHJRc3lBeU1DNGcwS1BRczlDKzBMdlF2dEM2SURZejBZVTJJTkdCMFlJeklDMGdNemd3MExyUXN5QXlNUzRnMEtQUXM5QyswTHZRdnRDNklEYzEwWVUySU5HQjBZSXpJQzBnTVRBdzBMclFzeUF5TWk0ZzBLUFFzOUMrMEx2UXZ0QzZJRGMxMFlVMU1OR0ZOU0RSZ2RHQ015QXRJREl3MExyUXN5QXlNeTRnMEp2UXVOR0IwWUlnMExQUXVpQXhMRFhRdk5DOElOR0IwWUl6SUMwZ016RFF1dEN6SURJMExpRFFtOUM0MFlIUmdpRFFzOUM2SURUUXZOQzhJTkdCMFlJeklDMGdOekRRdXRDeklESTFMaURRbTlDNDBZSFJnaURRczlDNklEWFF2TkM4SU5HQjBZSXpJQzBnTmpEUXV0Q3pJREkyTGlEUW05QzQwWUhSZ2lEUXM5QzZJREl3MEx6UXZDRFJnZEdDTXlBdElETXdNTkM2MExNZ01qY3VJTkNiMExqUmdkR0NJTkNmMEpMUW15QTBNRFlnTFNBek9URFF1dEN6SURJNExpRFFtOUM0MFlIUmdpRFF2dEdHMExqUXZkQzZMaUF3TERYUXZOQzhJQzBnTXpFeTBMclFzeUF5T1M0ZzBKdlF1TkdCMFlJZzBZWFF1aUF6MEx6UXZDQXRJREV3TU5DNjBMTWdNekF1SU5DYjBMalJnZEdDSU5DejBMb2dNVERRdk5DOElOR0IwWUl5TUNBdElERTJNTkM2MExNZ016RXVJTkNpMFlEUmc5Q3gwTEFnMEpMUWs5Q2ZJREl3MFlVekxESWdMU0EzTmRDNjBMTWdNekl1SU5DaTBZRFJnOUN4MExBZzBKTFFrOUNmSURJMTBZVXlMRGdnTFNBeU1OQzYwTE1nTXpNdUlOQ2kwWURSZzlDeDBMQWcwSkxRazlDZklETXkwWVV6TERJZ0xTQTBNTkM2MExNZ016UXVJTkNpMFlEUmc5Q3gwTEFnMEpMUWs5Q2ZJRFV3MFlVekxEVWdMU0F5TmRDNjBMTWdNelV1SU5DaTBZRFJnOUN4MExBZzBLM1FvZENTSURjMjBZVXpJQzBnTWpVdzBMclFzeUF6Tmk0ZzBLTFJnTkdEMExIUXNDRFF2OUdBMEw3UmhDQTBNTkdGTkREUmhUSWdMU0F4TmRDNjBMTWdNemN1SU5DaTBZRFJnOUN4MExBZzBML1JnTkMrMFlRZ05URFJoVFV3MFlVeklDMGdNamJRdXRDeklETTRMaURRb3RHQTBZUFFzZEN3SU5DeDBZZ2dNalhSaFRNZ0xTQXpOZEM2MExNOFhDOXdQbHh1UEhBZ1pHbHlQVndpYkhSeVhDSSswS1BRc3RDdzBMYlFzTkMxMEx6Umk5QzFJTkM2MEw3UXU5QzcwTFhRczlDNElOQzRJTkMvMExEUmdOR0MwTDNRdGRHQTBZc3NQRnd2Y0Q1Y2JqeHdJR1JwY2oxY0lteDBjbHdpUHRDZDBMRFJpTkN3SU5DYTBMN1F2TkMvMExEUXZkQzQwWThnMEwvUmdOQzQwTFRRdGRHQTBMYlF1TkN5MExEUXRkR0MwWUhSanlEUmpkR0MwTGpSaDlDMTBZSFF1dEM0MFlVZzBML1JnTkM0MEwzUmh0QzQwTC9RdnRDeUlOQ3kwTFhRdE5DMTBMM1F1TkdQSU5DeDBMalF0OUM5MExYUmdkQ3dJTkM0SU5DMDBMWFF1OUN3MExYUmdpRFFzdEdCMExVZzBMVFF1OUdQSU5HQzBMN1FzOUMrTENEUmg5R0MwTDdRc2RHTElOQ3kwTGZRc05DNDBMelF2dEMrMFlMUXZkQyswWWpRdGRDOTBMalJqeURSZ1NEUXZkQ3cwWWpRdU5DODBMZ2cwTC9Rc05HQTBZTFF2ZEMxMFlEUXNOQzgwTGdnMFlIUmd0R0EwTDdRdU5DNzBMalJnZEdNSU5DOTBMQWcwTC9SZ05DNDBMM1JodEM0MEwvUXNOR0ZJTkMrMFlMUXV0R0EwWXZSZ3RDKzBZSFJndEM0SU5DNElOQy8wWURRdnRDMzBZRFFzTkdIMEwzUXZ0R0IwWUxRdUM0ZzBKL1F2dEdOMFlMUXZ0QzgwWU1nMEwvUmdOQyswWUhRdU5DOElOQ1MwTERSZ1NEUmdkQyswTDdRc2RHSjBMRFJndEdNSU5DOTBMRFF2Q0RRdnRDeDBMNGcwTExSZ2RDMTBZVWcwTDNRdGRDejBMRFJndEM0MExMUXZkR0wwWVVnMFlUUXNOQzYwWUxRc05HRklOQ3kwTDRnMExMUXQ5Q3cwTGpRdk5DKzBMN1JndEM5MEw3UmlOQzEwTDNRdU5HUDBZVWcwWUVnMEwzUXNOR0kwTFhRdVNEUXV0QyswTHpRdjlDdzBMM1F1TkMxMExrZzBML1F2aURRc05DMDBZRFF0ZEdCMFlNbWJtSnpjRHRrYjNabGNtbGxRSE5qYlM1eWRTNGcwSkxSZ2RHUElOQzQwTDNSaE5DKzBZRFF2TkN3MFliUXVOR1BJTkMvMEw3UmdkR0MwWVBRdjlDdzBMWFJnaURRc2lEUXZkQzEwTGZRc05DeTBMalJnZEM0MEx6Umc5R09JTkdCMEx2Umc5QzIwTEhSZ3lEUXN0QzkwWVBSZ3RHQTBMWFF2ZEM5MExYUXM5QytJTkN3MFlQUXROQzQwWUxRc0M0OFhDOXdQbHh1UEhBZ1pHbHlQVndpYkhSeVhDSSswSi9SZ05DMTBZTFF0ZEM5MExmUXVOQzRJTkMvMEw0ZzBMclFzTkdIMExYUmdkR0MwTExSZ3lEUXZ0Q3gwWUhRdTlHRDBMYlF1TkN5MExEUXZkQzQwWThnMExqUXU5QzRJTkdDMEw3UXN0Q3cwWURRc0NEUXY5R0EwTGpRdmRDNDBMelFzTkdPMFlMUmdkR1BJTkM5MExBZzBZTFF0ZEM3MExYUmhOQyswTDBnMExQUXZ0R0EwWS9SaDlDMTBMa2cwTHZRdU5DOTBMalF1Q1p1WW5Od096Z3RPREF3TFRjd01EQXRNVEl6TGlEUWw5Q3kwTDdRdmRDNjBMZ2cwTC9RdmlEUW9OQyswWUhSZ2RDNDBMZ2cwTEhRdGRHQjBML1F1OUN3MFlMUXZkQytQR0p5UGp4Y0wzQStYRzQ4WkdsMklHbGtQVndpYldGcGJDMWhjSEF0WVhWMGJ5MWtaV1poZFd4MExYTnBaMjVoZEhWeVpWd2lQbHh1SUR4d0lHUnBjajFjSW14MGNsd2lQaTB0UEdKeVBseHVJQ0FnMEo3Umd0Qy8wWURRc05DeTBMdlF0ZEM5MEw0ZzBMalF0eUE4WVNCb2NtVm1QVndpYUhSMGNITTZMeTl0WVdsc0xuSjFMMXdpUGsxaGFXdzhYQzloUGlEUXROQzcwWThnUVc1a2NtOXBaRHhjTDNBK1hHNDhYQzlrYVhZK1BGd3ZRazlFV1Q0OFhDOUlWRTFNUGx4dUluMD0=")
    # order_rec.consumer_test(content="""Б НЛГ 30Б1 шт""")
    # TO DO: HARD
    # order_rec.consumer_test(hash='ZX...')