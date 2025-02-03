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
            model="GigaChat-Max",
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
                    content=f"Ниже приведён текст письма. Проанализируй его и опиши, какая заявка (или запрос) содержится:\n\n{email_text}"
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
    --
Отправлено из
Mail
для Android
-------- Пересланное письмо --------
От: Шарипов Дамир Ирекович
sharipovdi@spk.ru
Кому: Damir Sharipov
damir.sharipov23@mail.ru
Дата: пятница, 04 октября 2024г., 14:12 +05:00
Тема: Уголок. пример
Уголок 200х12 8509-93 СТ3 – 15 ШТ
Уголок 160х16 8509-93 СТ3 – 29 ШТ
Уголок 160х10 8509-93 СТ3 – 265 ШТ
Уголок 140х9 8509-93 СТ3 – 441 ШТ
Уголок 125х8 8509-93 СТ3 – 147 ШТ
Уголок 100х7 8509-93 СТ3 – 1501 ШТ
Уголок 90х7 8509-93 СТ3 – 135 ШТ
Уголок 90х6 8509-93 СТ3 – 207 ШТ
Уголок 80х6 8509-93 СТ3 – 400 ШТ
Уголок 70х6 8509-93 СТ3 – 1162 ШТ
Уголок 63х5 8509-93 СТ3 – 1778 ШТ
Уголок 50х4 8509-93 СТ3 – 2604 ШТ
Уголок 45х4 8509-93 СТ3 – 2178 ШТ
Уважаемые коллеги и партнеры,
Наша Компания придерживается этических принципов ведения бизнеса и делает все для того, чтобы взаимоотношения с нашими партнерами строились на принципах открытости и прозрачности. Поэтому просим Вас сообщать нам обо всех
негативных фактах во взаимоотношениях с нашей компанией по адресу
doverie@scm.ru
. Вся информация поступает в независимую службу внутреннего аудита.
Претензии по качеству обслуживания или товара принимаются на телефон горячей линии
8-800-7000-123
. Звонки по России бесплатно
    """
    
    result = recognizer.recognize_request(sample_email)
    print("Распознанная заявка:", result)
