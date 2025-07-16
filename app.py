import streamlit as st
import pandas as pd
import os
from threading import Lock
import re
import json
import html

from order_recognition.core.gemini_parser import GeminiParser
from order_recognition.core.distance import Find_materials
from order_recognition.core.worker import WEIGHTS, normalize_text_param
from order_recognition.core.worker import WEIGHTS

# --- КОНФИГУРАЦИЯ ---
OUTPUT_DIR = "output_data"
FEEDBACK_FILE = os.path.join(OUTPUT_DIR, "feedback.csv")
os.makedirs(OUTPUT_DIR, exist_ok=True)

file_lock = Lock()

# --- ФУНКЦИИ ---

@st.cache_resource
def load_services():
    """Загружает и кэширует тяжелые сервисы (модели, данные)."""
    print("--- ОДНОКРАТНАЯ ЗАГРУЗКА СЕРВИСОВ ---")
    try:
        finder_service = Find_materials()
        if finder_service.all_materials.empty:
            st.error("Критическая ошибка: не удалось загрузить базу материалов. Проверьте путь и наличие файла.")
            st.stop()
        gpt_service = GeminiParser()
        print("--- СЕРВИСЫ УСПЕШНО ЗАГРУЖЕНЫ ---")
        return finder_service, gpt_service
    except Exception as e:
        st.error(f"Критическая ошибка при загрузке сервисов: {e}")
        st.stop()

def save_feedback(original_query, correct_material_id, confirmed_material_name):
    """Сохраняет подтвержденный менеджером вариант в CSV."""
    new_feedback = pd.DataFrame(
        [[original_query, correct_material_id, confirmed_material_name]], 
        columns=['query', 'material_id', 'material_name']
    )
    with file_lock:
        try:
            file_exists = os.path.exists(FEEDBACK_FILE)
            new_feedback.to_csv(FEEDBACK_FILE, mode='a', header=not file_exists, index=False, encoding='utf-8')
            return True
        except Exception as e:
            print(f"Ошибка при сохранении фидбека: {e}")
            return False

def get_clarification_question(structured_position):
    """Формирует уточняющий вопрос, если не хватает данных."""
    base_name = structured_position.get("base_name")
    params = structured_position.get("params", {})
    original_query = structured_position.get('original_query', '')
    
    # >>>>> НАЧАЛО ИЗМЕНЕНИЙ >>>>>
    # Проверка для арматуры и круглой трубы
    if base_name in ["арматура", "труба_круглая", "круг"] and "диаметр" not in params:
        return f"Для позиции `{original_query}` не указан **диаметр**."
    
    # Проверка для листа
    if base_name == "лист" and "толщина" not in params:
        return f"Для листа `{original_query}` не указана **толщина**."
        
    # Проверка для профильной трубы (ДОБАВЛЯЕМ ЭТО)
    if base_name == "труба_профильная":
        if "размер" not in params:
            return f"Для профильной трубы `{original_query}` не указан **размер**."
        if "толщина" not in params:
            return f"Для профильной трубы `{original_query}` не указана **толщина** стенки."

    # Проверка для швеллера
    if base_name in ["швеллер", "балка"] and "номер" not in params:
        return f"Для {base_name.replace('_', ' ')} `{original_query}` не указан **номер**."

    return None

def clean_prompt_for_gemini(prompt_text: str) -> str:
    """
    Максимально аккуратно удаляет из текста только подписи и контакты,
    оставляя весь заказ нетронутым.
    """
    lines = prompt_text.split('\n')
    
    # 1. Находим, с какой строки начинается подпись
    signature_start_index = -1
    # Добавил "mercury" и другие триггеры из вашего примера
    signature_triggers = ['с уважением', 'с наилучшими', 'директор', 'менеджер', 'mercury', 'golos.click', 'amineva', 'отдел снабжения']
    for i, line in enumerate(lines):
        # Проверяем на наличие тире на пустой строке
        if line.strip() in ['--', '–', '—']:
             signature_start_index = i
             break
        if any(trigger in line.lower() for trigger in signature_triggers):
            signature_start_index = i
            break
            
    # 2. Если подпись найдена, обрезаем все строки, начиная с нее
    if signature_start_index != -1:
        lines = lines[:signature_start_index]
        
    # 3. Соединяем оставшиеся строки в один текст
    cleaned_text = '\n'.join(lines).strip()
    
    # >>>>> НАЧАЛО КЛЮЧЕВЫХ ИЗМЕНЕНИЙ <<<<<
    # 4. Заменяем все последовательности пробельных символов (пробелы, табы, и т.д.) на один пробел.
    # Это решает проблему "Invalid control character".
    # Также убираем лишние символы вроде "____"
    cleaned_text = re.sub(r'[\s_]+', ' ', cleaned_text)
    
    # 5. Можно добавить замену специфичных разделителей, если они есть
    # Например, если между позициями стоят `---`, их можно заменить на перенос строки
    # (в данном случае не требуется, но полезно для будущего)

    return cleaned_text.strip()

