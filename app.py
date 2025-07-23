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

def highlight_text(text: str, query_params: dict) -> str:
    """
    ФИНАЛЬНАЯ ВЕРСИЯ.
    Точно повторяет двойную логику сравнения из worker.py.
    """
    if not query_params:
        return text

    # 1. Подготовка значений из запроса для двух разных типов сравнения
    
    # Используем новую, единую функцию normalize_param
    exact_match_values = {
        normalize_param(str(v))
        for k, v in query_params.items()
        if k not in ['марка стали', 'размер']
    }

    steel_query_value = str(query_params.get('марка стали', '')).lower().replace('ст', '', 1).strip()

    size_parts = set()
    if 'размер' in query_params:
        # Используем новую, единую функцию normalize_param
        size_param = normalize_param(str(query_params['размер']))
        if 'x' in size_param:
            size_parts = set(size_param.split('x'))

    tokens_and_delimiters = re.split(r'([\w/.-]+)', text)

    output_parts = []
    for part in tokens_and_delimiters:
        if re.fullmatch(r'[\w/.-]+', part):
            should_highlight = False
            
            material_part_for_steel = part.lower().replace('ст', '', 1).strip()
            if steel_query_value and material_part_for_steel.startswith(steel_query_value):
                should_highlight = True
            else:
                # Используем новую, единую функцию normalize_param
                normalized_part = normalize_param(part)
                if normalized_part in exact_match_values or normalized_part in size_parts:
                    should_highlight = True
            
            if should_highlight:
                output_parts.append(f'<span style="background-color: #004D25; color: #E0E0E0; padding: 1px 4px; border-radius: 4px;">{part}</span>')
            else:
                output_parts.append(part)
        else:
            output_parts.append(part)

    return "".join(output_parts)

def generate_styled_tooltip(query_params: dict, material_id: str, finder) -> str:
    """
    ФИНАЛЬНАЯ ВЕРСИЯ. Генерирует HTML-блок, повторяя ВСЮ логику скоринга.
    """
    try:
        material_row = finder.all_materials[finder.all_materials['Материал'] == material_id].iloc[0]
        material_params = json.loads(material_row['params_json'])
    except (IndexError, json.JSONDecodeError, TypeError):
        return "Не удалось загрузить данные для подсказки."

    if not query_params:
        return "Нет параметров для сравнения."

    # --- ЭТАП 1: Расчет максимально возможного балла ---
    max_possible_score = 0
    for param_name in query_params:
        max_possible_score += WEIGHTS.get(param_name, WEIGHTS['default'])
    
    if max_possible_score <= 0:
        return "Неверные параметры запроса."

    # --- ЭТАП 2: Расчет фактического балла ---
    actual_score = 0
    
    # 2.1. Бонусы за совпадения
    bonus_lines = []
    for param_name, query_value in query_params.items():
        weight = WEIGHTS.get(param_name, WEIGHTS['default'])
        material_value = material_params.get(param_name)
        
        bonus_points = 0
        bonus_text = ""

        if material_value and str(material_value).strip() not in ['', '##']:
            q_val_str = str(query_value).lower().strip()
            m_val_str = str(material_value).lower().strip()
            
            if param_name == 'марка стали':
                norm_q = q_val_str.replace('ст', '', 1).strip()
                norm_m = m_val_str.replace('ст', '', 1).strip()
                if norm_q == norm_m:
                    bonus_points = weight
                    bonus_text = f'<span style="color: #7DCEA0;">+ {bonus_points}</span> за "{param_name}" (точно)'
                elif norm_m.startswith(norm_q):
                    bonus_points = int(weight * 0.8)
                    bonus_text = f'<span style="color: #DAF7A6;">+ {bonus_points}</span> за "{param_name}" (частично)'
            else:
                is_matched = False
                if param_name == 'тип':
                    if {t.strip() for t in q_val_str.split(',')}.issubset({t.strip() for t in m_val_str.split(',')}): is_matched = True
                elif param_name == 'длина':
                    if normalize_param(q_val_str) == normalize_param(m_val_str): is_matched = True
                    else:
                        try:
                            if float(q_val_str.replace('м', '')) == float(m_val_str.replace('м', '')): is_matched = True
                        except ValueError: pass
                else:
                    if normalize_param(q_val_str) == normalize_param(m_val_str): is_matched = True
                
                if is_matched:
                    bonus_points = weight
                    bonus_text = f'<span style="color: #7DCEA0;">+ {bonus_points}</span> за "{param_name}"'
        
        if bonus_points > 0:
            actual_score += bonus_points
            bonus_lines.append(bonus_text)


    # 2.2. Штрафы за избыточность и "скрытое" состояние
    penalty_lines = []
    EXCESS_PARAM_PENALTY = 15
    for material_param_name, material_param_value in material_params.items():
        if material_param_name not in query_params:
            if material_param_value and str(material_param_value).strip() not in ['', '##']:
                # ----> ВОТ ТО САМОЕ ИЗМЕНЕНИЕ <----
                if material_param_name != 'состояние': # Применяем обычный штраф ко всем, КРОМЕ состояния
                    actual_score -= EXCESS_PARAM_PENALTY
                    penalty_lines.append(f'<span style="color: #F1948A;">- {EXCESS_PARAM_PENALTY}</span> за лишний "{material_param_name}"')
                # ----> КОНЕЦ ИЗМЕНЕНИЯ <----

    # Штраф за "скрытое" состояние (НЛГ, НЕКОНД и т.д.)
    HIDDEN_CONDITION_PENALTY = 50
    if 'состояние' not in query_params:
        material_condition = material_params.get('состояние')
        if material_condition and str(material_condition).strip() not in ['', '##']:
            actual_score -= HIDDEN_CONDITION_PENALTY
            penalty_lines.append(f'<span style="color: #F1948A;">- {HIDDEN_CONDITION_PENALTY}</span> за скрытое состояние: {material_condition}')

    # --- ЭТАП 3: Формирование текста для подсказки ---
    final_score = max(0, actual_score)
    percentage = (final_score / max_possible_score) * 100
    
    bonuses_html = "<b>Бонусы за совпадения:</b><br>" + ("<br>".join(bonus_lines) if bonus_lines else "Нет")
    penalties_html = "<b>Штрафы:</b><br>" + ("<br>".join(penalty_lines) if penalty_lines else "Нет") # Переименовал для общности
    
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