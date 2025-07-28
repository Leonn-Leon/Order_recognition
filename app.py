# app.py
import streamlit as st
import pandas as pd
import os
from threading import Lock
import re
import json
import html

from order_recognition.core.gemini_parser import GeminiParser
from order_recognition.core.distance import Find_materials
from order_recognition.core.worker import WEIGHTS
from order_recognition.core.utils import normalize_param

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
    оставляя весь заказ нетронутым. Гарантированно превращает текст в одну строку.
    """
    lines = prompt_text.split('\n')
    
    # 1. Находим, с какой строки начинается подпись
    signature_start_index = -1
    signature_triggers = ['с уважением', 'с наилучшими', 'директор', 'менеджер', 'mercury', 'golos.click', 'amineva', 'отдел снабжения']
    for i, line in enumerate(lines):
        if line.strip() in ['--', '–', '—'] or any(trigger in line.lower() for trigger in signature_triggers):
            signature_start_index = i
            break
            
    # 2. Если подпись найдена, обрезаем все строки, начиная с нее
    if signature_start_index != -1:
        lines = lines[:signature_start_index]
        
    # 3. Соединяем строки обратно в единый текст
    cleaned_text = '\n'.join(lines)
    
    # 4. ЗАМЕНЯЕМ НЕНАДЕЖНОЕ РЕГУЛЯРНОЕ ВЫРАЖЕНИЕ НА БОЛЕЕ НАДЕЖНЫЙ МЕТОД
    # Этот метод разбивает строку по ЛЮБЫМ пробельным символам (пробелы, табы, переносы строк)
    # и затем соединяет обратно через один пробел. Это гарантирует результат в одну строку.
    single_line_text = " ".join(cleaned_text.split())

    return single_line_text


def highlight_text(material_row: pd.Series, query_params: dict) -> str:
    """
    ФИНАЛЬНАЯ ВЕРСИЯ С ЦВЕТОВОЙ СХЕМОЙ.
    Подсвечивает каждый параметр в названии товара в соответствии с его статусом:
    - Зеленый: полное совпадение.
    - Салатовый: частичное совпадение.
    - Оранжевый: несоответствие (запросили одно, в товаре другое).
    - Желтый: лишний параметр (в товаре есть, в запросе нет).
    """
    full_name = material_row['Полное наименование материала']
    try:
        material_params = json.loads(material_row['params_json'])
    except (json.JSONDecodeError, TypeError):
        return html.escape(full_name)

    if not query_params and not material_params:
        return html.escape(full_name)

    SYNONYMS = {
        "тип": {
            "гнутый": "ГН"
        }
        # Сюда можно будет добавлять другие синонимы, если потребуется
    }
    
    # --- Цветовая схема ---
    param_colors = {
        "match": "#7DCEA0",          # Ярко-зеленый
        "partial": "#DAF7A6",        # Салатовый
        "mismatch": "#F5B041",       # Оранжевый
        "excess": "gold",            # Желтый
    }

    highlights = {}

    # --- ЭТАП 1: Определяем статус для каждого параметра в НАЙДЕННОМ ТОВАРЕ ---
    for param_name, material_value in material_params.items():
        query_value = query_params.get(param_name)
        
        # Пропускаем пустые значения
        if not material_value or str(material_value).strip() in ['', '##']:
            continue

        status = None
        
        if query_value:
            # Параметр был в запросе - проверяем совпадение
            norm_q = normalize_param(str(query_value))
            norm_m = normalize_param(str(material_value))

            if norm_q == norm_m:
                status = "match"
            elif (param_name in ['гост_ту', 'марка стали', 'класс']) and (norm_q in norm_m):
                status = "partial"
            else:
                status = "mismatch"
        else:
            # Параметра не было в запросе - он лишний
            status = "excess"
        
        # Для сложных значений (размер, несколько марок стали) разбиваем на части
        parts_to_highlight = set()
        raw_parts = re.split(r'[ ,/хx*-]', str(material_value))
        for p in raw_parts:
            if p:
                parts_to_highlight.add(p.strip())

        # <<< НАЧАЛО НОВОГО БЛОКА: Добавляем синонимы в подсветку >>>
        if param_name in SYNONYMS and material_value in SYNONYMS[param_name]:
            parts_to_highlight.add(SYNONYMS[param_name][material_value])
        # <<< КОНЕЦ НОВОГО БЛОКА >>>

        for part in parts_to_highlight:
            highlights[part] = param_colors[status]

    # --- ЭТАП 2: Применяем подсветку к строке ---
    # Разбиваем название на слова и символы-разделители
    tokens = re.split(r'([\s,/хx*()-]+)', full_name)
    output_parts = []

    for token in tokens:
        norm_token = token.strip()
        color = highlights.get(norm_token) # Сначала ищем точное совпадение (например, для "СТ20")

        # Если точного совпадения нет, пробуем "очистить" токен от буквы "М" и поискать снова
        if not color:
            length_norm_token = norm_token.upper().replace('М', '')
            if length_norm_token in highlights:
                color = highlights[length_norm_token]

        if color:
            # Если нашли совпадение любым способом, подсвечиваем исходный токен
            output_parts.append(
                f'<span style="background-color: {color}; color: #1E1E1E; padding: 1px 4px; border-radius: 4px; font-weight: bold;">{html.escape(token)}</span>'
            )
        else:
            output_parts.append(html.escape(token))

    return "".join(output_parts)

def generate_styled_tooltip(query_params: dict, material_id: str, finder) -> str:
    """
    ФИНАЛЬНАЯ, ПОЛНОСТЬЮ СИНХРОНИЗИРОВАННАЯ ВЕРСИЯ.
    Генерирует HTML-блок, ТОЧНО повторяя ВСЮ логику скоринга из worker.py.
    """
    try:
        material_row = finder.all_materials[finder.all_materials['Материал'] == material_id].iloc[0]
        material_params = json.loads(material_row['params_json'])
    except (IndexError, json.JSONDecodeError, TypeError):
        return "Не удалось загрузить данные для подсказки."

    if not query_params: return "Нет параметров для сравнения."

    # --- Подтягиваем константы для расчета, чтобы они были в одном месте ---
    MISMATCH_PENALTY_FACTOR = 1.0
    MISSING_PARAM_PENALTY_FACTOR = 1.2
    EXCESS_PARAM_PENALTY = 15
    HIDDEN_CONDITION_PENALTY = 50
    PARTIAL_MATCH_BONUS_FACTOR = 0.6 # Начисляем 60% от веса за частичное совпадение
    EXCESS_PARAM_PENALTY_FACTOR = 0.3 # Штраф = 30% от веса лишнего параметра

    # --- ЭТАП 1: Расчет максимально возможного балла ---
    max_possible_score = sum(WEIGHTS.get(p, WEIGHTS['default']) for p in query_params)
    if max_possible_score <= 0: return "Неверные параметры запроса."

    actual_score = 0
    bonus_lines = []
    penalty_lines = []

    # --- ЭТАП 2: Анализируем ЗАПРОШЕННЫЕ параметры ---
    for param_name, query_value in query_params.items():
        weight = WEIGHTS.get(param_name, WEIGHTS['default'])
        material_value = material_params.get(param_name)

        # Случай 1: Параметр есть и в запросе, и в товаре. Сравниваем.
        if material_value and str(material_value).strip() not in ['', '##']:
            is_matched = False
            bonus_multiplier = 0.0

            # --- Логика сравнения (остается без изменений) ---
            if param_name == 'марка стали':
                norm_q = normalize_param(str(query_value))
                norm_m = normalize_param(str(material_value))
                if norm_q == norm_m:
                    is_matched = True; bonus_multiplier = 1.0
                    
            elif param_name == 'состояние':
                norm_q = normalize_param(str(query_value))
                norm_m = normalize_param(str(material_value))
                # Проверяем, что одна строка содержится в другой
                if norm_q in norm_m or norm_m in norm_q:
                    is_matched = True
                    bonus_multiplier = 1.0
                    
            else:
                query_set = {normalize_param(str(v)) for v in query_value} if isinstance(query_value, list) else {normalize_param(str(query_value))}
                material_set = {normalize_param(str(v)) for v in material_value} if isinstance(material_value, list) else {normalize_param(str(material_value))}
                if query_set.issubset(material_set):
                    is_matched = True; bonus_multiplier = 1.0
            
            # --- Логика начисления бонусов и штрафов ---
            if is_matched:
                bonus_points = int(weight * bonus_multiplier)
                actual_score += bonus_points
                bonus_text = f'+ {bonus_points}</span> за "{param_name}"'
                if bonus_multiplier < 1.0 and bonus_multiplier > 0:
                    bonus_text += ' (частично)'
                bonus_lines.append(f'<span style="color: {"#7DCEA0" if bonus_multiplier == 1.0 else "#DAF7A6"};">{bonus_text}')
            else:
                is_partial_match = False
                if param_name in ['гост_ту', 'марка стали', 'класс']:
                    norm_q = normalize_param(str(query_value))
                    norm_m = normalize_param(str(material_value))
                    if norm_q in norm_m:
                        is_partial_match = True

                if is_partial_match:
                    bonus_points = int(weight * PARTIAL_MATCH_BONUS_FACTOR)
                    actual_score += bonus_points
                    bonus_lines.append(f'<span style="color: #DAF7A6;">+ {bonus_points}</span> за "{param_name}" (частично)')
                else:
                    penalty_points = int(weight * MISMATCH_PENALTY_FACTOR)
                    actual_score -= penalty_points
                    penalty_lines.append(f'<span style="color: #F5B041;">- {penalty_points}</span> за несоответствие "{param_name}"') 

        # Случай 2: Параметр был в запросе, но ОТСУТСТВУЕТ в товаре.
        else:
            # <<< НОВЫЙ БЛОК 2: ШТРАФ ЗА ОТСУТСТВИЕ (MISSING) >>>
            penalty_points = int(weight * MISSING_PARAM_PENALTY_FACTOR)
            actual_score -= penalty_points
            penalty_lines.append(f'<span style="color: #EC7063;">- {penalty_points}</span> за отсутствие "{param_name}"')

    # --- ЭТАП 3: Штрафуем за ЛИШНИЕ параметры (этот блок у вас был и он корректен) ---
    for material_param_name in material_params:
        if material_param_name not in query_params and material_param_name != 'состояние':
            weight = WEIGHTS.get(material_param_name, WEIGHTS['default'])
            actual_score -= int(weight * EXCESS_PARAM_PENALTY_FACTOR)
            penalty_points = int(weight * EXCESS_PARAM_PENALTY_FACTOR)
            penalty_lines.append(f'<span style="color: gold;">- {penalty_points}</span> за лишний "{material_param_name}"')
    
    # --- ЭТАП 4: Штраф за "скрытое" состояние (этот блок у вас был и он корректен) ---
    if 'состояние' not in query_params and material_params.get('состояние'):
        condition = material_params["состояние"]
        actual_score -= HIDDEN_CONDITION_PENALTY
        penalty_lines.append(f'<span style="color: #E74C3C; font-weight: bold;">- {HIDDEN_CONDITION_PENALTY}</span> за скрытое состояние: {condition}')

    # --- ЭТАП 5: Формирование HTML (без изменений) ---
    final_score = max(0, actual_score)
    percentage = (final_score / max_possible_score) * 100

    bonuses_html = "<b>Бонусы:</b><br>" + ("<br>".join(bonus_lines) if bonus_lines else "Нет")
    penalties_html = "<b>Штрафы:</b><br>" + ("<br>".join(penalty_lines) if penalty_lines else "Нет")
    
    formula_html = f"""
    <hr style="margin: 5px 0; border-color: #444;">
    <b>Расчет:</b><br>
    Итоговый балл: {final_score}<br>
    Максимум: {max_possible_score}<br>
    <b>({final_score} / {max_possible_score}) * 100 = {int(percentage)}%</b>
    """
    
    return f"{bonuses_html}<br><br>{penalties_html}{formula_html}"

def format_params_to_string(params: dict) -> str:
    """Превращает словарь параметров в красивую строку."""
    if not params:
        return "Нет распознанных параметров"
    order = ['диаметр', 'размер', 'толщина', 'номер', 'класс', 'марка стали', 'длина', 'тип', 'состояние']
    parts = [f"**{key.replace('_', ' ')}:** `{params[key]}`" for key in order if key in params]
    parts += [f"**{key.replace('_', ' ')}:** `{value}`" for key, value in params.items() if key not in order]
    return ' | '.join(parts)


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
                # Передаем всю строку DataFrame (result_df.iloc[0]), а не только имя
                highlighted_name = highlight_text(result_df.iloc[0], query_params)
                
                tooltip_content = generate_styled_tooltip(query_params, mat_id, finder)
                
                score_html = f'''
                <div class="tooltip-container">
                    Совпадение: {score}%
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

def handle_user_prompt(prompt: str, finder, gpt):
    """Обрабатывает запрос пользователя и выводит результат."""
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.spinner("Анализирую текст..."):
        # Шаг 1: Базовая очистка от подписей
        cleaned_prompt = clean_prompt_for_gemini(prompt)

        ##### ИЗМЕНЕНИЕ: ДОБАВЛЯЕМ ДВУХСТУПЕНЧАТУЮ ОБРАБОТКУ #####
        
        # Шаг 2: "Крупное сито" - просим Gemini удалить комментарии и "мусор"
        filtered_text = gpt.filter_material_positions(cleaned_prompt)
        
        # Шаг 3: "Мелкое сито" - отправляем очищенный текст на детальный разбор
        structured_positions = gpt.parse_order_text(filtered_text)
        ##### КОНЕЦ ИЗМЕНЕНИЯ #####

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