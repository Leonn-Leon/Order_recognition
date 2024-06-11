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
# from config import connection_url, first_queue, second_queue
from Use_models import Use_models

class Order_recognition():

    def __init__(self):
        self.find_mats = Find_materials()


    def write_logs(self, text, event=1):
        event = 'EVENT' if event == 1 else 'ERROR'
        date_time = datetime.now().astimezone()
        file_name = './logs/' + str(date_time.date()) + '.txt'
        log = open(file_name, 'a')
        log.write(str(date_time) + ' | ' + event + ' | ' + text + '\n')
        log.close()

    def consumer_test(self, hash:str=None, content:str=None):
        if content is None:
            content = text_from_hash(hash)
            print('Text - ', content.split('\n'), flush=True)
        kw = Key_words()
        ygpt = custom_yandex_gpt()
        clear_email = ygpt.get_pos(content)
        # clear_email = kw.find_key_words(content)
        # Отправляем распознаннaй текст(!) на поиск материалов
        print('Очищенное сообщение -', clear_email)
        results = str(self.find_mats.find_mats(clear_email))
        self.write_logs('results - ' + results, 1)
        print('results = ', results)
        # self.send_result(results)

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
                    request_text, _, _ = self.find_mats.new_mat_prep(request_text)
                    request_text = request_text.strip()
                    try:
                        true_mat = self.find_mats.all_materials[self.find_mats.all_materials['Материал'].\
                            str.contains(str(int(pos['true_material'])))]['Полное наименование материала'].values[0]
                        true_first = self.find_mats.all_materials[self.find_mats.all_materials['Материал']. \
                            str.contains(str(int(pos['true_material'])))]['Название иерархии-1'].values[0]
                        # true_mat = str(int(pos['true_material']))
                        print('Отправляем обучать !')
                        Use_models().fit(request_text, true_first)
                    except:
                        self.write_logs('Не нашёл такого материала', event=0)
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
            print("Метод 2 всё")
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
            content = text_from_hash(body['email'])
            # print('Text - ', content)
            kw = Key_words()
            ygpt = custom_yandex_gpt()
            clear_email = ygpt.get_pos(content)
            # clear_email = kw.find_key_words(content)
            # Отправляем распознанный текст(!) на поиск материалов
            print('Clear email - ', clear_email)
            results = str(self.find_mats.find_mats(clear_email))
            self.write_logs('results - ' + results, 1)
            print('results = ', results)
            # self.send_result(results)

            # проверяем, требует ли сообщение ответа
            if msg.reply_to:
                # отправляем ответ в default exchange
                print('Отправляем результат', flush=True)
                self.write_logs('Отправляем результaт', 1)
                await channel.default_exchange.publish(
                    message=aio_pika.Message(
                        content_type='application/json',
                        body=str.encode(results.replace("'", '"')[1:-1]),
                        # body=b'{"a":"b"}',
                        correlation_id=msg.correlation_id
                    ),
                    routing_key=msg.reply_to,  # самое важное

                )
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
            queue = await channel.declare_queue(conf.first_queue, timeout=50000)
            # через partial прокидываем в наш обработчик сам канал
            await queue.consume(partial(self.consumer, channel=channel), timeout=50000)
            print('Слушаем очередь', flush=True)


            queue2 = await channel.declare_queue(conf.second_queue, timeout=50000)
            await queue2.bind(exchange=conf.exchange, routing_key=conf.routing_key, timeout=50000)
            # через partial прокидываем в наш обработчик сам канал
            await queue2.consume(partial(self.save_truth), timeout=50000)
            print('Слушаем очередь2', flush=True)
            try:
                await asyncio.Future()
            except Exception:
                pass

    def start(self):
        asyncio.run(self.main())

