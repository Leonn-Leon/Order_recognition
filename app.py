import streamlit as st
import pandas as pd
import os
from threading import Lock
import re

from order_recognition.core.gemini_parser import GeminiParser
from order_recognition.core.distance import Find_materials

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
    if base_name in ["арматура", "труба_круглая"] and "диаметр" not in params:
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
    if base_name == "швеллер" and "номер" not in params:
        return f"Для швеллера `{original_query}` не указан **номер**."
    # <<<<< КОНЕЦ ИЗМЕНЕНИЙ <<<<<

    return None

def normalize_for_highlighting(param_value: str) -> str:
    """
    "Пуленепробиваемая" нормализация, скопированная из worker.py.
    Используется, чтобы сравнивать яблоки с яблоками.
    """
    if not isinstance(param_value, str):
        return ""
    text = param_value.lower()
    text = text.replace('iii', '3').replace('ii', '2').replace('i', '1')
    replacements = {
        'а': 'a', 'с': 'c', 'е': 'e', 'о': 'o', 'р': 'p', 'х': 'x', 'к': 'k',
        '-': '', ' ': '', '.': '', '/': ''
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.strip()


def highlight_text(text: str, query_params: dict) -> str:
    """
    Финальная, надежная функция подсветки.
    Работает с повторяющимися параметрами.
    """
    if not query_params:
        return text

    # 1. Нормализуем все значения из запроса один раз для эффективности
    normalized_query_values = {normalize_for_highlighting(str(v)) for v in query_params.values()}
    
    # Отдельно обрабатываем "размер"
    size_parts = set()
    if 'размер' in query_params:
        size_param = normalize_for_highlighting(str(query_params['размер']))
        if 'x' in size_param:
            size_parts = set(size_param.split('x'))
            # Удаляем 'размер' из основного набора, чтобы не было двойной проверки
            normalized_query_values.discard(size_param)

    # 2. Разбиваем исходный текст на части: сами слова и разделители между ними
    tokens_and_delimiters = re.split(r'([\w/.-]+)', text)
    
    output_parts = []
    for part in tokens_and_delimiters:
        # Проверяем, является ли часть "словом" (а не пробелом или другим разделителем)
        if re.fullmatch(r'[\w/.-]+', part):
            normalized_part = normalize_for_highlighting(part)
            
            # Проверяем, совпадает ли слово с простым параметром или с частью "размера"
            if normalized_part in normalized_query_values or normalized_part in size_parts:
                # Если да, оборачиваем его в тег для подсветки
                output_parts.append(f'<span style="background-color: #004D25; color: #E0E0E0; padding: 1px 4px; border-radius: 4px;">{part}</span>')
            else:
                # Если нет, добавляем как есть
                output_parts.append(part)
        else:
            # Разделители (пробелы и т.д.) просто добавляем как есть
            output_parts.append(part)
            
    # 3. Соединяем все части обратно в одну строку HTML
    return "".join(output_parts)

def format_params_to_string(params: dict) -> str:
    """Превращает словарь параметров в красивую строку."""
    if not params:
        return "Нет распознанных параметров"
    order = ['диаметр', 'размер', 'толщина', 'номер', 'класс', 'марка стали', 'длина', 'тип', 'состояние']
    parts = [f"**{key.replace('_', ' ')}:** `{params[key]}`" for key in order if key in params]
    parts += [f"**{key.replace('_', ' ')}:** `{value}`" for key, value in params.items() if key not in order]
    return ' | '.join(parts)

def display_results(results_data, finder, query_params):
    """Отображает результаты с распознанными параметрами."""
    request_text = results_data.get('request_text', 'N/A')
    with st.container(border=True):
        st.markdown(f"**Исходный запрос:** `{request_text}`")
        st.markdown(f"**Распознано:** {format_params_to_string(query_params)}")
        st.divider()
        found_options = False
        for i in range(1, 6):
            mat_id = results_data.get(f'material{i}_id')
            score = results_data.get(f'weight_{i}')
            if not mat_id: continue
            result_df = finder.all_materials[finder.all_materials['Материал'] == mat_id]
            if not result_df.empty:
                full_name = result_df['Полное наименование материала'].values[0]
                unique_key = f"confirm_{request_text}_{mat_id}_{i}"
                highlighted_name = highlight_text(full_name, query_params)
                col_info, col_action = st.columns([0.8, 0.2])
                with col_info:
                    st.markdown(f'<div style="display: flex; align-items: center; gap: 10px;"><span style="font-size: 0.9em; color: #A0A0A0;">Top {i}</span><span>{highlighted_name}</span></div><div style="font-size: 0.8em; color: #707070; padding-left: 38px;">ID: {mat_id} | Score: {score}</div>', unsafe_allow_html=True)
                with col_action:
                    if unique_key in st.session_state.get('confirmed_feedback', set()):
                        st.success("✔️", icon="✅")
                    else:
                        if st.button("Выбрать", key=unique_key, use_container_width=True):
                            if save_feedback(request_text, mat_id, full_name):
                                st.session_state.confirmed_feedback.add(unique_key)
                                st.rerun()
                            else:
                                st.error("Ошибка")
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
        structured_positions = gpt.parse_order_text(prompt)

    if not structured_positions:
        error_message = "К сожалению, не удалось распознать товарные позиции в вашем запросе."
        st.session_state.messages.append({"role": "assistant", "content": error_message})
        with st.chat_message("assistant"):
            st.error(error_message)
        return

    with st.chat_message("assistant"):
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

        for pos_request in structured_positions:
            pos_results = next((res for res in results_object.get('positions', []) if res['request_text'] == pos_request['original_query']), None)
            if pos_results:
                query_params = pos_request.get('params', {})
                st.session_state.messages.append({"role": "assistant", "content": {"type": "results", "data": pos_results, "query_params": query_params}})
                display_results(pos_results, finder, query_params)

# --- ОСНОВНОЕ ПРИЛОЖЕНИЕ STREAMLIT ---
def main():
    # Конфигурация страницы должна быть первым вызовом st
    st.set_page_config(page_title="Агент СПК", layout="centered")

    # Этот CSS блок теперь не нужен, так как layout="centered" делает все за нас.
    # st.markdown("""
    #     <style>
    #         ...
    #     </style>
    # """, unsafe_allow_html=True)
    
    st.title("🤖 Агент по обработке заказов СПК")
    st.caption("Введите запрос, я его разберу, задам уточняющие вопросы и подберу товары.")

    finder, gpt = load_services()

    # Инициализация истории чата
    if "messages" not in st.session_state: st.session_state.messages = []
    if "confirmed_feedback" not in st.session_state: st.session_state.confirmed_feedback = set()

    # Отображение старых сообщений из истории
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if isinstance(message["content"], dict) and message["content"].get("type") == "results":
                display_results(message["content"]["data"], finder, message["content"].get("query_params", {}))
            else:
                st.markdown(message["content"])

    # Поле ввода пользователя
    if prompt := st.chat_input("Введите заказ или ответьте на вопрос..."):
        handle_user_prompt(prompt, finder, gpt)

if __name__ == '__main__':
    main()