def normalize_for_highlighting(param_value: str) -> str:
    """
    "Пуленепробиваемая" нормализация. Должна быть идентична normalize_text_param в worker.py.
    """
    if not isinstance(param_value, str):
        return ""
    text = param_value.lower()
    text = text.replace('iii', '3').replace('ii', '2').replace('i', '1')
    
    replacements = {
        # Кириллица -> Латиница (важно для стали)
        'а': 'a', 'с': 'c', 'е': 'e', 'о': 'o', 
        'р': 'p', 'х': 'x', 'к': 'k', 'т': 't', 
        'у': 'y', 'в': 'b', 'м': 'm',
        
        # Удаление разделителей
        '-': '', ' ': '', '.': '', '/': ''
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.strip()


def highlight_text(text: str, query_params: dict) -> str:
    """
    ФИНАЛЬНАЯ ВЕРСИЯ.
    Точно повторяет двойную логику сравнения из worker.py.
    """
    if not query_params:
        return text

    # 1. Подготовка значений из запроса для двух разных типов сравнения
    
    # Значения для ТОЧНОГО совпадения после полной нормализации (все, кроме стали и размера)
    exact_match_values = {
        normalize_for_highlighting(str(v))
        for k, v in query_params.items()
        if k not in ['марка стали', 'размер']
    }
    
    # Значение для "мягкого" совпадения для стали (просто lower() и убрать 'ст')
    steel_query_value = str(query_params.get('марка стали', '')).lower().replace('ст', '', 1).strip()

    # Отдельная обработка для 'размера'
    size_parts = set()
    if 'размер' in query_params:
        size_param = normalize_for_highlighting(str(query_params['размер']))
        if 'x' in size_param:
            size_parts = set(size_param.split('x'))

    # 2. Разбиваем текст из базы данных на части и проверяем каждую
    tokens_and_delimiters = re.split(r'([\w/.-]+)', text)
    
    output_parts = []
    for part in tokens_and_delimiters:
        # ЭТА СТРОКА ИСПРАВЛЕНА
        if re.fullmatch(r'[\w/.-]+', part):
            should_highlight = False
            
            # --- Логика, зеркальная worker.py ---

            # Проверка №1: Особая логика для СТАЛИ
            # Сравниваем через .startswith, используя простое преобразование
            material_part_for_steel = part.lower().replace('ст', '', 1).strip()
            if steel_query_value and material_part_for_steel.startswith(steel_query_value):
                should_highlight = True
            
            # Проверка №2: Логика для ВСЕХ ОСТАЛЬНЫХ параметров
            # Сравниваем на точное равенство после полной нормализации
            else:
                normalized_part = normalize_for_highlighting(part)
                if normalized_part in exact_match_values or normalized_part in size_parts:
                    should_highlight = True
            
            # --- Конец логики ---

            if should_highlight:
                output_parts.append(f'<span style="background-color: #004D25; color: #E0E0E0; padding: 1px 4px; border-radius: 4px;">{part}</span>')
            else:
                output_parts.append(part)
        else:
            output_parts.append(part)
            
    return "".join(output_parts)

def generate_styled_tooltip(query_params: dict, material_id: str, finder) -> str:
    """
    Генерирует КОРРЕКТНЫЙ HTML-блок, полностью повторяя логику скоринга из worker.py.
    """
    try:
        material_row = finder.all_materials[finder.all_materials['Материал'] == material_id].iloc[0]
        material_params = json.loads(material_row['params_json'])
    except (IndexError, json.JSONDecodeError, TypeError):
        return ""

    lines = []
    
    for param, q_val in query_params.items():
        weight = WEIGHTS.get(param, WEIGHTS['default'])
        
        is_matched = False
        material_value = material_params.get(param)
        
        if material_value and str(material_value).strip() not in ['', '##']:
            q_val_str = str(q_val).lower().strip()
            m_val_str = str(material_value).lower().strip()

            # --- Дублируем логику из worker.py ---
            if param == 'тип':
                query_types = {t.strip() for t in q_val_str.split(',')}
                material_types = {t.strip() for t in m_val_str.split(',')}
                if query_types.issubset(material_types):
                    is_matched = True
            
            elif param == 'марка стали':
                norm_q = q_val_str.replace('ст', '', 1).strip()
                norm_m = m_val_str.replace('ст', '', 1).strip()
                if norm_m.startswith(norm_q):
                    is_matched = True
            
            elif param == 'длина':
                # Используем ту же самую надежную проверку
                if normalize_text_param(q_val_str) == normalize_text_param(m_val_str):
                    is_matched = True
                else:
                    try:
                        if float(q_val_str.replace('м', '')) == float(m_val_str.replace('м', '')):
                            is_matched = True
                    except ValueError: pass # Для подсказки сложный парсинг диапазона не нужен
            
            else: # Для всех остальных (номер, класс, размер...)
                if normalize_text_param(q_val_str) == normalize_text_param(m_val_str):
                    is_matched = True
        
        # --- Формируем строку для подсказки на основе результата ---
        if is_matched:
            lines.append(f'<span style="color: #7DCEA0;">+ {weight*2}</span> за совпадение "{param}"')
        else:
            # Пустой `material_value` или несовпадение - это всегда штраф
            pass # Штраф уже учтен в базовом скоре, просто не добавляем бонус

    # Соберем итоговый текст для подсказки
    # Формула: Score = (Сумма бонусов за совпадения) - (Сумма весов всех параметров в запросе)
    # Это полностью соответствует логике worker.py: score += (weight*2) и score -= weight
    
    bonuses = "<b>Бонусы:</b><br>" + "<br>".join(lines)
    
    penalties_list = [f'<span style="color: #F1948A;">- {WEIGHTS.get(p, 10)}</span> за "{p}"' for p in query_params.keys()]
    penalties = "<b>Штрафы (базовые):</b><br>" + "<br>".join(penalties_list)
    
    return f"{bonuses}<br><br>{penalties}"

def format_params_to_string(params: dict) -> str:
    """Превращает словарь параметров в красивую строку."""
    if not params:
        return "Нет распознанных параметров"
    order = ['диаметр', 'размер', 'толщина', 'номер', 'класс', 'марка стали', 'длина', 'тип', 'состояние']
    parts = [f"**{key.replace('_', ' ')}:** `{params[key]}`" for key in order if key in params]
    parts += [f"**{key.replace('_', ' ')}:** `{value}`" for key, value in params.items() if key not in order]
    return ' | '.join(parts)

# Файл: app.py

def display_results(results_data, finder, pos_request):
    """Отображает результаты с ПРОСТЫМ полем для ввода и БЕЗ кнопок 'Выбрать'."""

    query_params = pos_request.get('params', {})
    request_text = pos_request.get('original_query', 'N/A')
    detected_qty = pos_request.get('quantity', 1)
    detected_unit = pos_request.get('unit', 'шт')

    # CSS стили для подсказки остаются без изменений
    st.markdown("""
    <style>
        .tooltip-container {
            position: relative;
            display: inline-block;
            cursor: help;
            border-bottom: 1px dotted #A0A0A0;
        }
        .tooltip-text {
            visibility: hidden;
            width: 220px;
            background-color: #282C34; /* Темный фон */
            color: #E0E0E0; /* Светлый текст */
            text-align: left;
            border-radius: 6px;
            padding: 8px 12px;
            position: absolute;
            z-index: 1;
            bottom: 125%;
            left: 50%;
            margin-left: -110px; /* Половина ширины для центрирования */
            opacity: 0;
            transition: opacity 0.3s;
            font-size: 0.8em;
            border: 1px solid #444;
        }
        .tooltip-container:hover .tooltip-text {
            visibility: visible;
            opacity: 1;
        }
    </style>
    """, unsafe_allow_html=True)

    with st.container(border=True):
        
        # 1. Создаем уникальные ключи
        qty_key = f"qty_{request_text}"
        unit_key = f"unit_{request_text}"

        # 2. Инициализируем состояние
        if qty_key not in st.session_state:
            # Сохраняем как строку для st.text_input
            st.session_state[qty_key] = str(detected_qty) 
        if unit_key not in st.session_state:
            st.session_state[unit_key] = detected_unit

        # 3. Создаем колонки и виджеты
        col_info_header, col_qty, col_unit = st.columns([0.65, 0.2, 0.15])
        
        with col_info_header:
            st.markdown(f"**Исходный запрос:** `{request_text}`")
            st.markdown(f"**Распознано:** {format_params_to_string(query_params)}")

        # >>>>> ИЗМЕНЕНИЕ: ИСПОЛЬЗУЕМ ПРОСТОЕ ТЕКСТОВОЕ ПОЛЕ <<<<<
        with col_qty:
            st.text_input(
                "Кол-во",
                key=qty_key,
                label_visibility="collapsed"
            )

        with col_unit:
            st.selectbox(
                "Ед.изм.", options=['шт', 'т', 'кг', 'м'], key=unit_key,
                label_visibility="collapsed"
            )
        
        st.divider()
        
        found_options = False
        for i in range(1, 6):
            mat_id = results_data.get(f'material{i}_id')
            score = results_data.get(f'weight_{i}')
            if not mat_id: continue
            
            result_df = finder.all_materials[finder.all_materials['Материал'] == mat_id]
            if not result_df.empty:
                full_name = result_df['Полное наименование материала'].values[0]
                highlighted_name = highlight_text(full_name, query_params)
                
                tooltip_content = generate_styled_tooltip(query_params, mat_id, finder)
                
                score_html = f'''
                <div class="tooltip-container">
                    Score: {score}
                    <span class="tooltip-text">{tooltip_content}</span>
                </div>
                '''

                # >>>>> ИЗМЕНЕНИЕ: УБИРАЕМ КОЛОНКИ И КНОПКУ 'ВЫБРАТЬ' <<<<<
                st.markdown(
                    f'<div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">' # Добавил отступ
                    f'<span style="font-size: 0.9em; color: #A0A0A0;">Top {i}</span>'
                    f'<span>{highlighted_name}</span></div>'
                    f'<div style="font-size: 0.8em; color: #707070; padding-left: 38px;">'
                    f'ID: {mat_id} | {score_html}'
                    f'</div>',
                    unsafe_allow_html=True
                )
                
                found_options = True
        
        if not found_options:
            st.warning("_Не найдено подходящих вариантов для этой позиции._")
            
    st.write("")

def split_text_into_positions(text: str) -> list[str]:
    """
    Интеллектуально разделяет большой текст на отдельные товарные позиции.
    Удаляет мусор и подписи.
    """
    # 1. Удаляем все после явных признаков подписи
    signature_triggers = ['с уважением', 'с наилучшими', 'директор', 'менеджер']
    for trigger in signature_triggers:
        if trigger in text.lower():
            text = text.split(trigger)[0]
            break
            
    # 2. Удаляем контакты
    text = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '', text)
    text = re.sub(r'(\+7|8)[\s(-]*\d{3}[\s)-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}', '', text)
    
    # 3. Удаляем приветствия и общие фразы
    greeting_phrases = ['эльвира,', 'доброе утро!', 'добрый день!', 'прошу счет:']
    for phrase in greeting_phrases:
        text = text.replace(phrase, '')

    # 4. Основная логика разделения.
    # Мы ищем переносы строк, тире, которые часто отделяют позиции.
    # Также ищем ключевые слова, с которых начинается новая позиция.
    # Это регулярное выражение ищет перенос строки, за которым следует одно из ключевых слов.
    # (?=...) - это "lookahead", он находит место, но не включает сам разделитель в результат.
    keywords = ['арматура', 'лист', 'уголок', 'труба', 'проволока', 'швеллер']
    pattern = r'\n(?=[\s-]*(' + '|'.join(keywords) + '))'
    
    positions = re.split(pattern, text, flags=re.IGNORECASE)
    
    # Очищаем результат от пустых строк и лишних пробелов
    cleaned_positions = []
    for pos in positions:
        # Убираем лишние символы и проверяем, что строка не пустая
        cleaned_line = pos.strip(' \n\t-•,')
        if cleaned_line and cleaned_line.lower() not in keywords:
            cleaned_positions.append(cleaned_line)
            
    # Если разделение по ключевым словам не сработало, просто делим по строкам
    if not cleaned_positions or len(cleaned_positions) < 2:
        cleaned_positions = [line.strip(' \n\t-•,') for line in text.split('\n') if line.strip()]

    return cleaned_positions

