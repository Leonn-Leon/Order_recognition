# rabbit_rpc_client.py
import pika
import uuid
import json
import os


RABBITMQ_URL = os.getenv("RMQ_AI_URL", "amqp://guest:guest@localhost:5672/%2F")
EXCHANGE_NAME = os.getenv("RMQ_EXCHANGE_NAME", "ai")
ROUTING_KEY = os.getenv("ROUTING_KEY_1", "orderrecognition.find_request")

class RpcClient(object):
    def __init__(self):

        self.connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        self.channel = self.connection.channel()

        result = self.channel.queue_declare(queue='', exclusive=True)
        self.callback_queue = result.method.queue

        self.channel.basic_consume(
            queue=self.callback_queue,
            on_message_callback=self.on_response,
            auto_ack=True 
        )

        self.response = None
        self.corr_id = None

    def on_response(self, ch, method, props, body):

        if self.corr_id == props.correlation_id:
            self.response = body

    def call(self, data_to_send):

        self.response = None
        self.corr_id = str(uuid.uuid4())

        self.channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key=ROUTING_KEY,
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,  
            ),
            body=json.dumps(data_to_send) 
        )

        print(f" [x] Запрос отправлен в exchange='{EXCHANGE_NAME}' с ключом='{ROUTING_KEY}', ожидание ответа...")
        while self.response is None:
            self.connection.process_data_events(time_limit=None)

        self.connection.close()
        
        return json.loads(self.response)

def execute_rpc_call(structured_positions: list) -> dict:

    if not structured_positions:
        return {"error": "Нет позиций для обработки."}

    print(f" [>] Создание RPC клиента для отправки {len(structured_positions)} позиций.")
    rpc_client = RpcClient()
    
    try:
        response = rpc_client.call(structured_positions)
        print(" [<] Ответ от воркера получен.")
        return response
    except Exception as e:
        print(f" [!] Ошибка во время RPC вызова: {e}")
        return {"error": f"Ошибка связи с RabbitMQ: {e}"}