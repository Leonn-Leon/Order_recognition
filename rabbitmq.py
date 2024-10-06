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
                        self.write_logs('Не нашёл такого материала ' + str(pos['true_material']) + ' ' + str(exc),
                                        event=0)
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
    # order_rec.consumer_test(content="""22. Труба профильная 75x750x0.9 L 6000 9 шт""")
    # order_rec.consumer_test(hash='ZXlKaWRXTnJaWFJPWVcxbElqb2lZM0p0TFdWdFlXbHNJaXdpYjJKcVpXTjBUbUZ0WlNJNkltMXpaMTlpT1dZMU5EQXlOMlUzTXpVNU1HSmtaVGt4TlRnMVptVTJOams1TkRCbE9DSXNJbVpwYkdWRGIyNTBaVzUwSWpvaVhHNDhTRlJOVEQ0OFFrOUVXVDQ4WkdsMlBqeGthWFkrMEpUUW50Q1IwSkRRa3RDWTBLTFFyRHhjTDJScGRqNDhaR2wyUHRDaExUZ2dOVEF5TVNBMjBMd3VQVFBSaU5HQ0xqeGNMMlJwZGo0OFpHbDJQdENpMFlEUmc5Q3gwTEFnTmpEUmhUWXcwWVV5MFlVMjBMd3VQVEUxMFlqUmdpNDhYQzlrYVhZK1BHUnBkajdRb3RHQTBZUFFzZEN3SURVdzBZVTFNTkdGTXRHRk50QzhMajAxMFlqUmdpNDhYQzlrYVhZK1BHUnBkajdRb3RHQTBZUFFzZEN3SURNdzBZVXlNTkdGTXRHRk50QzhMajB6TU5HSTBZSXVQRnd2WkdsMlBqeGthWFkrMEovUXU5QyswWUhRdXRDNDBMa2cwTHZRdU5HQjBZSWcwWWJRdU5DOTBMb2dNQ3cwUFRFMTBZalJnaTQ4WEM5a2FYWStQR0pzYjJOcmNYVnZkR1VnYzNSNWJHVTlYQ0ppYjNKa1pYSXRiR1ZtZERveGNIZ2djMjlzYVdRZ0l6QTROVGRCTmpzZ2JXRnlaMmx1T2pFd2NIZzdJSEJoWkdScGJtYzZNQ0F3SURBZ01UQndlRHRjSWo3UW45R1AwWUxRdmRDNDBZYlFzQ3dnTWpNZzBMRFFzdEN6MFlQUmdkR0MwTEFnTWpBeU5Dd2dNVFk2TXpBZ0t6QTNPakF3SU5DKzBZSWdYQ0xRa2RDdzBMdlJqdEdDMExYUXZkQzFMQ0RRbU5HQTBMalF2ZEN3SU5DVDBMWFF2ZEM5MExEUXROR00wTFhRc3RDOTBMQmNJaUFtYkhRN1ltRnNlWFYwWlc1bFFITndheTV5ZFNabmREczZQR0p5UGladVluTndPenhrYVhZZ2FXUTlYQ0pjSWo0OFpHbDJJR05zWVhOelBWd2lhbk10YUdWc2NHVnlJR3B6TFhKbFlXUnRjMmN0YlhOblhDSStQR1JwZGo0OFpHbDJJR2xrUFZ3aWMzUjViR1ZmTVRjeU5EUXdOVFF5T1RBd01qRXlORGswTnpCZlFrOUVXVndpUGp4a2FYWWdZMnhoYzNNOVhDSmpiRjgzTXpNNE1qQmNJajQ4Y0Q3UWxOQyswTEhSZ05HTDBMa2cwTFRRdGRDOTBZd2hQRnd2Y0Q0OGNDQnpkSGxzWlQxY0ltTnZiRzl5T2lNellUYzFZelE3SUdadmJuUTZPWEIwSUVGeWFXRnNYQ0krMEtQUXN0Q3cwTGJRc05DMTBMelJpOUMxSU5DNjBMN1F1OUM3MExYUXM5QzRJTkM0SU5DLzBMRFJnTkdDMEwzUXRkR0EwWXNzUEZ3dmNENDhjQ0J6ZEhsc1pUMWNJbU52Ykc5eU9pTXpZVGMxWXpRN0lHWnZiblE2T1hCMElFRnlhV0ZzWENJKzBKM1FzTkdJMExBZzBKclF2dEM4MEwvUXNOQzkwTGpSanlEUXY5R0EwTGpRdE5DMTBZRFF0dEM0MExMUXNOQzEwWUxSZ2RHUElOR04wWUxRdU5HSDBMWFJnZEM2MExqUmhTRFF2OUdBMExqUXZkR0cwTGpRdjlDKzBMSWcwTExRdGRDMDBMWFF2ZEM0MFk4ZzBMSFF1TkMzMEwzUXRkR0IwTEFnMExnZzBMVFF0ZEM3MExEUXRkR0NJTkN5MFlIUXRTRFF0TkM3MFk4ZzBZTFF2dEN6MEw0c0lOR0gwWUxRdnRDeDBZc2cwTExRdDlDdzBMalF2TkMrMEw3Umd0QzkwTDdSaU5DMTBMM1F1TkdQSU5HQklOQzkwTERSaU5DNDBMelF1Q0RRdjlDdzBZRFJndEM5MExYUmdOQ3cwTHpRdUNEUmdkR0MwWURRdnRDNDBMdlF1TkdCMFl3ZzBMM1FzQ0RRdjlHQTBMalF2ZEdHMExqUXY5Q3cwWVVnMEw3Umd0QzYwWURSaTlHQzBMN1JnZEdDMExnZzBMZ2cwTC9SZ05DKzBMZlJnTkN3MFlmUXZkQyswWUhSZ3RDNExpRFFuOUMrMFkzUmd0QyswTHpSZ3lEUXY5R0EwTDdSZ2RDNDBMd2cwSkxRc05HQklOR0IwTDdRdnRDeDBZblFzTkdDMFl3ZzBMM1FzTkM4SU5DKzBMSFF2aURRc3RHQjBMWFJoU0RRdmRDMTBMUFFzTkdDMExqUXN0QzkwWXZSaFNEUmhOQ3cwTHJSZ3RDdzBZVWcwTExRdmlEUXN0QzMwTERRdU5DODBMN1F2dEdDMEwzUXZ0R0kwTFhRdmRDNDBZL1JoU0RSZ1NEUXZkQ3cwWWpRdGRDNUlOQzYwTDdRdk5DLzBMRFF2ZEM0MExYUXVTRFF2OUMrSU5DdzBMVFJnTkMxMFlIUmd5QThZU0J6ZEhsc1pUMWNJbU52Ykc5eU9pTXpZVGMxWXpRN1hDSWdhSEpsWmoxY0lpOHZaUzV0WVdsc0xuSjFMMk52YlhCdmMyVXZQMjFoYVd4MGJ6MXRZV2xzZEc4bE0yRmtiM1psY21sbFFITmpiUzV5ZFZ3aVBpQmtiM1psY21sbFFITmpiUzV5ZFR4Y0wyRStMaURRa3RHQjBZOGcwTGpRdmRHRTBMN1JnTkM4MExEUmh0QzQwWThnMEwvUXZ0R0IwWUxSZzlDLzBMRFF0ZEdDSU5DeUlOQzkwTFhRdDlDdzBMTFF1TkdCMExqUXZOR0QwWTRnMFlIUXU5R0QwTGJRc2RHRElOQ3kwTDNSZzlHQzBZRFF0ZEM5MEwzUXRkQ3owTDRnMExEUmc5QzAwTGpSZ3RDd0xqeGNMM0ErUEhBZ2MzUjViR1U5WENKamIyeHZjam9qTTJFM05XTTBPeUJtYjI1ME9qbHdkQ0JCY21saGJGd2lQdENmMFlEUXRkR0MwTFhRdmRDMzBMalF1Q0RRdjlDK0lOQzYwTERSaDlDMTBZSFJndEN5MFlNZzBMN1FzZEdCMEx2Umc5QzIwTGpRc3RDdzBMM1F1TkdQSU5DNDBMdlF1Q0RSZ3RDKzBMTFFzTkdBMExBZzBML1JnTkM0MEwzUXVOQzgwTERSanRHQzBZSFJqeURRdmRDd0lOR0MwTFhRdTlDMTBZVFF2dEM5SU5DejBMN1JnTkdQMFlmUXRkQzVJTkM3MExqUXZkQzQwTGdnUEhVK1BITndZVzRnWTJ4aGMzTTlYQ0pxY3kxd2FHOXVaUzF1ZFcxaVpYSmNJajQ0TFRnd01DMDNNREF3TFRFeU16eGNMM053WVc0K1BGd3ZkVDR1SU5DWDBMTFF2dEM5MExyUXVDRFF2OUMrSU5DZzBMN1JnZEdCMExqUXVDRFFzZEMxMFlIUXY5QzcwTERSZ3RDOTBMNDhYQzl3UGp4Y0wyUnBkajQ4WEM5a2FYWStQRnd2WkdsMlBqeGNMMlJwZGo0OFhDOWthWFkrUEZ3dllteHZZMnR4ZFc5MFpUNG1ibUp6Y0RzOFpHbDJQaVp1WW5Od096eGNMMlJwZGo0OFpHbDJJR1JoZEdFdGMybG5ibUYwZFhKbExYZHBaR2RsZEQxY0ltTnZiblJoYVc1bGNsd2lQanhrYVhZZ1pHRjBZUzF6YVdkdVlYUjFjbVV0ZDJsa1oyVjBQVndpWTI5dWRHVnVkRndpUGp4a2FYWSswS0VnMFlQUXN0Q3cwTGJRdGRDOTBMalF0ZEM4UEdKeVB0Q2gwTHpRdGRDNzBMN1FzaURRbjlDMTBZTFJnQ0RRbmRDNDBMclF2dEM3MExEUXRkQ3kwTGpSaHp4aWNqNXZjSFF1WkhadmNrQnRZV2xzTG5KMVBHSnlQamc1TmpFNE9EWTJOREkwUEZ3dlpHbDJQanhjTDJScGRqNDhYQzlrYVhZK1BHUnBkajRtYm1KemNEczhYQzlrYVhZK1BGd3ZaR2wyUGp4Y0wwSlBSRmsrUEZ3dlNGUk5URDVjYmlKOQ==')
    # order_rec.save_truth_test(content="{'req_number': '187ca897-4b2c-4b07-aa75-4f0d9dff8fc5', 'mail_code': '0057653611', 'user': 'SHARIPOVDI', 'positions': [{'position_id': '4', 'true_material': '000000000000083739', 'true_ei': 'ШТ', 'true_value': '15.000', 'spec_mat': ''}]}".replace("'", '"'))