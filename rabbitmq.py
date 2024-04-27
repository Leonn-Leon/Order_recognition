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
import config as conf
# from config import connection_url, first_queue, second_queue

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
        clear_email = kw.find_key_words(content)
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
                    request_text = positions[int(pos['position_id'])]['request_text']
                    try:
                        true_mat = self.find_mats.all_materials[self.find_mats.all_materials['Материал'].\
                            str.contains(str(int(pos['true_material'])))]['Полное наименование материала'].values[0]
                        # true_mat = str(int(pos['true_material']))
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
                    self.find_mats.method2.loc[request_text] = res.decode('utf-8')
                self.find_mats.method2.to_csv('data/method2.csv')
            else:
                print('Не нашёл такого письма', flush=True)
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
            clear_email = kw.find_key_words(content)
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
            queue = await channel.declare_queue(conf.first_queue)
            # через partial прокидываем в наш обработчик сам канал
            await queue.consume(partial(self.consumer, channel=channel))
            print('Слушаем очередь', flush=True)


            queue2 = await channel.declare_queue(conf.second_queue)
            await queue2.bind(exchange=conf.exchange, routing_key=conf.routing_key)
            # через partial прокидываем в наш обработчик сам канал
            await queue2.consume(partial(self.save_truth))
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
    # order_rec.consumer_test(content="""труба 30x30x2 профильная
    # уголок 32x32x4 г/к ст3пс5/сп5
    # 25 65""")
    # order_rec.consumer_test(hash='UEQ5NGJXd2dkbVZ5YzJsdmJqMG5NUzR3SnlCbGJtTnZaR2x1WnowbmRYUm1MVGduUHo0OGMyOWhjR1Z1ZGpwRmJuWmxiRzl3WlNCNGJXeHVjenB6YjJGd1pXNTJQU0pvZEhSd09pOHZjMk5vWlcxaGN5NTRiV3h6YjJGd0xtOXlaeTl6YjJGd0wyVnVkbVZzYjNCbEx5SStQSE52WVhCbGJuWTZRbTlrZVQ0OGFuTnZiazlpYW1WamRENDhiMkpxWldOMFRtRnRaVDV0YzJkZllUTm1NV1poWW1JMlltWTJORE5rWVdSallUVm1ZMkkzTURSbVkySmxPR0k4TDI5aWFtVmpkRTVoYldVK1BHSjFZMnRsZEU1aGJXVStZM0p0TFdWdFlXbHNQQzlpZFdOclpYUk9ZVzFsUGp4bWFXeGxRMjl1ZEdWdWRENG1iSFE3YUhSdGJENG1JM2hrT3dvbWJIUTdhR1ZoWkQ0bUkzaGtPd29tYkhRN2JXVjBZU0JvZEhSd0xXVnhkV2wyUFNKRGIyNTBaVzUwTFZSNWNHVWlJR052Ym5SbGJuUTlJblJsZUhRdmFIUnRiRHNnWTJoaGNuTmxkRDExZEdZdE9DSStKaU40WkRzS0pteDBPeTlvWldGa1BpWWplR1E3Q2lac2REdGliMlI1UGlZamVHUTdDaVpzZER0d0lITjBlV3hsUFNKbWIyNTBMWE5wZW1VNk1UQndkRHNnWTI5c2IzSTZJekF3TURCbVppSStKbXgwTzJrKzBKTFFuZENWMEtqUW5kQ3YwSzhnMEovUW50Q24wS0xRa0RvZzBKWFJnZEM3MExnZzBMN1JndEMvMFlEUXNOQ3kwTGpSZ3RDMTBMdlJqQ0RRdmRDMTBMalF0OUN5MExYUmdkR0MwTFhRdlN3ZzBMM1F0U0RRdjlDMTBZRFF0ZEdGMEw3UXROQzQwWUxRdFNEUXY5QytJTkdCMFlIUmk5QzcwTHJRc05DOExDRFF2ZEMxSU5DKzBZTFF2OUdBMExEUXN0QzcwWS9RdWRHQzBMVWcwTC9Rc05HQTBMN1F1OUM0TENEUmdTRFF2dEdCMFlMUXZ0R0EwTDdRdHRDOTBMN1JnZEdDMFl6UmppRFF2dEdDMExyUmdOR0wwTExRc05DNTBZTFF0U0RRc3RDNzBMN1F0dEMxMEwzUXVOR1BMaVpzZERzdmFUNG1iSFE3TDNBK0ppTjRaRHNLSm14ME8ySnlQaVlqZUdRN0NpWnNkRHRpY2o0bUkzaGtPd29tYkhRN1luSStKaU40WkRzS0pteDBPMkp5UGlZamVHUTdDaVpzZER0a2FYWStKaU40WkRzS0pteDBPMlJwZGlCa2FYSTlJbXgwY2lJKzBKL1JnTkM0MEx6UXVOR0MwTFVzSU5DLzBMN1F0dEN3MEx2Umc5QzUwWUhSZ3RDd0xDRFF0OUN3MFkvUXN0QzYwWU1nMEwzUXNDQXdNUzR3TkNac2REdGljajRtSTNoa093b21iSFE3YzNCaGJpQnpkSGxzWlQwaVkyOXNiM0k2Y21kaUtEVXhMRFV4TERVeEtUdG1iMjUwTFdaaGJXbHNlVHB6ZVhOMFpXMHRkV2tzTFdGd2NHeGxMWE41YzNSbGJTeENiR2x1YTAxaFkxTjVjM1JsYlVadmJuUXNKbUZ0Y0R0eGRXOTBPMU5sWjI5bElGVkpKbUZ0Y0R0eGRXOTBPeXhTYjJKdmRHOHNWV0oxYm5SMUxDWmhiWEE3Y1hWdmREdElaV3gyWlhScFkyRWdUbVYxWlNaaGJYQTdjWFZ2ZERzc1FYSnBZV3dzYzJGdWN5MXpaWEpwWml3bVlXMXdPM0YxYjNRN1FYQndiR1VnUTI5c2IzSWdSVzF2YW1rbVlXMXdPM0YxYjNRN0xDWmhiWEE3Y1hWdmREdFRaV2R2WlNCVlNTQkZiVzlxYVNaaGJYQTdjWFZ2ZERzc0ptRnRjRHR4ZFc5ME8xTmxaMjlsSUZWSklGTjViV0p2YkNaaGJYQTdjWFZ2ZERzN1ptOXVkQzF6YVhwbE9qRTFjSGdpUHRDaTBZRFJnOUN4MExBZ01qWFJoVEkxMFlVeExEVWcwTC9SZ05DKzBZVFF1TkM3MFl6UXZkQ3cwWThnS05DOEtTQXlNREFnMEx3bWJIUTdMM053WVc0K0pteDBPMkp5SUhOMGVXeGxQU0ppYjNndGMybDZhVzVuT21KdmNtUmxjaTFpYjNnN1kyOXNiM0k2Y21kaUtEVXhMRFV4TERVeEtUdG1iMjUwTFdaaGJXbHNlVHB6ZVhOMFpXMHRkV2tzTFdGd2NHeGxMWE41YzNSbGJTeENiR2x1YTAxaFkxTjVjM1JsYlVadmJuUXNKbUZ0Y0R0eGRXOTBPMU5sWjI5bElGVkpKbUZ0Y0R0eGRXOTBPeXhTYjJKdmRHOHNWV0oxYm5SMUxDWmhiWEE3Y1hWdmREdElaV3gyWlhScFkyRWdUbVYxWlNaaGJYQTdjWFZ2ZERzc1FYSnBZV3dzYzJGdWN5MXpaWEpwWml3bVlXMXdPM0YxYjNRN1FYQndiR1VnUTI5c2IzSWdSVzF2YW1rbVlXMXdPM0YxYjNRN0xDWmhiWEE3Y1hWdmREdFRaV2R2WlNCVlNTQkZiVzlxYVNaaGJYQTdjWFZ2ZERzc0ptRnRjRHR4ZFc5ME8xTmxaMjlsSUZWSklGTjViV0p2YkNaaGJYQTdjWFZ2ZERzN1ptOXVkQzF6YVhwbE9qRTFjSGdpUGlZamVHUTdDaVpzZER0emNHRnVJSE4wZVd4bFBTSmpiMnh2Y2pweVoySW9OVEVzTlRFc05URXBPMlp2Ym5RdFptRnRhV3g1T25ONWMzUmxiUzExYVN3dFlYQndiR1V0YzNsemRHVnRMRUpzYVc1clRXRmpVM2x6ZEdWdFJtOXVkQ3dtWVcxd08zRjFiM1E3VTJWbmIyVWdWVWttWVcxd08zRjFiM1E3TEZKdlltOTBieXhWWW5WdWRIVXNKbUZ0Y0R0eGRXOTBPMGhsYkhabGRHbGpZU0JPWlhWbEptRnRjRHR4ZFc5ME95eEJjbWxoYkN4ellXNXpMWE5sY21sbUxDWmhiWEE3Y1hWdmREdEJjSEJzWlNCRGIyeHZjaUJGYlc5cWFTWmhiWEE3Y1hWdmREc3NKbUZ0Y0R0eGRXOTBPMU5sWjI5bElGVkpJRVZ0YjJwcEptRnRjRHR4ZFc5ME95d21ZVzF3TzNGMWIzUTdVMlZuYjJVZ1ZVa2dVM2x0WW05c0ptRnRjRHR4ZFc5ME96dG1iMjUwTFhOcGVtVTZNVFZ3ZUNJKzBLTFJnTkdEMExIUXNDQXpNTkdGTXpEUmhUSWcwTC9SZ05DKzBZVFF1TkM3MFl6UXZkQ3cwWThtWVcxd08yNWljM0E3Sm1GdGNEdHVZbk53T3laaGJYQTdibUp6Y0RzbVlXMXdPMjVpYzNBN0lERXdNQ0RRdkNac2REc3ZjM0JoYmo0bWJIUTdZbklnYzNSNWJHVTlJbUp2ZUMxemFYcHBibWM2WW05eVpHVnlMV0p2ZUR0amIyeHZjanB5WjJJb05URXNOVEVzTlRFcE8yWnZiblF0Wm1GdGFXeDVPbk41YzNSbGJTMTFhU3d0WVhCd2JHVXRjM2x6ZEdWdExFSnNhVzVyVFdGalUzbHpkR1Z0Um05dWRDd21ZVzF3TzNGMWIzUTdVMlZuYjJVZ1ZVa21ZVzF3TzNGMWIzUTdMRkp2WW05MGJ5eFZZblZ1ZEhVc0ptRnRjRHR4ZFc5ME8waGxiSFpsZEdsallTQk9aWFZsSm1GdGNEdHhkVzkwT3l4QmNtbGhiQ3h6WVc1ekxYTmxjbWxtTENaaGJYQTdjWFZ2ZER0QmNIQnNaU0JEYjJ4dmNpQkZiVzlxYVNaaGJYQTdjWFZ2ZERzc0ptRnRjRHR4ZFc5ME8xTmxaMjlsSUZWSklFVnRiMnBwSm1GdGNEdHhkVzkwT3l3bVlXMXdPM0YxYjNRN1UyVm5iMlVnVlVrZ1UzbHRZbTlzSm1GdGNEdHhkVzkwT3p0bWIyNTBMWE5wZW1VNk1UVndlQ0krSmlONFpEc0tKbXgwTzNOd1lXNGdjM1I1YkdVOUltTnZiRzl5T25KbllpZzFNU3cxTVN3MU1TazdabTl1ZEMxbVlXMXBiSGs2YzNsemRHVnRMWFZwTEMxaGNIQnNaUzF6ZVhOMFpXMHNRbXhwYm10TllXTlRlWE4wWlcxR2IyNTBMQ1poYlhBN2NYVnZkRHRUWldkdlpTQlZTU1poYlhBN2NYVnZkRHNzVW05aWIzUnZMRlZpZFc1MGRTd21ZVzF3TzNGMWIzUTdTR1ZzZG1WMGFXTmhJRTVsZFdVbVlXMXdPM0YxYjNRN0xFRnlhV0ZzTEhOaGJuTXRjMlZ5YVdZc0ptRnRjRHR4ZFc5ME8wRndjR3hsSUVOdmJHOXlJRVZ0YjJwcEptRnRjRHR4ZFc5ME95d21ZVzF3TzNGMWIzUTdVMlZuYjJVZ1ZVa2dSVzF2YW1rbVlXMXdPM0YxYjNRN0xDWmhiWEE3Y1hWdmREdFRaV2R2WlNCVlNTQlRlVzFpYjJ3bVlXMXdPM0YxYjNRN08yWnZiblF0YzJsNlpUb3hOWEI0SWo3UW85Q3owTDdRdTlDKzBMb2dNekxSaFRNeTBZVTBJTkN6TDlDNklOR0IwWUl6MEwvUmdUVXYwWUhRdnpVZzBKUFFudENoMEtJZ09EVXdPU1lqZUdRN0NpQW8wTHJRc3lrbVlXMXdPMjVpYzNBN0ptRnRjRHR1WW5Od095WmhiWEE3Ym1KemNEc21ZVzF3TzI1aWMzQTdJREV3TURBZzBMclFzeVpzZERzdmMzQmhiajRtYkhRN1luSWdZMnhsWVhJOUltRnNiQ0krSmlONFpEc0tKbXgwTzJScGRqNG1iSFE3WW5JK0ppTjRaRHNLSm14ME95OWthWFkrSmlONFpEc0tKbXgwTzNOd1lXNGdZMnhoYzNNOUltZHRZV2xzWDNOcFoyNWhkSFZ5WlY5d2NtVm1hWGdpUGkwdElDWnNkRHN2YzNCaGJqNG1iSFE3WW5JK0ppTjRaRHNLSm14ME8yUnBkaUJrYVhJOUlteDBjaUlnWTJ4aGMzTTlJbWR0WVdsc1gzTnBaMjVoZEhWeVpTSWdaR0YwWVMxemJXRnlkRzFoYVd3OUltZHRZV2xzWDNOcFoyNWhkSFZ5WlNJK0ppTjRaRHNLSm14ME8yUnBkaUJrYVhJOUlteDBjaUkrMEtFZzBZUFFzdEN3MExiUXRkQzkwTGpRdFNEUXZOQzEwTDNRdGRDMDBMYlF0ZEdBSU5DKzBZTFF0TkMxMEx2UXNDRFJnZEM5MExEUXNkQzIwTFhRdmRDNDBZOGcwSnJRc05HQzBMRFF0ZEN5SU5DVTBMWFF2ZEM0MFlFdUptRnRjRHR1WW5Od095WnNkRHRpY2o0bUkzaGtPd3JSZ3RDMTBMc3VPQzA1TlRNdE5qZzRMVFF3TFRjeEpteDBPeTlrYVhZK0ppTjRaRHNLSm14ME95OWthWFkrSmlONFpEc0tKbXgwT3k5a2FYWStKaU40WkRzS0pteDBPeTlrYVhZK0ppTjRaRHNLSm14ME95OWliMlI1UGlZamVHUTdDaVpzZERzdmFIUnRiRDRtSTNoa093bzhMMlpwYkdWRGIyNTBaVzUwUGp3dmFuTnZiazlpYW1WamRENDhMM052WVhCbGJuWTZRbTlrZVQ0OEwzTnZZWEJsYm5ZNlJXNTJaV3h2Y0dVKw==')
    # order_rec.consumer_test(hash='UEQ5NGJXd2dkbVZ5YzJsdmJqMG5NUzR3SnlCbGJtTnZaR2x1WnowbmRYUm1MVGduUHo0OGMyOWhjR1Z1ZGpwRmJuWmxiRzl3WlNCNGJXeHVjenB6YjJGd1pXNTJQU0pvZEhSd09pOHZjMk5vWlcxaGN5NTRiV3h6YjJGd0xtOXlaeTl6YjJGd0wyVnVkbVZzYjNCbEx5SStQSE52WVhCbGJuWTZRbTlrZVQ0OGFuTnZiazlpYW1WamRENDhiMkpxWldOMFRtRnRaVDV0YzJkZk56TmxNVFF6TW1Wa01tRXdZbVZsTTJNMFl6WXpaakF6WWpFM1lXRXhNMk04TDI5aWFtVmpkRTVoYldVK1BHSjFZMnRsZEU1aGJXVStZM0p0TFdWdFlXbHNQQzlpZFdOclpYUk9ZVzFsUGp4bWFXeGxRMjl1ZEdWdWRENG1iSFE3YUhSdGJENG1JM2hrT3dvbWJIUTdhR1ZoWkQ0bUkzaGtPd29tYkhRN2JXVjBZU0JvZEhSd0xXVnhkV2wyUFNKRGIyNTBaVzUwTFZSNWNHVWlJR052Ym5SbGJuUTlJblJsZUhRdmFIUnRiRHNnWTJoaGNuTmxkRDExZEdZdE9DSStKaU40WkRzS0pteDBPeTlvWldGa1BpWWplR1E3Q2lac2REdGliMlI1UGlZamVHUTdDaVpzZER0d0lITjBlV3hsUFNKbWIyNTBMWE5wZW1VNk1UQndkRHNnWTI5c2IzSTZJekF3TURCbVppSStKbXgwTzJrKzBKTFFuZENWMEtqUW5kQ3YwSzhnMEovUW50Q24wS0xRa0RvZzBKWFJnZEM3MExnZzBMN1JndEMvMFlEUXNOQ3kwTGpSZ3RDMTBMdlJqQ0RRdmRDMTBMalF0OUN5MExYUmdkR0MwTFhRdlN3ZzBMM1F0U0RRdjlDMTBZRFF0ZEdGMEw3UXROQzQwWUxRdFNEUXY5QytJTkdCMFlIUmk5QzcwTHJRc05DOExDRFF2ZEMxSU5DKzBZTFF2OUdBMExEUXN0QzcwWS9RdWRHQzBMVWcwTC9Rc05HQTBMN1F1OUM0TENEUmdTRFF2dEdCMFlMUXZ0R0EwTDdRdHRDOTBMN1JnZEdDMFl6UmppRFF2dEdDMExyUmdOR0wwTExRc05DNTBZTFF0U0RRc3RDNzBMN1F0dEMxMEwzUXVOR1BMaVpzZERzdmFUNG1iSFE3TDNBK0ppTjRaRHNLSm14ME8ySnlQaVlqZUdRN0NpWnNkRHRpY2o0bUkzaGtPd29tYkhRN1luSStKaU40WkRzS0pteDBPMkp5UGlZamVHUTdDaVpzZER0a2FYWStKaU40WkRzS0pteDBPMlJwZGlCemRIbHNaVDBpWm05dWRDMW1ZVzFwYkhrNklHRnlhV0ZzTENCb1pXeDJaWFJwWTJFc0lITmhibk10YzJWeWFXWTdJR1p2Ym5RdGMybDZaVG9nTVRKd2REc2dZMjlzYjNJNklDTXdNREF3TURBaVBpWWplR1E3Q2lac2REdGthWFkrMEpUUXZ0Q3gwWURRdnRDMUlOR0QwWUxSZ05DK0lTRWhJU0VtWVcxd08yNWljM0E3SU5DbTBMWFF2ZEN3Sm1GdGNEdHVZbk53T3lEUXVDRFF2ZEN3MEx2UXVOR0gwTGpRdFRvbWJIUTdMMlJwZGo0bUkzaGtPd29tYkhRN1pHbDJQaVpzZER0aWNpQmtZWFJoTFcxalpTMWliMmQxY3owaU1TSStKaU40WkRzS0pteDBPeTlrYVhZK0ppTjRaRHNLSm14ME8yUnBkajRtYkhRN0lTMHRVM1JoY25SR2NtRm5iV1Z1ZEMwdFBpWWplR1E3Q2lac2REdGthWFlnYzNSNWJHVTlJbU52Ykc5eU9pQWpNREF3TURBd095Qm1iMjUwTFdaaGJXbHNlVG9nWVhKcFlXd3NJR2hsYkhabGRHbGpZU3dnYzJGdWN5MXpaWEpwWmpzZ1ptOXVkQzF6YVhwbE9pQXhNbkIwT3lCbWIyNTBMWE4wZVd4bE9pQnViM0p0WVd3N0lHWnZiblF0ZG1GeWFXRnVkQzFzYVdkaGRIVnlaWE02SUc1dmNtMWhiRHNnWm05dWRDMTJZWEpwWVc1MExXTmhjSE02SUc1dmNtMWhiRHNnWm05dWRDMTNaV2xuYUhRNklEUXdNRHNnYkdWMGRHVnlMWE53WVdOcGJtYzZJRzV2Y20xaGJEc2diM0p3YUdGdWN6b2dNanNnZEdWNGRDMWhiR2xuYmpvZ2MzUmhjblE3SUhSbGVIUXRhVzVrWlc1ME9pQXdjSGc3SUhSbGVIUXRkSEpoYm5ObWIzSnRPaUJ1YjI1bE95QjNhV1J2ZDNNNklESTdJSGR2Y21RdGMzQmhZMmx1WnpvZ01IQjRPeUF0ZDJWaWEybDBMWFJsZUhRdGMzUnliMnRsTFhkcFpIUm9PaUF3Y0hnN0lIZG9hWFJsTFhOd1lXTmxPaUJ1YjNKdFlXdzdJR0poWTJ0bmNtOTFibVF0WTI5c2IzSTZJQ05tWkdaa1ptUTdJSFJsZUhRdFpHVmpiM0poZEdsdmJpMTBhR2xqYTI1bGMzTTZJR2x1YVhScFlXdzdJSFJsZUhRdFpHVmpiM0poZEdsdmJpMXpkSGxzWlRvZ2FXNXBkR2xoYkRzZ2RHVjRkQzFrWldOdmNtRjBhVzl1TFdOdmJHOXlPaUJwYm1sMGFXRnNPeUlnWkdGMFlTMXRZMlV0YzNSNWJHVTlJbU52Ykc5eU9pQWpNREF3TURBd095Qm1iMjUwTFdaaGJXbHNlVG9nWVhKcFlXd3NJR2hsYkhabGRHbGpZU3dnYzJGdWN5MXpaWEpwWmpzZ1ptOXVkQzF6YVhwbE9pQXhNbkIwT3lCbWIyNTBMWE4wZVd4bE9pQnViM0p0WVd3N0lHWnZiblF0ZG1GeWFXRnVkQzFzYVdkaGRIVnlaWE02SUc1dmNtMWhiRHNnWm05dWRDMTJZWEpwWVc1MExXTmhjSE02SUc1dmNtMWhiRHNnWm05dWRDMTNaV2xuYUhRNklEUXdNRHNnYkdWMGRHVnlMWE53WVdOcGJtYzZJRzV2Y20xaGJEc2diM0p3YUdGdWN6b2dNanNnZEdWNGRDMWhiR2xuYmpvZ2MzUmhjblE3SUhSbGVIUXRhVzVrWlc1ME9pQXdjSGc3SUhSbGVIUXRkSEpoYm5ObWIzSnRPaUJ1YjI1bE95QjNhV1J2ZDNNNklESTdJSGR2Y21RdGMzQmhZMmx1WnpvZ01IQjRPeUF0ZDJWaWEybDBMWFJsZUhRdGMzUnliMnRsTFhkcFpIUm9PaUF3Y0hnN0lIZG9hWFJsTFhOd1lXTmxPaUJ1YjNKdFlXdzdJR0poWTJ0bmNtOTFibVF0WTI5c2IzSTZJQ05tWkdaa1ptUTdJSFJsZUhRdFpHVmpiM0poZEdsdmJpMTBhR2xqYTI1bGMzTTZJR2x1YVhScFlXdzdJSFJsZUhRdFpHVmpiM0poZEdsdmJpMXpkSGxzWlRvZ2FXNXBkR2xoYkRzZ2RHVjRkQzFrWldOdmNtRjBhVzl1TFdOdmJHOXlPaUJwYm1sMGFXRnNPeUkrSmlONFpEc0tKbXgwTzJScGRqN1FrTkdBMEx6UXNOR0MwWVBSZ05Dd0lOR0VNVFlnMEpBMU1ERFFvU0F4TXRDOEptRnRjRHR1WW5Od095QXRJREV5TERnMk5OR0MwTDBtYkhRN0wyUnBkajRtSTNoa093b21iSFE3WkdsMlBpWnNkRHR6Y0dGdUlITjBlV3hsUFNKamIyeHZjam9nSXpBd01EQXdNRHNnWm05dWRDMW1ZVzFwYkhrNklHRnlhV0ZzTENCb1pXeDJaWFJwWTJFc0lITmhibk10YzJWeWFXWTdJR1p2Ym5RdGMybDZaVG9nTVRad2VEc2dabTl1ZEMxemRIbHNaVG9nYm05eWJXRnNPeUJtYjI1MExYZGxhV2RvZERvZ05EQXdPeUJzWlhSMFpYSXRjM0JoWTJsdVp6b2dibTl5YldGc095QjBaWGgwTFdsdVpHVnVkRG9nTUhCNE95QjBaWGgwTFhSeVlXNXpabTl5YlRvZ2JtOXVaVHNnZDI5eVpDMXpjR0ZqYVc1bk9pQXdjSGc3SUhkb2FYUmxMWE53WVdObE9pQnViM0p0WVd3N0lHSmhZMnRuY205MWJtUXRZMjlzYjNJNklDTm1abVptWm1ZN0lHWnNiMkYwT2lCdWIyNWxPeUJrYVhOd2JHRjVPaUJwYm14cGJtVWdJV2x0Y0c5eWRHRnVkRHNpSUdSaGRHRXRiV05sTFhOMGVXeGxQU0pqYjJ4dmNqb2dJekF3TURBd01Ec2dabTl1ZEMxbVlXMXBiSGs2SUdGeWFXRnNMQ0JvWld4MlpYUnBZMkVzSUhOaGJuTXRjMlZ5YVdZN0lHWnZiblF0YzJsNlpUb2dNVFp3ZURzZ1ptOXVkQzF6ZEhsc1pUb2dibTl5YldGc095Qm1iMjUwTFhkbGFXZG9kRG9nTkRBd095QnNaWFIwWlhJdGMzQmhZMmx1WnpvZ2JtOXliV0ZzT3lCMFpYaDBMV2x1WkdWdWREb2dNSEI0T3lCMFpYaDBMWFJ5WVc1elptOXliVG9nYm05dVpUc2dkMjl5WkMxemNHRmphVzVuT2lBd2NIZzdJSGRvYVhSbExYTndZV05sT2lCdWIzSnRZV3c3SUdKaFkydG5jbTkxYm1RdFkyOXNiM0k2SUNObVptWm1abVk3SUdac2IyRjBPaUJ1YjI1bE95QmthWE53YkdGNU9pQnBibXhwYm1VZ0lXbHRjRzl5ZEdGdWREc2lQdENRMFlEUXZOQ3cwWUxSZzlHQTBMQW1JM2hrT3dvZzBZUXhNaURRa0RVd01OQ2hJREV5MEx3bVlXMXdPMjVpYzNBN0lDMGdOU3d3T0RqUmd0QzlKbXgwT3k5emNHRnVQaVpzZER0aWNqNG1JM2hrT3dvbWJIUTdMMlJwZGo0bUkzaGtPd29tYkhRN1pHbDJQaVpzZER0emNHRnVJSE4wZVd4bFBTSmpiMnh2Y2pvZ0l6QXdNREF3TURzZ1ptOXVkQzFtWVcxcGJIazZJR0Z5YVdGc0xDQm9aV3gyWlhScFkyRXNJSE5oYm5NdGMyVnlhV1k3SUdadmJuUXRjMmw2WlRvZ01UWndlRHNnWm05dWRDMXpkSGxzWlRvZ2JtOXliV0ZzT3lCbWIyNTBMWGRsYVdkb2REb2dOREF3T3lCc1pYUjBaWEl0YzNCaFkybHVaem9nYm05eWJXRnNPeUIwWlhoMExXbHVaR1Z1ZERvZ01IQjRPeUIwWlhoMExYUnlZVzV6Wm05eWJUb2dibTl1WlRzZ2QyOXlaQzF6Y0dGamFXNW5PaUF3Y0hnN0lIZG9hWFJsTFhOd1lXTmxPaUJ1YjNKdFlXdzdJR0poWTJ0bmNtOTFibVF0WTI5c2IzSTZJQ05tWm1abVptWTdJR1pzYjJGME9pQnViMjVsT3lCa2FYTndiR0Y1T2lCcGJteHBibVVnSVdsdGNHOXlkR0Z1ZERzaUlHUmhkR0V0YldObExYTjBlV3hsUFNKamIyeHZjam9nSXpBd01EQXdNRHNnWm05dWRDMW1ZVzFwYkhrNklHRnlhV0ZzTENCb1pXeDJaWFJwWTJFc0lITmhibk10YzJWeWFXWTdJR1p2Ym5RdGMybDZaVG9nTVRad2VEc2dabTl1ZEMxemRIbHNaVG9nYm05eWJXRnNPeUJtYjI1MExYZGxhV2RvZERvZ05EQXdPeUJzWlhSMFpYSXRjM0JoWTJsdVp6b2dibTl5YldGc095QjBaWGgwTFdsdVpHVnVkRG9nTUhCNE95QjBaWGgwTFhSeVlXNXpabTl5YlRvZ2JtOXVaVHNnZDI5eVpDMXpjR0ZqYVc1bk9pQXdjSGc3SUhkb2FYUmxMWE53WVdObE9pQnViM0p0WVd3N0lHSmhZMnRuY205MWJtUXRZMjlzYjNJNklDTm1abVptWm1ZN0lHWnNiMkYwT2lCdWIyNWxPeUJrYVhOd2JHRjVPaUJwYm14cGJtVWdJV2x0Y0c5eWRHRnVkRHNpUHRDUTBZRFF2TkN3MFlMUmc5R0EwTEFtSTNoa093b2cwWVEySU5DUU1qUXcwS0VnTVRMUXZDWmhiWEE3Ym1KemNEc2dMU0F3TERQUmd0QzlKbXgwT3k5emNHRnVQaVpzZER0aWNqNG1JM2hrT3dvbWJIUTdMMlJwZGo0bUkzaGtPd29tYkhRN1pHbDJQaVpzZER0emNHRnVJSE4wZVd4bFBTSmpiMnh2Y2pvZ0l6QXdNREF3TURzZ1ptOXVkQzFtWVcxcGJIazZJR0Z5YVdGc0xDQm9aV3gyWlhScFkyRXNJSE5oYm5NdGMyVnlhV1k3SUdadmJuUXRjMmw2WlRvZ01UWndlRHNnWm05dWRDMXpkSGxzWlRvZ2JtOXliV0ZzT3lCbWIyNTBMWGRsYVdkb2REb2dOREF3T3lCc1pYUjBaWEl0YzNCaFkybHVaem9nYm05eWJXRnNPeUIwWlhoMExXbHVaR1Z1ZERvZ01IQjRPeUIwWlhoMExYUnlZVzV6Wm05eWJUb2dibTl1WlRzZ2QyOXlaQzF6Y0dGamFXNW5PaUF3Y0hnN0lIZG9hWFJsTFhOd1lXTmxPaUJ1YjNKdFlXdzdJR0poWTJ0bmNtOTFibVF0WTI5c2IzSTZJQ05tWm1abVptWTdJR1pzYjJGME9pQnViMjVsT3lCa2FYTndiR0Y1T2lCcGJteHBibVVnSVdsdGNHOXlkR0Z1ZERzaUlHUmhkR0V0YldObExYTjBlV3hsUFNKamIyeHZjam9nSXpBd01EQXdNRHNnWm05dWRDMW1ZVzFwYkhrNklHRnlhV0ZzTENCb1pXeDJaWFJwWTJFc0lITmhibk10YzJWeWFXWTdJR1p2Ym5RdGMybDZaVG9nTVRad2VEc2dabTl1ZEMxemRIbHNaVG9nYm05eWJXRnNPeUJtYjI1MExYZGxhV2RvZERvZ05EQXdPeUJzWlhSMFpYSXRjM0JoWTJsdVp6b2dibTl5YldGc095QjBaWGgwTFdsdVpHVnVkRG9nTUhCNE95QjBaWGgwTFhSeVlXNXpabTl5YlRvZ2JtOXVaVHNnZDI5eVpDMXpjR0ZqYVc1bk9pQXdjSGc3SUhkb2FYUmxMWE53WVdObE9pQnViM0p0WVd3N0lHSmhZMnRuY205MWJtUXRZMjlzYjNJNklDTm1abVptWm1ZN0lHWnNiMkYwT2lCdWIyNWxPeUJrYVhOd2JHRjVPaUJwYm14cGJtVWdJV2x0Y0c5eWRHRnVkRHNpUHRHRTBMalF1dEdCMExEUmd0QyswWUFtSTNoa093b2cwTERSZ05DODBMRFJndEdEMFlEUml5RFF2OUMrMFlMUXZ0QzcwTDdSaDlDOTBMRFJqeURRdnRDLzBMN1JnTkN3SURZd01ERFJpTkdDSm14ME95OXpjR0Z1UGlac2REc3ZaR2wyUGlZamVHUTdDaVpzZERzdlpHbDJQaVlqZUdRN0NpWnNkRHR6Y0dGdUlITjBlV3hsUFNKamIyeHZjam9nSXpBd01EQXdNRHNnWm05dWRDMW1ZVzFwYkhrNklHRnlhV0ZzTENCb1pXeDJaWFJwWTJFc0lITmhibk10YzJWeWFXWTdJR1p2Ym5RdGMybDZaVG9nTVRad2VEc2dabTl1ZEMxemRIbHNaVG9nYm05eWJXRnNPeUJtYjI1MExYWmhjbWxoYm5RdGJHbG5ZWFIxY21Wek9pQnViM0p0WVd3N0lHWnZiblF0ZG1GeWFXRnVkQzFqWVhCek9pQnViM0p0WVd3N0lHWnZiblF0ZDJWcFoyaDBPaUEwTURBN0lHeGxkSFJsY2kxemNHRmphVzVuT2lCdWIzSnRZV3c3SUc5eWNHaGhibk02SURJN0lIUmxlSFF0WVd4cFoyNDZJSE4wWVhKME95QjBaWGgwTFdsdVpHVnVkRG9nTUhCNE95QjBaWGgwTFhSeVlXNXpabTl5YlRvZ2JtOXVaVHNnZDJsa2IzZHpPaUF5T3lCM2IzSmtMWE53WVdOcGJtYzZJREJ3ZURzZ0xYZGxZbXRwZEMxMFpYaDBMWE4wY205clpTMTNhV1IwYURvZ01IQjRPeUIzYUdsMFpTMXpjR0ZqWlRvZ2JtOXliV0ZzT3lCaVlXTnJaM0p2ZFc1a0xXTnZiRzl5T2lBalptUm1aR1prT3lCMFpYaDBMV1JsWTI5eVlYUnBiMjR0ZEdocFkydHVaWE56T2lCcGJtbDBhV0ZzT3lCMFpYaDBMV1JsWTI5eVlYUnBiMjR0YzNSNWJHVTZJR2x1YVhScFlXdzdJSFJsZUhRdFpHVmpiM0poZEdsdmJpMWpiMnh2Y2pvZ2FXNXBkR2xoYkRzZ1pHbHpjR3hoZVRvZ2FXNXNhVzVsSUNGcGJYQnZjblJoYm5RN0lHWnNiMkYwT2lCdWIyNWxPeUlnWkdGMFlTMXRZMlV0YzNSNWJHVTlJbU52Ykc5eU9pQWpNREF3TURBd095Qm1iMjUwTFdaaGJXbHNlVG9nWVhKcFlXd3NJR2hsYkhabGRHbGpZU3dnYzJGdWN5MXpaWEpwWmpzZ1ptOXVkQzF6YVhwbE9pQXhObkI0T3lCbWIyNTBMWE4wZVd4bE9pQnViM0p0WVd3N0lHWnZiblF0ZG1GeWFXRnVkQzFzYVdkaGRIVnlaWE02SUc1dmNtMWhiRHNnWm05dWRDMTJZWEpwWVc1MExXTmhjSE02SUc1dmNtMWhiRHNnWm05dWRDMTNaV2xuYUhRNklEUXdNRHNnYkdWMGRHVnlMWE53WVdOcGJtYzZJRzV2Y20xaGJEc2diM0p3YUdGdWN6b2dNanNnZEdWNGRDMWhiR2xuYmpvZ2MzUmhjblE3SUhSbGVIUXRhVzVrWlc1ME9pQXdjSGc3SUhSbGVIUXRkSEpoYm5ObWIzSnRPaUJ1YjI1bE95QjNhV1J2ZDNNNklESTdJSGR2Y21RdGMzQmhZMmx1WnpvZ01IQjRPeUF0ZDJWaWEybDBMWFJsZUhRdGMzUnliMnRsTFhkcFpIUm9PaUF3Y0hnN0lIZG9hWFJsTFhOd1lXTmxPaUJ1YjNKdFlXdzdJR0poWTJ0bmNtOTFibVF0WTI5c2IzSTZJQ05tWkdaa1ptUTdJSFJsZUhRdFpHVmpiM0poZEdsdmJpMTBhR2xqYTI1bGMzTTZJR2x1YVhScFlXdzdJSFJsZUhRdFpHVmpiM0poZEdsdmJpMXpkSGxzWlRvZ2FXNXBkR2xoYkRzZ2RHVjRkQzFrWldOdmNtRjBhVzl1TFdOdmJHOXlPaUJwYm1sMGFXRnNPeUJrYVhOd2JHRjVPaUJwYm14cGJtVWdJV2x0Y0c5eWRHRnVkRHNnWm14dllYUTZJRzV2Ym1VN0lqN1F2OUdBMEw3UXN0QyswTHZRdnRDNjBMQW1JM2hrT3dvZzBMTFJqOUMzMExEUXU5R00wTDNRc05HUElERXNNdEM4MEx3Z0xTQXlNemZRdXRDekpteDBPeTl6Y0dGdVBpWnNkRHNoTFMxRmJtUkdjbUZuYldWdWRDMHRQaVlqZUdRN0NpWnNkRHRrYVhZZ2MzUjViR1U5SW1Oc1pXRnlPaUJpYjNSb095SWdaR0YwWVMxdFkyVXRjM1I1YkdVOUltTnNaV0Z5T2lCaWIzUm9PeUkrSm14ME8ySnlJR1JoZEdFdGJXTmxMV0p2WjNWelBTSXhJajRtSTNoa093b21iSFE3TDJScGRqNG1JM2hrT3dvbWJIUTdMMlJwZGo0bUkzaGtPd29tYkhRN1pHbDJJR1JoZEdFdGJXRnlhMlZ5UFNKZlgxTkpSMTlRVDFOVVgxOGlQaTB0SUNac2REdGljajRtSTNoa093b21iSFE3TDJScGRqNG1JM2hrT3dvbWJIUTdaR2wyUHRDaElOR0QwTExRc05DMjBMWFF2ZEM0MExYUXZDd2cwTHZRdnRDejBMalJnZEdDSm14ME8ySnlQaVlqZUdRN0N0QzYwTDdRdk5DLzBMRFF2ZEM0MExnZ0ptRnRjRHR4ZFc5ME85Q2EwWURRdnRDeTBMWFF1OUdNMEwzUmk5QzVJTkNtMExYUXZkR0MwWUFtWVcxd08zRjFiM1E3Sm14ME8ySnlQaVlqZUdRN0N0Q2EwTERRdWRDMDBMRFF1OUM0MEwzUXNDRFFudEM2MFlIUXNOQzkwTEFnMEozUXVOQzYwTDdRdTlDdzBMWFFzdEM5MExBbWJIUTdZbkkrSmlONFpEc0swTE11SU5DYTBZRFFzTkdCMEwzUXZ0R1AwWURSZ2RDNkpteDBPMkp5UGlZamVHUTdDdEdDMExYUXV5NGdPRGs0TXpJMk5qUXpNekFtYkhRN1luSStKaU40WkRzSzBMclJnTkMrMExMUXRkQzcwWXpRdmRHTDBMblJodEMxMEwzUmd0R0FMdEdBMFlRdkpteDBPeTlrYVhZK0ppTjRaRHNLSm14ME95OWthWFkrSmlONFpEc0tKbXgwT3k5a2FYWStKaU40WkRzS0pteDBPeTlpYjJSNVBpWWplR1E3Q2lac2REc3ZhSFJ0YkQ0bUkzaGtPd284TDJacGJHVkRiMjUwWlc1MFBqd3Zhbk52Yms5aWFtVmpkRDQ4TDNOdllYQmxiblk2UW05a2VUNDhMM052WVhCbGJuWTZSVzUyWld4dmNHVSs=')