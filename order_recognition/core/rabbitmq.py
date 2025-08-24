import os
import asyncio
import aio_pika
import pandas as pd
import json
from order_recognition.core.distance import Find_materials
from functools import partial
from order_recognition.core.hash2text import text_from_hash
from order_recognition.confs import config as conf
from order_recognition.utils import logger
from order_recognition.utils.data_text_processing import Data_text_processing
from thread import Thread
from order_recognition.core.deepseek_parser import DeepSeekParser
from order_recognition.core.worker import process_one_task, init_worker
from aiormq.exceptions import AMQPConnectionError


class Order_recognition():

    def __init__(self):
        self.dp = Data_text_processing()
        if not os.path.exists("order_recognition/data/logs"):
            os.makedirs("order_recognition/data/logs")
        self.find_mats = Find_materials()
        self.parser = DeepSeekParser()

    async def save_truth(self,
            msg: aio_pika.IncomingMessage):
        # используем контекстный менеджер для ack'а сообщения
        async with msg.process():
            body_raw = msg.body
            try:
                body = json.loads(body_raw)
            except Exception as exc:
                logger.write_logs(f"save_truth: bad body json: {exc}", 0)
                return

            req_number = body.get('req_number') or body.get('req_Number')
            true_positions = body.get('positions', [])
            if not true_positions:
                logger.write_logs('save_truth: empty positions', 0)
                return

            # Подготовим карту Материал -> Наименование
            mat_name_map = {}
            try:
                materials_df = self.find_mats.all_materials
                if not materials_df.empty:
                    mat_series = materials_df[['Материал', 'Полное наименование материала']].dropna()
                    mat_series['Материал'] = mat_series['Материал'].astype(str)
                    mat_name_map = dict(zip(mat_series['Материал'], mat_series['Полное наименование материала']))
            except Exception as exc:
                logger.write_logs(f'save_truth: cannot build material map: {exc}', 0)

            rows = []
            for pos in true_positions:
                try:
                    material_id = str(int(pos.get('true_material')))
                except Exception:
                    material_id = str(pos.get('true_material')) if pos.get('true_material') is not None else ''

                material_name = mat_name_map.get(material_id, '')
                rows.append({
                    'req_number': req_number or '',
                    'position_id': pos.get('position_id', ''),
                    'true_material': material_id,
                    'true_material_name': material_name,
                    'true_ei': pos.get('true_ei', ''),
                    'true_value': pos.get('true_value', ''),
                    'spec_mat': pos.get('spec_mat', ''),
                })

            out_path = 'order_recognition/data/method2.csv'
            try:
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                new_df = pd.DataFrame(rows)
                if os.path.exists(out_path):
                    old_df = pd.read_csv(out_path, dtype=str)
                    out_df = pd.concat([old_df, new_df], ignore_index=True)
                else:
                    out_df = new_df
                out_df.to_csv(out_path, index=False, encoding='utf-8')
                logger.write_logs(f'save_truth: saved {len(rows)} rows to method2.csv', 1)
            except Exception as exc:
                logger.write_logs(f'save_truth: cannot write CSV: {exc}', 0)

    def start_analize_email(self, content, msg, channel):
        """
        Метод для анализа письма и отправки результата

        Args:
            content (_type_): 
            msg (_type_): 
            channel (_type_): 
        """
        print('Начало потока!', flush=True)
        logger.write_logs('start_analize_email: begin')

        # Шаг 1: Парсим сырой текст в структурированные позиции
        try:
            filtered_text = self.parser.filter_material_positions(content)
            logger.write_logs('start_analize_email: after filter')
        except Exception as exc:
            logger.write_logs(f'start_analize_email: filter error {exc}', 0)
            print('Ошибка фильтрации:', exc, flush=True)
            return

        try:
            structured_positions = self.parser.parse_order_text(filtered_text)
            logger.write_logs('start_analize_email: after parse')
        except Exception as exc:
            logger.write_logs(f'start_analize_email: parse error {exc}', 0)
            print('Ошибка парсинга:', exc, flush=True)
            return

        if not structured_positions:
            print("Не удалось распознать позиции. Поток завершен.")
            # Можно отправить пустой ответ или сообщение об ошибке
            return

        print('Распознанные структурированные позиции -', structured_positions)

        # Шаг 2: Обрабатываем каждую позицию через worker
        results_list = []
        for task in structured_positions:
            try:
                result_for_task = process_one_task(task)
            except Exception as exc:
                logger.write_logs(f'start_analize_email: process_one_task error {exc}', 0)
                print('Ошибка обработчика задачи:', exc, flush=True)
                result_for_task = {'request_text': task.get('original_query',''), 'error': str(exc)}
            results_list.append(result_for_task)

        # Шаг 3: Формируем и отправляем итоговый JSON
        response_data = {"positions": results_list}
        response_body = json.dumps(response_data, ensure_ascii=False).encode('utf-8')
        
        logger.write_logs('results - ' + response_body.decode('utf-8'), 1)
        print('results = ', response_body.decode('utf-8'))

        if msg.reply_to:
            print('Отправляем результат', flush=True)
            logger.write_logs('Отправляем результaт', 1)
            asyncio.run(channel.default_exchange.publish(
                message=aio_pika.Message(
                    content_type='application/json',
                    body=response_body,
                    correlation_id=msg.correlation_id
                ),
                routing_key=msg.reply_to,
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

    async def main(self):
        """
        Подключаемся к брокеру, объявляем очередь,
        подписываемся на неё и ждем сообщений.
        
        """
        amqp_url = conf.connection_url
        logger.write_logs(f"RMQ: connecting to {amqp_url}", 1)
        connection = await aio_pika.connect_robust(amqp_url)


        async with connection:
            channel = await connection.channel()
            # Ensure exchange exists before bindings/publishes
            await channel.declare_exchange(conf.exchange, aio_pika.ExchangeType.DIRECT, durable=True)
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
    order_rec = Order_recognition()
    print("--- [WORKER] Инициализация данных... ---")
    init_worker(
       csv_path='order_recognition/data/mats_with_features.csv', 
       csv_encoding='utf-8'
    )
    order_rec.start()