def handle_user_prompt(prompt: str, finder, gpt):
    """Обрабатывает запрос пользователя и выводит результат."""
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.spinner("Анализирую текст..."):
        # Очищаем текст от подписей
        cleaned_prompt = clean_prompt_for_gemini(prompt)

        print("--- Очищенный промпт для Gemini ---")
        print(cleaned_prompt)

        # Отправляем ВЕСЬ очищенный текст в Gemini
        structured_positions = gpt.parse_order_text(cleaned_prompt)

    if not structured_positions:
        error_message = "К сожалению, не удалось распознать товарные позиции в вашем запросе. Проверьте консоль на предмет блокировки ответа."
        st.session_state.messages.append({"role": "assistant", "content": error_message})
        with st.chat_message("assistant"):
            st.error(error_message)
        return

    with st.chat_message("assistant"):
        # structured_positions - это уже готовый список словарей от Gemini
        questions_exist = any(get_clarification_question(pos) for pos in structured_positions)
        if questions_exist:
            st.markdown("##### Требуются уточнения:")
            for pos in structured_positions:
                question = get_clarification_question(pos)
                if question:
                    st.warning(f"🔸 {question}")
            st.divider()
        
        with st.spinner("Ищу товары в базе..."):
             results_object = finder.single_thread_rows(structured_positions)

        # Здесь логика остается той же, она уже рассчитана на работу со списком
    for pos_request in structured_positions:
        pos_results = next((res for res in results_object.get('positions', []) if res['request_text'] == pos_request['original_query']), None)
        if pos_results:
            # >>>>> ИЗМЕНЯЕМ ЭТУ СТРОКУ <<<<<
            # Раньше было: query_params = pos_request.get('params', {})
            st.session_state.messages.append({
                "role": "assistant",
                "content": {
                    "type": "results",
                    "pos_request": pos_request,  # Сохраняем весь объект запроса
                    "data": pos_results
                }
            }) 
            display_results(pos_results, finder, pos_request) # Передаем весь pos_request

