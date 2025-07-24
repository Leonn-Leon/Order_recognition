# order_recognition/core/gemini_parser.py
import google.generativeai as genai
import json
import os
from dotenv import load_dotenv
import re
from order_recognition.core.param_mapper import PARAM_MAP

load_dotenv()

SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

class GeminiParser:
    def __init__(self):
        try:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("Переменная окружения GEMINI_API_KEY не найдена.")
            genai.configure(api_key=api_key)
            
            generation_config = {"temperature": 0.0}
            
            self.model = genai.GenerativeModel(
                model_name="gemini-1.5-flash-latest", 
                generation_config=generation_config,
                safety_settings=SAFETY_SETTINGS
            )
            print("--- Gemini Parser (gemini-1.5-flash-latest) с настройками безопасности успешно инициализирован ---")

        except Exception as e:
            raise Exception(f"Ошибка при инициализации Gemini: {e}")

    def _extract_json_from_response(self, text: str) -> dict | None:
        match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', text, re.DOTALL)
        if match:
            json_string = match.group(1)
        else:
            match = re.search(r'\{[\s\S]*\}', text, re.DOTALL)
            if not match:
                print("--- Ошибка парсинга: JSON-объект не найден в ответе модели. ---")
                return None
            json_string = match.group(0)
        
        try:
            return json.loads(json_string)
        except json.JSONDecodeError as e:
            print(f"--- Ошибка декодирования JSON: {e}")
            print(f"Проблемный фрагмент: {json_string[:300]}...")
            return None

    ##### НОВАЯ ФУНКЦИЯ-ФИЛЬТР #####
    def filter_material_positions(self, text: str) -> str:
        """
        Первый проход. Очищает текст от комментариев и разговоров,
        оставляя только строки, похожие на товарные позиции.
        """
        
        prompt = f"""
        Твоя задача - выступить в роли строгого фильтра. Проанализируй текст ниже и верни ТОЛЬКО строки, которые являются конкретными товарными позициями для заказа.

        ПРАВИЛА:
        1.  **УДАЛЯЙ ВСЁ ЛИШНЕЕ:** Комментарии, договоренности ("тут как договаривались..."), вопросы, приветствия, заголовки ("Каменщики доп заявка") должны быть полностью удалены.
        2.  **СОХРАНЯЙ ТОЛЬКО ЗАКАЗЫ:** Оставляй только строки, содержащие название материала и его характеристики (например, "Арматура ф14 А500С тн 14,00").
        3.  **ФОРМАТ ВЫВОДА:** Каждую отфильтрованную позицию выводи с новой строки. Не добавляй нумерацию или маркеры списка.

        ---
        ПРИМЕР:

        ВХОДНОЙ ТЕКСТ:
        "Монолит Калинина парковка:
        Арматурная сталь	ф14 А500С	тн	14,00
        Каменщики доп заявка
        Стержень	12-А500С, ГОСТ 34028-2016
        Тут как договаривались 183 шт по 12 метров. Там они сами нарежут.
        Угол 125х8 т 4,00"

        ПРАВИЛЬНЫЙ ВЫВОД:
        "Арматурная сталь ф14 А500С тн 14,00
        Стержень 12-А500С, ГОСТ 34028-2016
        Угол 125х8 т 4,00"
        ---

        ТЕКСТ ДЛЯ ОБРАБОТКИ:
        "{text}"
        """

        try:
            response = self.model.generate_content(prompt.format(text=text), safety_settings=SAFETY_SETTINGS)
            if not response.parts:
                print("--- Фильтрующий промпт был заблокирован ---")
                return text # В случае ошибки возвращаем исходный текст
            
            print("--- Текст после первого прохода (фильтрации) ---")
            print(response.text)
            return response.text.strip()
            
        except Exception as e:
            print(f"Ошибка на этапе фильтрации текста: {e}")
            return text # В случае ошибки возвращаем исходный текст


    def parse_order_text(self, text: str) -> list[dict]:
        
        VALID_BASE_NAMES = list(PARAM_MAP.keys())
       
        # ФИНАЛЬНАЯ, САМАЯ СТРОГАЯ ВЕРСИЯ ПРОМПТА
        prompt = f"""
        Проанализируй текст заказа и верни ТОЛЬКО ОДИН JSON-объект.
        **КЛЮЧЕВОЕ ПРАВИЛО: Извлекай в `params` только те характеристики, которые ЯВНО УКАЗАНЫ в тексте. Ничего не додумывай.**

        Текст для анализа: "{text}"

        Инструкции:
        1.  Создай ключ "positions", содержащий список JSON-объектов для каждой товарной позиции.
        2.  Каждый объект должен иметь ключи: `original_query`, `base_name`, `quantity` (по умолч. 1), `unit` (по умолч. 'шт'), и `params`.
        3.  Ключ `base_name` должен быть одним из: {VALID_BASE_NAMES}.

        Правила для `params` (в нижнем регистре):
        - `номер`: Для швеллера или балки. **Извлекай из строки ТОЛЬКО ЦИФРЫ номера (например, из "24у" извлеки "24", из "70ш4" извлеки "70").**
        - `размер`: Для профильных труб и уголков (например, "80x40").
        - `диаметр`: Для круглых труб, арматуры, кругов. **Ищи его в форматах "ф12", "d12" или "12-А500С".**
        - `толщина`: Толщина стенки или листа.
        - `марка стали`: Марка стали без префикса 'ст' (например, "09г2с", "3пс5/сп5").
        - `класс`: Класс арматуры ("а500с").
        - `длина`: Длина в метрах. Нормализуй числовые значения ("12 метров" -> "12"). Для нечисловых используй "бухта" или "немер". **Если видишь конструкцию вида `(L=410мм ...)` или `(L=4.1м ...)`, извлекай из нее длину и приводи ее К МЕТРАМ (например, `410мм` -> `0.41`, `4.1м` -> `4.1`).**
        - `тип`: **Универсальный параметр.** Для швеллера/балки ищи букву, идущую за номером (из "16п" -> "п"). Для труб ищи 'вгп', 'эс', 'оц'. Если найдено несколько типов для трубы, верни их как список (["оц", "вгп"]).
        - Остальные (`гост_ту`, `состояние`, и т.д.) добавляй, только если они явно есть в тексте.

        **Особая логика для УГОЛКА:**
        - Если видишь уголок с двумя числами, где второе число мало (меньше 20), например "уголок 75х6", "угол 75*6" или "уголок 75 6", **всегда** преобразуй это в два параметра: `"размер": "75x75"` и `"толщина": "6"`.

        ---
        ПРИМЕР РАЗБОРА СЛОЖНОЙ СТРОКИ:
        Входной текст: "Балку 70Ш4 12М СТ3ПС5/СП5 57837 и Арматура ф20А500"
        Выходной JSON:
```json
        {{
            "positions": [
                {{
                    "original_query": "Балку 70Ш4 12М СТ3ПС5/СП5 57837",
                    "base_name": "балка",
                    "quantity": 1,
                    "unit": "шт",
                    "params": {{
                        "номер": "70",
                        "тип": "ш4",
                        "длина": "12",
                        "марка стали": "3пс5/сп5",
                        "гост_ту": "57837"
                    }}
                }},
                {{
                    "original_query": "швеллер 16п",
                    "base_name": "швеллер",
                    "quantity": 1,
                    "unit": "шт",
                    "params": {{
                        "номер": "16",
                        "тип": "п"
                    }}
                }},
                {{
                    "original_query": "Арматура ф20А500",
                    "base_name": "арматура",
                    "quantity": 1,
                    "unit": "шт",
                    "params": {{
                        "диаметр": "20",
                        "класс": "а500"
                    }}
                }},
                {{
                    "original_query": "Стержень 12-А500С, ГОСТ 34028-2016",
                    "base_name": "арматура",
                    "quantity": 1,
                    "unit": "шт",
                    "params": {{
                        "диаметр": "12",
                        "класс": "а500с",
                        "гост_ту": "34028-2016"
                    }}
                }}
                {{
                    "original_query": "Стержень 12-А500С (L=410мм)",
                    "base_name": "арматура",
                    "quantity": 1,
                    "unit": "шт",
                    "params": {{
                        "диаметр": "12",
                        "класс": "а500с",
                        "длина": "0.41"
                    }}
                }}
            ]
        }}
        ```
        Не добавляй пояснений. Верни только JSON.
        """

        try:
            # ВАЖНО: Мы больше не используем .format(), так как переменная {text} уже вставлена в f-string
            response = self.model.generate_content(prompt, safety_settings=SAFETY_SETTINGS)
            
            if not response.parts:
                finish_reason_info = f"Finish reason: {response.prompt_feedback.block_reason}." if response.prompt_feedback else "Причина не указана."
                print(f"--- Ответ от Gemini был заблокирован. {finish_reason_info} ---")
                return []

            data = self._extract_json_from_response(response.text)

            if not data:
                return []

            positions = data.get('positions', [])
            
            if isinstance(positions, list):
                print(f"Gemini (gemini-1.5-flash-latest) распознал: {positions}")
                return positions
            
            print(f"--- Ошибка: Ключ 'positions' в ответе модели не является списком. Ответ: {data} ---")
            return []
                
        except Exception as e:
            print(f"Ошибка при обращении к Gemini API: {e}")
            return []