if __name__ == '__main__':
    order_rec = Order_recognition()
    order_rec.start()
    # order_rec.consumer_test(content="""лист 8 09г2с""")
    # order_rec.consumer_test(hash='UEQ5NGJXd2dkbVZ5YzJsdmJqMG5NUzR3SnlCbGJtTnZaR2x1WnowbmRYUm1MVGduUHo0OGMyOWhjR1Z1ZGpwRmJuWmxiRzl3WlNCNGJXeHVjenB6YjJGd1pXNTJQU0pvZEhSd09pOHZjMk5vWlcxaGN5NTRiV3h6YjJGd0xtOXlaeTl6YjJGd0wyVnVkbVZzYjNCbEx5SStQSE52WVhCbGJuWTZRbTlrZVQ0OGFuTnZiazlpYW1WamRENDhiMkpxWldOMFRtRnRaVDV0YzJkZllXRmxaR1kzT0dVNVlqTmlNMkppWm1ZNU9EQTBOakl5T0dKall6UTNaR1k4TDI5aWFtVmpkRTVoYldVK1BHSjFZMnRsZEU1aGJXVStZM0p0TFdWdFlXbHNQQzlpZFdOclpYUk9ZVzFsUGp4bWFXeGxRMjl1ZEdWdWRENG1iSFE3YUhSdGJENG1JM2hrT3dvbWJIUTdhR1ZoWkQ0bUkzaGtPd29tYkhRN2JXVjBZU0JvZEhSd0xXVnhkV2wyUFNKRGIyNTBaVzUwTFZSNWNHVWlJR052Ym5SbGJuUTlJblJsZUhRdmFIUnRiRHNnWTJoaGNuTmxkRDExZEdZdE9DSStKaU40WkRzS0pteDBPeTlvWldGa1BpWWplR1E3Q2lac2REdGliMlI1UGlZamVHUTdDaVpzZER0d0lITjBlV3hsUFNKbWIyNTBMWE5wZW1VNk1UQndkRHNnWTI5c2IzSTZJekF3TURCbVppSStKbXgwTzJrKzBKTFFuZENWMEtqUW5kQ3YwSzhnMEovUW50Q24wS0xRa0RvZzBKWFJnZEM3MExnZzBMN1JndEMvMFlEUXNOQ3kwTGpSZ3RDMTBMdlJqQ0RRdmRDMTBMalF0OUN5MExYUmdkR0MwTFhRdlN3ZzBMM1F0U0RRdjlDMTBZRFF0ZEdGMEw3UXROQzQwWUxRdFNEUXY5QytJTkdCMFlIUmk5QzcwTHJRc05DOExDRFF2ZEMxSU5DKzBZTFF2OUdBMExEUXN0QzcwWS9RdWRHQzBMVWcwTC9Rc05HQTBMN1F1OUM0TENEUmdTRFF2dEdCMFlMUXZ0R0EwTDdRdHRDOTBMN1JnZEdDMFl6UmppRFF2dEdDMExyUmdOR0wwTExRc05DNTBZTFF0U0RRc3RDNzBMN1F0dEMxMEwzUXVOR1BMaVpzZERzdmFUNG1iSFE3TDNBK0ppTjRaRHNLSm14ME8ySnlQaVlqZUdRN0NpWnNkRHRpY2o0bUkzaGtPd29tYkhRN1luSStKaU40WkRzS0pteDBPMkp5UGlZamVHUTdDaVpzZER0a2FYWStKaU40WkRzS0pteDBPMlJwZGlCcFpEMGlZMjl0Y0c5elpWZGxZbFpwWlhkZlpXUnBkR0ZpYkdWZlkyOXVkR1Z1ZENJZ1pHRjBZUzF0WVdsc2NuVmhjSEF0WTI5dGNHOXpaUzFwWkQwaVkyOXRjRzl6WlZkbFlsWnBaWGRmWldScGRHRmliR1ZmWTI5dWRHVnVkQ0lnYzNSNWJHVTlJblJsZUhRdFlXeHBaMjQ2SUd4bFpuUTdJajRtSTNoa093b21iSFE3WkdsMlBpWnNkRHRpY2o0bUkzaGtPd29tYkhRN0wyUnBkajRtSTNoa093b21iSFE3WkdsMlBpWnNkRHRpY2o0bUkzaGtPd29tYkhRN0wyUnBkajRtSTNoa093b21iSFE3WkdsMklHbGtQU0p0WVdsc0xXRndjQzFoZFhSdkxXUmxabUYxYkhRdGMybG5ibUYwZFhKbElqNG1iSFE3WW5JK0ppTjRaRHNLSm14ME8ySnlQaVlqZUdRN0N0Q2UwWUxRdjlHQTBMRFFzdEM3MExYUXZkQytJTkM0MExjZzBMelF2dEN4MExqUXU5R00wTDNRdnRDNUlOQ2YwTDdSaDlHQzBZc2dUV0ZwYkM1eWRTWnNkRHRpY2o0bUkzaGtPd29tYkhRN0wyUnBkajRtSTNoa093b21iSFE3WW5JK0ppTjRaRHNLSm14ME8ySnlQaVlqZUdRN0NpMHRMUzB0TFMwdElOQ2YwTFhSZ05DMTBZSFJpOUM3MExEUXRkQzgwTDdRdFNEUmdkQyswTDdRc2RHSjBMWFF2ZEM0MExVZ0xTMHRMUzB0TFMwbWJIUTdZbkkrSmlONFpEc0swSjdSZ2pvZzBKclFzTkdDMFk4ZzBKRFF2ZEdEMFlUUmdOQzQwTFhRc3RDd0lDWmhiWEE3YkhRN1lXNTFabkpwWlhaaFgydGhkSGxoTVRNeE1UazBRRzFoYVd3dWNuVW1ZVzF3TzJkME95WnNkRHRpY2o0bUkzaGtPd3JRbXRDKzBMelJnem9nWVc1MVpuSnBaWFpoSUNaaGJYQTdiSFE3WVc1MVpuSnBaWFpoUUhOd2F5NXlkU1poYlhBN1ozUTdKbXgwTzJKeVBpWWplR1E3Q3RDVTBMRFJndEN3T2lEUXY5R1AwWUxRdmRDNDBZYlFzQ3dnTnlEUXVOR08wTDNSanlBeU1ESTA0b0N2MExNdUlOQ3lJREV6T2pBMUlDWmhiWEE3SXpRek96QTFPakF3Sm14ME8ySnlQaVlqZUdRN0N0Q2kwTFhRdk5Dd09pRFFsOUN3MFkvUXN0QzYwTEFtYkhRN1luSStKaU40WkRzS0pteDBPMkp5UGlZamVHUTdDaVpzZER0aWNqNG1JM2hrT3dvbWJIUTdaR2wySUdsa1BTSmpiMjF3YjNObFYyVmlWbWxsZDE5d2NtVjJhVzkxYzJWZlkyOXVkR1Z1ZENJZ1pHRjBZUzF0WVdsc2NuVmhjSEF0WTI5dGNHOXpaUzFwWkQwaVkyOXRjRzl6WlZkbFlsWnBaWGRmY0hKbGRtbHZkWE5sWDJOdmJuUmxiblFpUGlZamVHUTdDaVpzZER0aWJHOWphM0YxYjNSbElHbGtQU0p0WVdsc0xXRndjQzFoZFhSdkxYRjFiM1JsSWlCemRIbHNaVDBpWW05eVpHVnlMV3hsWm5RdGQybGtkR2c2SURGd2VEc2dZbTl5WkdWeUxXeGxablF0YzNSNWJHVTZJSE52Ykdsa095QmliM0prWlhJdGJHVm1kQzFqYjJ4dmNqb2djbWRpS0RBc0lEazFMQ0F5TkRrcE95QnRZWEpuYVc0NklERXdjSGdnTUhCNElERXdjSGdnTlhCNE95QndZV1JrYVc1bk9pQXdjSGdnTUhCNElEQndlQ0F4TUhCNE95QmthWE53YkdGNU9pQnBibWhsY21sME95SStKaU40WkRzS0pteDBPMlJwZGlCamJHRnpjejBpYW5NdGFHVnNjR1Z5SUdwekxYSmxZV1J0YzJjdGJYTm5JajRtYkhRN2MzUjViR1VnZEhsd1pUMGlkR1Y0ZEM5amMzTWlQaVpzZERzdmMzUjViR1UrSm14ME8ySmhjMlVnZEdGeVoyVjBQU0pmYzJWc1ppSWdhSEpsWmowaWFIUjBjSE02THk5bExtMWhhV3d1Y25VdklqNG1JM2hrT3dvbWJIUTdaR2wySUdsa1BTSnpkSGxzWlY4eE56RTNOelEzTlRNd01UYzROVFF5TnpJME15SStKaU40WkRzS0pteDBPMlJwZGlCcFpEMGljM1I1YkdWZk1UY3hOemMwTnpVek1ERTNPRFUwTWpjeU5ETmZRazlFV1NJK0ppTjRaRHNLSm14ME8yUnBkaUJqYkdGemN6MGlZMnhmTnpVMk16UTRJajRtSTNoa093b21iSFE3WkdsMklHbGtQU0pqYjIxd2IzTmxWMlZpVm1sbGQxOWxaR2wwWVdKc1pWOWpiMjUwWlc1MFgyMXlYMk56YzE5aGRIUnlJaUJ6ZEhsc1pUMGlkR1Y0ZEMxaGJHbG5iam9nYkdWbWREc2lQaVlqZUdRN0NpWnNkRHRrYVhZK0pteDBPMkp5UGlZamVHUTdDaVpzZERzdlpHbDJQaVlqZUdRN0NpWnNkRHRrYVhZKzBKdlF1TkdCMFlJZ05pQXdPZEN6TXRHQklERXNOZEdGTXlBdElEZlJpTkdDSm14ME95OWthWFkrSmlONFpEc0tKbXgwTzJScGRqN1FtOUM0MFlIUmdpQTRJREE1MExNeTBZRWdNU3cxMFlVeklDMGdOTkdJMFlJbWJIUTdZbkkrSmlONFpEc0tKbXgwT3k5a2FYWStKaU40WkRzS0pteDBPMlJwZGo3UW05QzQwWUhSZ2lBeE1DQXdPZEN6TXRHQklERXNOZEdGTXlBdE1UVFJpTkdDSm14ME8ySnlQaVlqZUdRN0NpWnNkRHN2WkdsMlBpWWplR1E3Q2lac2REdGthWFkrMEp2UXVOR0IwWUlnTVRJZ01EblFzekxSZ1NBeExEWFJoVE1nTFNBeTBZalJnaVpzZER0aWNqNG1JM2hrT3dvbWJIUTdMMlJwZGo0bUkzaGtPd29tYkhRN1pHbDJQdENiMExqUmdkR0NJREl3SURBNTBMTXkwWUVnTVN3MTBZVTJJREhSaU5HQ0ptRnRjRHR1WW5Od095WnNkRHN2WkdsMlBpWWplR1E3Q2lac2REdGthWFkrSm14ME8ySnlQaVlqZUdRN0NpWnNkRHN2WkdsMlBpWWplR1E3Q2lac2REdGthWFlnYVdROUltMWhhV3d0WVhCd0xXRjFkRzh0WkdWbVlYVnNkQzF6YVdkdVlYUjFjbVZmYlhKZlkzTnpYMkYwZEhJaVBpWnNkRHRpY2o0bUkzaGtPd29tYkhRN1luSStKaU40WkRzSzBKN1JndEMvMFlEUXNOQ3kwTHZRdGRDOTBMNGcwTGpRdHlEUXZOQyswTEhRdU5DNzBZelF2ZEMrMExrZzBKL1F2dEdIMFlMUml5Qk5ZV2xzTG5KMUpteDBPMkp5UGlZamVHUTdDaVpzZERzdlpHbDJQaVlqZUdRN0NpWnNkRHRrYVhZZ2FXUTlJbU52YlhCdmMyVlhaV0pXYVdWM1gzQnlaWFpwYjNWelpWOWpiMjUwWlc1MFgyMXlYMk56YzE5aGRIUnlJajRtYkhRN0wyUnBkajRtSTNoa093b21iSFE3TDJScGRqNG1JM2hrT3dvbWJIUTdMMlJwZGo0bUkzaGtPd29tYkhRN0wyUnBkajRtSTNoa093b21iSFE3TDJScGRqNG1JM2hrT3dvbWJIUTdMMlJwZGo0bUkzaGtPd29tYkhRN0wySnNiMk5yY1hWdmRHVStKaU40WkRzS0pteDBPeTlrYVhZK0ppTjRaRHNLSm14ME95OWthWFkrSmlONFpEc0tKbXgwT3k5a2FYWStKaU40WkRzS0pteDBPeTlpYjJSNVBpWWplR1E3Q2lac2REc3ZhSFJ0YkQ0bUkzaGtPd284TDJacGJHVkRiMjUwWlc1MFBqd3Zhbk52Yms5aWFtVmpkRDQ4TDNOdllYQmxiblk2UW05a2VUNDhMM052WVhCbGJuWTZSVzUyWld4dmNHVSs=')
    # order_rec.consumer_test(hash='UEQ5NGJXd2dkbVZ5YzJsdmJqMG5NUzR3SnlCbGJtTnZaR2x1WnowbmRYUm1MVGduUHo0OGMyOWhjR1Z1ZGpwRmJuWmxiRzl3WlNCNGJXeHVjenB6YjJGd1pXNTJQU0pvZEhSd09pOHZjMk5vWlcxaGN5NTRiV3h6YjJGd0xtOXlaeTl6YjJGd0wyVnVkbVZzYjNCbEx5SStQSE52WVhCbGJuWTZRbTlrZVQ0OGFuTnZiazlpYW1WamRENDhiMkpxWldOMFRtRnRaVDV0YzJkZk56TmxNVFF6TW1Wa01tRXdZbVZsTTJNMFl6WXpaakF6WWpFM1lXRXhNMk04TDI5aWFtVmpkRTVoYldVK1BHSjFZMnRsZEU1aGJXVStZM0p0TFdWdFlXbHNQQzlpZFdOclpYUk9ZVzFsUGp4bWFXeGxRMjl1ZEdWdWRENG1iSFE3YUhSdGJENG1JM2hrT3dvbWJIUTdhR1ZoWkQ0bUkzaGtPd29tYkhRN2JXVjBZU0JvZEhSd0xXVnhkV2wyUFNKRGIyNTBaVzUwTFZSNWNHVWlJR052Ym5SbGJuUTlJblJsZUhRdmFIUnRiRHNnWTJoaGNuTmxkRDExZEdZdE9DSStKaU40WkRzS0pteDBPeTlvWldGa1BpWWplR1E3Q2lac2REdGliMlI1UGlZamVHUTdDaVpzZER0d0lITjBlV3hsUFNKbWIyNTBMWE5wZW1VNk1UQndkRHNnWTI5c2IzSTZJekF3TURCbVppSStKbXgwTzJrKzBKTFFuZENWMEtqUW5kQ3YwSzhnMEovUW50Q24wS0xRa0RvZzBKWFJnZEM3MExnZzBMN1JndEMvMFlEUXNOQ3kwTGpSZ3RDMTBMdlJqQ0RRdmRDMTBMalF0OUN5MExYUmdkR0MwTFhRdlN3ZzBMM1F0U0RRdjlDMTBZRFF0ZEdGMEw3UXROQzQwWUxRdFNEUXY5QytJTkdCMFlIUmk5QzcwTHJRc05DOExDRFF2ZEMxSU5DKzBZTFF2OUdBMExEUXN0QzcwWS9RdWRHQzBMVWcwTC9Rc05HQTBMN1F1OUM0TENEUmdTRFF2dEdCMFlMUXZ0R0EwTDdRdHRDOTBMN1JnZEdDMFl6UmppRFF2dEdDMExyUmdOR0wwTExRc05DNTBZTFF0U0RRc3RDNzBMN1F0dEMxMEwzUXVOR1BMaVpzZERzdmFUNG1iSFE3TDNBK0ppTjRaRHNLSm14ME8ySnlQaVlqZUdRN0NpWnNkRHRpY2o0bUkzaGtPd29tYkhRN1luSStKaU40WkRzS0pteDBPMkp5UGlZamVHUTdDaVpzZER0a2FYWStKaU40WkRzS0pteDBPMlJwZGlCemRIbHNaVDBpWm05dWRDMW1ZVzFwYkhrNklHRnlhV0ZzTENCb1pXeDJaWFJwWTJFc0lITmhibk10YzJWeWFXWTdJR1p2Ym5RdGMybDZaVG9nTVRKd2REc2dZMjlzYjNJNklDTXdNREF3TURBaVBpWWplR1E3Q2lac2REdGthWFkrMEpUUXZ0Q3gwWURRdnRDMUlOR0QwWUxSZ05DK0lTRWhJU0VtWVcxd08yNWljM0E3SU5DbTBMWFF2ZEN3Sm1GdGNEdHVZbk53T3lEUXVDRFF2ZEN3MEx2UXVOR0gwTGpRdFRvbWJIUTdMMlJwZGo0bUkzaGtPd29tYkhRN1pHbDJQaVpzZER0aWNpQmtZWFJoTFcxalpTMWliMmQxY3owaU1TSStKaU40WkRzS0pteDBPeTlrYVhZK0ppTjRaRHNLSm14ME8yUnBkajRtYkhRN0lTMHRVM1JoY25SR2NtRm5iV1Z1ZEMwdFBpWWplR1E3Q2lac2REdGthWFlnYzNSNWJHVTlJbU52Ykc5eU9pQWpNREF3TURBd095Qm1iMjUwTFdaaGJXbHNlVG9nWVhKcFlXd3NJR2hsYkhabGRHbGpZU3dnYzJGdWN5MXpaWEpwWmpzZ1ptOXVkQzF6YVhwbE9pQXhNbkIwT3lCbWIyNTBMWE4wZVd4bE9pQnViM0p0WVd3N0lHWnZiblF0ZG1GeWFXRnVkQzFzYVdkaGRIVnlaWE02SUc1dmNtMWhiRHNnWm05dWRDMTJZWEpwWVc1MExXTmhjSE02SUc1dmNtMWhiRHNnWm05dWRDMTNaV2xuYUhRNklEUXdNRHNnYkdWMGRHVnlMWE53WVdOcGJtYzZJRzV2Y20xaGJEc2diM0p3YUdGdWN6b2dNanNnZEdWNGRDMWhiR2xuYmpvZ2MzUmhjblE3SUhSbGVIUXRhVzVrWlc1ME9pQXdjSGc3SUhSbGVIUXRkSEpoYm5ObWIzSnRPaUJ1YjI1bE95QjNhV1J2ZDNNNklESTdJSGR2Y21RdGMzQmhZMmx1WnpvZ01IQjRPeUF0ZDJWaWEybDBMWFJsZUhRdGMzUnliMnRsTFhkcFpIUm9PaUF3Y0hnN0lIZG9hWFJsTFhOd1lXTmxPaUJ1YjNKdFlXdzdJR0poWTJ0bmNtOTFibVF0WTI5c2IzSTZJQ05tWkdaa1ptUTdJSFJsZUhRdFpHVmpiM0poZEdsdmJpMTBhR2xqYTI1bGMzTTZJR2x1YVhScFlXdzdJSFJsZUhRdFpHVmpiM0poZEdsdmJpMXpkSGxzWlRvZ2FXNXBkR2xoYkRzZ2RHVjRkQzFrWldOdmNtRjBhVzl1TFdOdmJHOXlPaUJwYm1sMGFXRnNPeUlnWkdGMFlTMXRZMlV0YzNSNWJHVTlJbU52Ykc5eU9pQWpNREF3TURBd095Qm1iMjUwTFdaaGJXbHNlVG9nWVhKcFlXd3NJR2hsYkhabGRHbGpZU3dnYzJGdWN5MXpaWEpwWmpzZ1ptOXVkQzF6YVhwbE9pQXhNbkIwT3lCbWIyNTBMWE4wZVd4bE9pQnViM0p0WVd3N0lHWnZiblF0ZG1GeWFXRnVkQzFzYVdkaGRIVnlaWE02SUc1dmNtMWhiRHNnWm05dWRDMTJZWEpwWVc1MExXTmhjSE02SUc1dmNtMWhiRHNnWm05dWRDMTNaV2xuYUhRNklEUXdNRHNnYkdWMGRHVnlMWE53WVdOcGJtYzZJRzV2Y20xaGJEc2diM0p3YUdGdWN6b2dNanNnZEdWNGRDMWhiR2xuYmpvZ2MzUmhjblE3SUhSbGVIUXRhVzVrWlc1ME9pQXdjSGc3SUhSbGVIUXRkSEpoYm5ObWIzSnRPaUJ1YjI1bE95QjNhV1J2ZDNNNklESTdJSGR2Y21RdGMzQmhZMmx1WnpvZ01IQjRPeUF0ZDJWaWEybDBMWFJsZUhRdGMzUnliMnRsTFhkcFpIUm9PaUF3Y0hnN0lIZG9hWFJsTFhOd1lXTmxPaUJ1YjNKdFlXdzdJR0poWTJ0bmNtOTFibVF0WTI5c2IzSTZJQ05tWkdaa1ptUTdJSFJsZUhRdFpHVmpiM0poZEdsdmJpMTBhR2xqYTI1bGMzTTZJR2x1YVhScFlXdzdJSFJsZUhRdFpHVmpiM0poZEdsdmJpMXpkSGxzWlRvZ2FXNXBkR2xoYkRzZ2RHVjRkQzFrWldOdmNtRjBhVzl1TFdOdmJHOXlPaUJwYm1sMGFXRnNPeUkrSmlONFpEc0tKbXgwTzJScGRqN1FrTkdBMEx6UXNOR0MwWVBSZ05Dd0lOR0VNVFlnMEpBMU1ERFFvU0F4TXRDOEptRnRjRHR1WW5Od095QXRJREV5TERnMk5OR0MwTDBtYkhRN0wyUnBkajRtSTNoa093b21iSFE3WkdsMlBpWnNkRHR6Y0dGdUlITjBlV3hsUFNKamIyeHZjam9nSXpBd01EQXdNRHNnWm05dWRDMW1ZVzFwYkhrNklHRnlhV0ZzTENCb1pXeDJaWFJwWTJFc0lITmhibk10YzJWeWFXWTdJR1p2Ym5RdGMybDZaVG9nTVRad2VEc2dabTl1ZEMxemRIbHNaVG9nYm05eWJXRnNPeUJtYjI1MExYZGxhV2RvZERvZ05EQXdPeUJzWlhSMFpYSXRjM0JoWTJsdVp6b2dibTl5YldGc095QjBaWGgwTFdsdVpHVnVkRG9nTUhCNE95QjBaWGgwTFhSeVlXNXpabTl5YlRvZ2JtOXVaVHNnZDI5eVpDMXpjR0ZqYVc1bk9pQXdjSGc3SUhkb2FYUmxMWE53WVdObE9pQnViM0p0WVd3N0lHSmhZMnRuY205MWJtUXRZMjlzYjNJNklDTm1abVptWm1ZN0lHWnNiMkYwT2lCdWIyNWxPeUJrYVhOd2JHRjVPaUJwYm14cGJtVWdJV2x0Y0c5eWRHRnVkRHNpSUdSaGRHRXRiV05sTFhOMGVXeGxQU0pqYjJ4dmNqb2dJekF3TURBd01Ec2dabTl1ZEMxbVlXMXBiSGs2SUdGeWFXRnNMQ0JvWld4MlpYUnBZMkVzSUhOaGJuTXRjMlZ5YVdZN0lHWnZiblF0YzJsNlpUb2dNVFp3ZURzZ1ptOXVkQzF6ZEhsc1pUb2dibTl5YldGc095Qm1iMjUwTFhkbGFXZG9kRG9nTkRBd095QnNaWFIwWlhJdGMzQmhZMmx1WnpvZ2JtOXliV0ZzT3lCMFpYaDBMV2x1WkdWdWREb2dNSEI0T3lCMFpYaDBMWFJ5WVc1elptOXliVG9nYm05dVpUc2dkMjl5WkMxemNHRmphVzVuT2lBd2NIZzdJSGRvYVhSbExYTndZV05sT2lCdWIzSnRZV3c3SUdKaFkydG5jbTkxYm1RdFkyOXNiM0k2SUNObVptWm1abVk3SUdac2IyRjBPaUJ1YjI1bE95QmthWE53YkdGNU9pQnBibXhwYm1VZ0lXbHRjRzl5ZEdGdWREc2lQdENRMFlEUXZOQ3cwWUxSZzlHQTBMQW1JM2hrT3dvZzBZUXhNaURRa0RVd01OQ2hJREV5MEx3bVlXMXdPMjVpYzNBN0lDMGdOU3d3T0RqUmd0QzlKbXgwT3k5emNHRnVQaVpzZER0aWNqNG1JM2hrT3dvbWJIUTdMMlJwZGo0bUkzaGtPd29tYkhRN1pHbDJQaVpzZER0emNHRnVJSE4wZVd4bFBTSmpiMnh2Y2pvZ0l6QXdNREF3TURzZ1ptOXVkQzFtWVcxcGJIazZJR0Z5YVdGc0xDQm9aV3gyWlhScFkyRXNJSE5oYm5NdGMyVnlhV1k3SUdadmJuUXRjMmw2WlRvZ01UWndlRHNnWm05dWRDMXpkSGxzWlRvZ2JtOXliV0ZzT3lCbWIyNTBMWGRsYVdkb2REb2dOREF3T3lCc1pYUjBaWEl0YzNCaFkybHVaem9nYm05eWJXRnNPeUIwWlhoMExXbHVaR1Z1ZERvZ01IQjRPeUIwWlhoMExYUnlZVzV6Wm05eWJUb2dibTl1WlRzZ2QyOXlaQzF6Y0dGamFXNW5PaUF3Y0hnN0lIZG9hWFJsTFhOd1lXTmxPaUJ1YjNKdFlXdzdJR0poWTJ0bmNtOTFibVF0WTI5c2IzSTZJQ05tWm1abVptWTdJR1pzYjJGME9pQnViMjVsT3lCa2FYTndiR0Y1T2lCcGJteHBibVVnSVdsdGNHOXlkR0Z1ZERzaUlHUmhkR0V0YldObExYTjBlV3hsUFNKamIyeHZjam9nSXpBd01EQXdNRHNnWm05dWRDMW1ZVzFwYkhrNklHRnlhV0ZzTENCb1pXeDJaWFJwWTJFc0lITmhibk10YzJWeWFXWTdJR1p2Ym5RdGMybDZaVG9nTVRad2VEc2dabTl1ZEMxemRIbHNaVG9nYm05eWJXRnNPeUJtYjI1MExYZGxhV2RvZERvZ05EQXdPeUJzWlhSMFpYSXRjM0JoWTJsdVp6b2dibTl5YldGc095QjBaWGgwTFdsdVpHVnVkRG9nTUhCNE95QjBaWGgwTFhSeVlXNXpabTl5YlRvZ2JtOXVaVHNnZDI5eVpDMXpjR0ZqYVc1bk9pQXdjSGc3SUhkb2FYUmxMWE53WVdObE9pQnViM0p0WVd3N0lHSmhZMnRuY205MWJtUXRZMjlzYjNJNklDTm1abVptWm1ZN0lHWnNiMkYwT2lCdWIyNWxPeUJrYVhOd2JHRjVPaUJwYm14cGJtVWdJV2x0Y0c5eWRHRnVkRHNpUHRDUTBZRFF2TkN3MFlMUmc5R0EwTEFtSTNoa093b2cwWVEySU5DUU1qUXcwS0VnTVRMUXZDWmhiWEE3Ym1KemNEc2dMU0F3TERQUmd0QzlKbXgwT3k5emNHRnVQaVpzZER0aWNqNG1JM2hrT3dvbWJIUTdMMlJwZGo0bUkzaGtPd29tYkhRN1pHbDJQaVpzZER0emNHRnVJSE4wZVd4bFBTSmpiMnh2Y2pvZ0l6QXdNREF3TURzZ1ptOXVkQzFtWVcxcGJIazZJR0Z5YVdGc0xDQm9aV3gyWlhScFkyRXNJSE5oYm5NdGMyVnlhV1k3SUdadmJuUXRjMmw2WlRvZ01UWndlRHNnWm05dWRDMXpkSGxzWlRvZ2JtOXliV0ZzT3lCbWIyNTBMWGRsYVdkb2REb2dOREF3T3lCc1pYUjBaWEl0YzNCaFkybHVaem9nYm05eWJXRnNPeUIwWlhoMExXbHVaR1Z1ZERvZ01IQjRPeUIwWlhoMExYUnlZVzV6Wm05eWJUb2dibTl1WlRzZ2QyOXlaQzF6Y0dGamFXNW5PaUF3Y0hnN0lIZG9hWFJsTFhOd1lXTmxPaUJ1YjNKdFlXdzdJR0poWTJ0bmNtOTFibVF0WTI5c2IzSTZJQ05tWm1abVptWTdJR1pzYjJGME9pQnViMjVsT3lCa2FYTndiR0Y1T2lCcGJteHBibVVnSVdsdGNHOXlkR0Z1ZERzaUlHUmhkR0V0YldObExYTjBlV3hsUFNKamIyeHZjam9nSXpBd01EQXdNRHNnWm05dWRDMW1ZVzFwYkhrNklHRnlhV0ZzTENCb1pXeDJaWFJwWTJFc0lITmhibk10YzJWeWFXWTdJR1p2Ym5RdGMybDZaVG9nTVRad2VEc2dabTl1ZEMxemRIbHNaVG9nYm05eWJXRnNPeUJtYjI1MExYZGxhV2RvZERvZ05EQXdPeUJzWlhSMFpYSXRjM0JoWTJsdVp6b2dibTl5YldGc095QjBaWGgwTFdsdVpHVnVkRG9nTUhCNE95QjBaWGgwTFhSeVlXNXpabTl5YlRvZ2JtOXVaVHNnZDI5eVpDMXpjR0ZqYVc1bk9pQXdjSGc3SUhkb2FYUmxMWE53WVdObE9pQnViM0p0WVd3N0lHSmhZMnRuY205MWJtUXRZMjlzYjNJNklDTm1abVptWm1ZN0lHWnNiMkYwT2lCdWIyNWxPeUJrYVhOd2JHRjVPaUJwYm14cGJtVWdJV2x0Y0c5eWRHRnVkRHNpUHRHRTBMalF1dEdCMExEUmd0QyswWUFtSTNoa093b2cwTERSZ05DODBMRFJndEdEMFlEUml5RFF2OUMrMFlMUXZ0QzcwTDdSaDlDOTBMRFJqeURRdnRDLzBMN1JnTkN3SURZd01ERFJpTkdDSm14ME95OXpjR0Z1UGlac2REc3ZaR2wyUGlZamVHUTdDaVpzZERzdlpHbDJQaVlqZUdRN0NpWnNkRHR6Y0dGdUlITjBlV3hsUFNKamIyeHZjam9nSXpBd01EQXdNRHNnWm05dWRDMW1ZVzFwYkhrNklHRnlhV0ZzTENCb1pXeDJaWFJwWTJFc0lITmhibk10YzJWeWFXWTdJR1p2Ym5RdGMybDZaVG9nTVRad2VEc2dabTl1ZEMxemRIbHNaVG9nYm05eWJXRnNPeUJtYjI1MExYWmhjbWxoYm5RdGJHbG5ZWFIxY21Wek9pQnViM0p0WVd3N0lHWnZiblF0ZG1GeWFXRnVkQzFqWVhCek9pQnViM0p0WVd3N0lHWnZiblF0ZDJWcFoyaDBPaUEwTURBN0lHeGxkSFJsY2kxemNHRmphVzVuT2lCdWIzSnRZV3c3SUc5eWNHaGhibk02SURJN0lIUmxlSFF0WVd4cFoyNDZJSE4wWVhKME95QjBaWGgwTFdsdVpHVnVkRG9nTUhCNE95QjBaWGgwTFhSeVlXNXpabTl5YlRvZ2JtOXVaVHNnZDJsa2IzZHpPaUF5T3lCM2IzSmtMWE53WVdOcGJtYzZJREJ3ZURzZ0xYZGxZbXRwZEMxMFpYaDBMWE4wY205clpTMTNhV1IwYURvZ01IQjRPeUIzYUdsMFpTMXpjR0ZqWlRvZ2JtOXliV0ZzT3lCaVlXTnJaM0p2ZFc1a0xXTnZiRzl5T2lBalptUm1aR1prT3lCMFpYaDBMV1JsWTI5eVlYUnBiMjR0ZEdocFkydHVaWE56T2lCcGJtbDBhV0ZzT3lCMFpYaDBMV1JsWTI5eVlYUnBiMjR0YzNSNWJHVTZJR2x1YVhScFlXdzdJSFJsZUhRdFpHVmpiM0poZEdsdmJpMWpiMnh2Y2pvZ2FXNXBkR2xoYkRzZ1pHbHpjR3hoZVRvZ2FXNXNhVzVsSUNGcGJYQnZjblJoYm5RN0lHWnNiMkYwT2lCdWIyNWxPeUlnWkdGMFlTMXRZMlV0YzNSNWJHVTlJbU52Ykc5eU9pQWpNREF3TURBd095Qm1iMjUwTFdaaGJXbHNlVG9nWVhKcFlXd3NJR2hsYkhabGRHbGpZU3dnYzJGdWN5MXpaWEpwWmpzZ1ptOXVkQzF6YVhwbE9pQXhObkI0T3lCbWIyNTBMWE4wZVd4bE9pQnViM0p0WVd3N0lHWnZiblF0ZG1GeWFXRnVkQzFzYVdkaGRIVnlaWE02SUc1dmNtMWhiRHNnWm05dWRDMTJZWEpwWVc1MExXTmhjSE02SUc1dmNtMWhiRHNnWm05dWRDMTNaV2xuYUhRNklEUXdNRHNnYkdWMGRHVnlMWE53WVdOcGJtYzZJRzV2Y20xaGJEc2diM0p3YUdGdWN6b2dNanNnZEdWNGRDMWhiR2xuYmpvZ2MzUmhjblE3SUhSbGVIUXRhVzVrWlc1ME9pQXdjSGc3SUhSbGVIUXRkSEpoYm5ObWIzSnRPaUJ1YjI1bE95QjNhV1J2ZDNNNklESTdJSGR2Y21RdGMzQmhZMmx1WnpvZ01IQjRPeUF0ZDJWaWEybDBMWFJsZUhRdGMzUnliMnRsTFhkcFpIUm9PaUF3Y0hnN0lIZG9hWFJsTFhOd1lXTmxPaUJ1YjNKdFlXdzdJR0poWTJ0bmNtOTFibVF0WTI5c2IzSTZJQ05tWkdaa1ptUTdJSFJsZUhRdFpHVmpiM0poZEdsdmJpMTBhR2xqYTI1bGMzTTZJR2x1YVhScFlXdzdJSFJsZUhRdFpHVmpiM0poZEdsdmJpMXpkSGxzWlRvZ2FXNXBkR2xoYkRzZ2RHVjRkQzFrWldOdmNtRjBhVzl1TFdOdmJHOXlPaUJwYm1sMGFXRnNPeUJrYVhOd2JHRjVPaUJwYm14cGJtVWdJV2x0Y0c5eWRHRnVkRHNnWm14dllYUTZJRzV2Ym1VN0lqN1F2OUdBMEw3UXN0QyswTHZRdnRDNjBMQW1JM2hrT3dvZzBMTFJqOUMzMExEUXU5R00wTDNRc05HUElERXNNdEM4MEx3Z0xTQXlNemZRdXRDekpteDBPeTl6Y0dGdVBpWnNkRHNoTFMxRmJtUkdjbUZuYldWdWRDMHRQaVlqZUdRN0NpWnNkRHRrYVhZZ2MzUjViR1U5SW1Oc1pXRnlPaUJpYjNSb095SWdaR0YwWVMxdFkyVXRjM1I1YkdVOUltTnNaV0Z5T2lCaWIzUm9PeUkrSm14ME8ySnlJR1JoZEdFdGJXTmxMV0p2WjNWelBTSXhJajRtSTNoa093b21iSFE3TDJScGRqNG1JM2hrT3dvbWJIUTdMMlJwZGo0bUkzaGtPd29tYkhRN1pHbDJJR1JoZEdFdGJXRnlhMlZ5UFNKZlgxTkpSMTlRVDFOVVgxOGlQaTB0SUNac2REdGljajRtSTNoa093b21iSFE3TDJScGRqNG1JM2hrT3dvbWJIUTdaR2wyUHRDaElOR0QwTExRc05DMjBMWFF2ZEM0MExYUXZDd2cwTHZRdnRDejBMalJnZEdDSm14ME8ySnlQaVlqZUdRN0N0QzYwTDdRdk5DLzBMRFF2ZEM0MExnZ0ptRnRjRHR4ZFc5ME85Q2EwWURRdnRDeTBMWFF1OUdNMEwzUmk5QzVJTkNtMExYUXZkR0MwWUFtWVcxd08zRjFiM1E3Sm14ME8ySnlQaVlqZUdRN0N0Q2EwTERRdWRDMDBMRFF1OUM0MEwzUXNDRFFudEM2MFlIUXNOQzkwTEFnMEozUXVOQzYwTDdRdTlDdzBMWFFzdEM5MExBbWJIUTdZbkkrSmlONFpEc0swTE11SU5DYTBZRFFzTkdCMEwzUXZ0R1AwWURSZ2RDNkpteDBPMkp5UGlZamVHUTdDdEdDMExYUXV5NGdPRGs0TXpJMk5qUXpNekFtYkhRN1luSStKaU40WkRzSzBMclJnTkMrMExMUXRkQzcwWXpRdmRHTDBMblJodEMxMEwzUmd0R0FMdEdBMFlRdkpteDBPeTlrYVhZK0ppTjRaRHNLSm14ME95OWthWFkrSmlONFpEc0tKbXgwT3k5a2FYWStKaU40WkRzS0pteDBPeTlpYjJSNVBpWWplR1E3Q2lac2REc3ZhSFJ0YkQ0bUkzaGtPd284TDJacGJHVkRiMjUwWlc1MFBqd3Zhbk52Yms5aWFtVmpkRDQ4TDNOdllYQmxiblk2UW05a2VUNDhMM052WVhCbGJuWTZSVzUyWld4dmNHVSs=')