# --- ОСНОВНОЕ ПРИЛОЖЕНИЕ STREAMLIT ---
def main():
    # Конфигурация страницы должна быть первым вызовом st
    st.set_page_config(page_title="Агент СПК", layout="centered")
    
        # >>>>> НАЧАЛО ИЗМЕНЕНИЙ: ДОБАВЛЯЕМ БЛОК СТИЛЕЙ <<<<<
    st.markdown("""
        <style>
            /* Импортируем современный шрифт из Google Fonts */
            @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700&display=swap');

            /* Стили для всей страницы */
            body {
                font-family: 'Montserrat', sans-serif;
            }
            
            /* Стили для главного заголовка (st.title) */
            h1 {
                font-family: 'Montserrat', sans-serif;
                font-size: 3rem; /* Делаем шрифт крупнее */
                font-weight: 700; /* Делаем жирнее */
                letter-spacing: -2px; /* Немного сжимаем буквы для стиля */
                text-align: center;
                margin-bottom: 0.5rem;
                /* Плавное появление */
                animation: fadeIn 0.8s ease-out;
            }

            /* Стили для подзаголовка (st.caption) */
            /* Мы используем такой сложный селектор, чтобы точно нацелиться на нужный элемент */
            [data-testid="stCaptionContainer"] > p {
                font-family: 'Montserrat', sans-serif;
                text-align: center;
                font-size: 1.1rem;
                color: #A0A0A0; /* Делаем текст сероватым, а не черным */
                margin-bottom: 3rem; /* Увеличиваем отступ снизу */
                animation: fadeIn 1.2s ease-out;
            }

            /* Анимация плавного появления */
            @keyframes fadeIn {
                from {
                    opacity: 0;
                    transform: translateY(-20px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
        </style>
    """, unsafe_allow_html=True)
    # <<<<< КОНЕЦ ИЗМЕНЕНИЙ <<<<<
    
    st.title("🤖  Агент по обработке заказов СПК")
    st.caption("Введите запрос...")

    finder, gpt = load_services()

    # Инициализация истории чата
    if "messages" not in st.session_state: st.session_state.messages = []
    if "confirmed_feedback" not in st.session_state: st.session_state.confirmed_feedback = set()

    # Отображение старых сообщений из истории
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            content = message["content"]
            if isinstance(content, dict) and content.get("type") == "results":
                # Извлекаем ВСЕ данные, которые мы сохранили на Шаге 1
                pos_request = content.get("pos_request")
                results_data = content.get("data")
                
                # Если все данные на месте, вызываем отрисовку
                if pos_request and results_data:
                    display_results(results_data, finder, pos_request)
            else:
                # Отрисовка обычных текстовых сообщений
                st.markdown(content)

    # Поле ввода пользователя (без изменений)
    if prompt := st.chat_input("Введите заказ или ответьте на вопрос..."):
        handle_user_prompt(prompt, finder, gpt)

if __name__ == '__main__':
    main()