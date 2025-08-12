import xml.etree.ElementTree as ET
import re
import os
import asyncio
import aio_pika
import base64
import json
import time

from functools import partial

from .distance import Find_materials
from .hash2text import text_from_hash
from .yandexgpt import custom_yandex_gpt
from .worker import process_one_task, init_worker
from ..confs import config as conf
from ..utils import logger
from ..utils.data_text_processing import Data_text_processing
from ..utils.split_by_keys import Key_words


class Order_recognition():

    def __init__(self):
        self.dp = Data_text_processing()
        if not os.path.exists("order_recognition/data/logs"):
            os.makedirs("order_recognition/data/logs")
        self.find_mats = Find_materials()

    #def consumer_test(self, hash:str=None, content:str=None):
    #    if content is None:
    #        content = text_from_hash(hash)
    #    print('Text - ', content.split('\n'), flush=True)
        # self.test_analize_email(content)

    #    start_time = time.time()
    #    ygpt = custom_yandex_gpt()
    #    
    #    my_thread = Thread(target=self.test_analize_email, args=[ygpt, content])
    #    my_thread.start()
    #    
    #    my_thread.join()
    #    elapsed_time = time.time() - start_time
    #    print(f"Время обработки письма: {elapsed_time:.2f} секунд")

    def test_analize_email(self, ygpt: custom_yandex_gpt, content):
        clear_email = ygpt.big_mail(content)
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

        print('Clear email - ', clear_email)
        results = str(self.find_mats.paralell_rows(clear_email))
        logger.write_logs('results - ' + results, 1)
        print('results = ', results)
        # self.send_result(results)
        if msg.reply_to:
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

        async with msg.process():

            if not msg.reply_to:
                print(f" [!] Получено сообщение без 'reply_to'. Игнорирую.")
                return

            print(f" [x] Получен RPC запрос. ID: {msg.correlation_id}")
            
            try:
                structured_positions = json.loads(msg.body)
                
                results = []
                for task in structured_positions:
                    result_for_task = process_one_task(task)
                    results.append(result_for_task)
                
                response_data = {"positions": results}
                response_body = json.dumps(response_data).encode('utf-8')

                await channel.default_exchange.publish(
                    message=aio_pika.Message(
                        body=response_body,
                        correlation_id=msg.correlation_id 
                    ),
                    routing_key=msg.reply_to,
                )
                print(f" [.] Ответ для ID {msg.correlation_id} отправлен.")

            except json.JSONDecodeError:
                print(f" [!] Ошибка декодирования JSON для ID: {msg.correlation_id}")
            except Exception as e:
                print(f" [!] Ошибка при обработке запроса ID {msg.correlation_id}: {e}")
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
            logger.write_logs('Письмо не читается,'+str(exc), 0)
            print('Error, письмо не читается,', exc)
            return 'Error while reading'
        return content

    async def main(self):

        connection_url = os.getenv("RMQ_AI_URL", conf.connection_url)
        q1_name = os.getenv("first_queue", conf.first_queue)
        q2_name = os.getenv("second_queue", conf.second_queue)
        q3_name = os.getenv("third_queue", conf.third_queue)
        
        exchange_name = os.getenv("RMQ_EXCHANGE_NAME", conf.exchange)
        key1 = os.getenv("ROUTING_KEY_1", conf.routing_key)
        key2 = os.getenv("ROUTING_KEY_2", conf.routing_key2)
        key3 = os.getenv("ROUTING_KEY_3", conf.routing_key3)

        connection = None
        
        for i in range(10):
            try:
                print(f"--- [WORKER] Попытка подключения к RabbitMQ ({i+1}/10)... ---")
                connection = await aio_pika.connect_robust(connection_url)
                print("--- [WORKER] Успешное подключение к RabbitMQ! ---")
                break
            except (ConnectionRefusedError, aio_pika.exceptions.AMQPConnectionError) as e:
                if i < 9:
                    print(f"--- [WORKER] Не удалось подключиться: {e}. Повтор через 5 секунд... ---")
                    await asyncio.sleep(5)
                else:
                    print("--- [WORKER] Не удалось подключиться к RabbitMQ после всех попыток. Поток завершается. ---")
                    return

        if not connection: return
    
        async with connection:
            channel = await connection.channel()

            
            exchange = await channel.declare_exchange(
                exchange_name, aio_pika.ExchangeType.TOPIC, durable=True
            )
            
            queue1 = await channel.declare_queue(q1_name, timeout=60000)
            await queue1.bind(exchange, routing_key=key1)
            await queue1.consume(partial(self.consumer, channel=channel), timeout=60000)
            print(f"[*] Слушаем очередь 1 - '{q1_name}' (ключ: '{key1}')", flush=True)


            queue2 = await channel.declare_queue(q2_name, timeout=10000)
            await queue2.bind(exchange, routing_key=key2)
            await queue2.consume(partial(self.save_truth), timeout=10000)
            print(f"[*] Слушаем очередь 2 - '{q2_name}' (ключ: '{key2}')", flush=True)

            queue3 = await channel.declare_queue(q3_name, timeout=10000)
            await queue3.bind(exchange, routing_key=key3)
            print(f"[*] Очередь 3 - '{q3_name}' (ключ: '{key3}') создана.", flush=True)

            print("\n [OK] Воркер готов к работе. Ожидание сообщений...")
            try:
                await asyncio.Future()
            except Exception:
                pass

    def start(self):
        asyncio.run(self.main())

#if __name__ == '__main__':
#    order_rec = Order_recognition()
#    
#    print("--- [WORKER] Инициализация данных... ---")
#    init_worker(
#        csv_path='order_recognition/data/mats_with_features.csv', 
#        csv_encoding='utf-8'
#    )
#    
#    print("--- [WORKER] Запуск основного цикла сервера... ---")
#    order_rec.start()