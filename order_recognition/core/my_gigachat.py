import os
import json
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

class EmailRequestRecognizer:
    """
    Класс для распознавания заявок из писем с помощью GigaChat.

    При инициализации загружаются:
      - Файл настроек для получения API-ключа.
      - Файл инструкции new_gpt_instruction.txt, содержащий системное сообщение.

    Метод recognize_request(email_text) отправляет письмо в GigaChat для распознавания.
    """
    def __init__(
        self,
        config_path='order_recognition/confs/gpt_keys.json',
        
        instruction_path='order_recognition/confs/new_gpt_instruction.txt'
    ):
        self.api_key = self._load_api_key(config_path)
        self.instruction = self._load_instruction(instruction_path)
        self.model = GigaChat(
            credentials=self.api_key,
            scope="GIGACHAT_API_PERS",
            model="GigaChat",
            verify_ssl_certs=False,
        )

    def _load_api_key(self, config_path):
        """
        Считывание GigaChat API-ключа из файла конфигурации.
        """
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config.get('GIGACHAT_CREDENTIALS', '')

    def _load_instruction(self, instruction_path):
        """
        Загрузка системной инструкции из файла, которая будет передаваться
        в System-сообщении для GigaChat.
        """
        with open(instruction_path, 'r', encoding='utf-8') as file:
            return file.read().strip()

    def recognize_request(self, email_text):
        """
        Метод для распознавания заявки в тексте письма.
        Возвращает ответ от GigaChat с проанализированными данными.
        """
        # Формируем payload для GigaChat
        payload = Chat(
            messages=[
                Messages(
                    role=MessagesRole.SYSTEM,
                    content=self.instruction
                ),
                Messages(
                    role=MessagesRole.USER,
                    content=f"{email_text}"
                )
            ],
            temperature=0.01,
            max_tokens=3000
        )

        # Отправляем запрос в модель
        response = self.model.chat(payload)

        # Обрабатываем и возвращаем ответ
        if response and response.choices:
            return response.choices[0].message.content.strip()
        else:
            raise Exception("Ошибка: не удалось распознать заявку в письме.")


# Пример использования скрипта
if __name__ == "__main__":
    recognizer = EmailRequestRecognizer()
    
    sample_email = """
б нлг 20ш1 12м с355 57837
б нлг 30б1 12м с355 57837
б нлг 25б1 12м с355 57837
б 20ш1 12м с255 57837
б 16б1 12м ст3пс5/сп5 57837
б 25б1 12м с255 57837
б 30к1 12м с255 57837
б 18б1 12м с255 57837
б нлг 25к1 12м с355 57837
б 20б2 12м с255 57837
б 14б1 12м ст3пс5/сп5 57837
б нлг 30б2 12м с355 57837
б нлг 40б1 12м с355 57837
б 24м 12м с255 19425
б 30к2 12м с255 57837
б 25к2 12м с255 57837
б 12б1 12м ст3пс5/сп5 57837
б 40ш1 12м с255 57837
б нлг 25ш1 12м с355 57837
б 20б1 12м с255 57837
б 20к2 12м с255 57837
б нлг 20к2 12м с355 57837
    """
    
    result = recognizer.recognize_request(sample_email)
    print("Распознанная заявка:", result)
