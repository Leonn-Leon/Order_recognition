# order_recognition/core/worker.py
import pandas as pd
import os
import json
import re

# --- КОНФИГУРАЦИЯ СКОРИНГА (ТОЛЬКО ВЕСА) ---
WEIGHTS = {
    # Самые важные (определяют геометрию)
    'диаметр': 300, 
    'размер': 300, 
    'толщина': 250, 
    'класс': 250, 
    'номер': 250,

    # Средней важности (материал, свойства)
    'марка стали': 150,
    'тип': 70,              # Важно для (оц, вгп, х/к)
    'покрытие': 60,         # ПЭ
    'цвет_ral': 50,
    
    # Наименее важные (длина, стандарты, состояние)
    'длина': 40,
    'гост_ту': 30, 
    'состояние': 20,        # неконд, б/у

    'default': 10           # Вес для любых других параметров
}
# --- КОНЕЦ КОНФИГУРАЦИИ ---


worker_materials_with_features = None


def init_worker(csv_path: str, csv_encoding: str):
    global worker_materials_with_features
    print(f"--- Инициализация воркера (PID: {os.getpid()}) ---")
    try:
        worker_materials_with_features = pd.read_csv(csv_path, dtype=str, encoding=csv_encoding)
        worker_materials_with_features['Материал'] = worker_materials_with_features['Материал'].str.zfill(18)
        print(f"--- Воркер (PID: {os.getpid()}) успешно инициализирован ---")
    except FileNotFoundError:
        print(f"ОШИБКА В ВОРКЕРЕ: Файл с признаками не найден по пути {csv_path}")
        worker_materials_with_features = pd.DataFrame()


def normalize_text_param(param_value: str) -> str:
    """
    "Пуленепробиваемая" нормализация для ТЕКСТОВЫХ параметров.
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


def parse_length_range(value: str) -> tuple[float, float] | None:
    """
    Вспомогательная функция. Ищет в строке диапазон вида '6-9' или '6.5 - 9.5'.
    Возвращает кортеж (min, max) или None, если диапазон не найден.
    """
    match = re.search(r'(\d+\.?\d*)\s*-\s*(\d+\.?\d*)', value)
    if match:
        min_val = float(match.group(1))
        max_val = float(match.group(2))
        return (min(min_val, max_val), max(min_val, max_val))
    return None


def calculate_score(query_params: dict, material_params_json: str) -> int:
    """
    ФИНАЛЬНАЯ ВЕРСИЯ.
    Унифицированная логика с "мягкой" проверкой марки стали и поддержкой диапазонов.
    """
    try:
        material_params = json.loads(material_params_json)
    except (json.JSONDecodeError, TypeError):
        return -9999

    if not query_params:
        return 0

    score = 0
    
    for param_name, query_value in query_params.items():
        material_value = material_params.get(param_name)
        weight = WEIGHTS.get(param_name, WEIGHTS['default'])
        
        is_matched = False
        
        if material_value and str(material_value).strip() not in ['', '##']:
            q_val_str = str(query_value).lower().strip()
            m_val_str = str(material_value).lower().strip()

            # >>>>> НАЧАЛО ИЗМЕНЕНИЙ >>>>>
            if param_name == 'тип':
                # И в запросе, и в базе могут быть несколько типов
                query_types = {t.strip() for t in q_val_str.split(',')}
                material_types = {t.strip() for t in m_val_str.split(',')}
                # Считаем совпадением, если все типы из запроса есть в базе
                if query_types.issubset(material_types):
                    is_matched = True

            if param_name == 'марка стали':
                norm_q = q_val_str.replace('ст', '', 1).strip()
                norm_m = m_val_str.replace('ст', '', 1).strip()
                if norm_m.startswith(norm_q):
                    is_matched = True
            
            elif param_name == 'длина':
                length_range = parse_length_range(q_val_str) # <-- ИСПРАВЛЕНО ЗДЕСЬ
                
                if length_range:
                    try:
                        material_len_float = float(m_val_str.replace('м', '').strip())
                        if length_range[0] <= material_len_float <= length_range[1]:
                            is_matched = True
                    except ValueError: pass
                else:
                    try:
                        if float(q_val_str.replace('м', '')) == float(m_val_str.replace('м', '')):
                            is_matched = True
                    except ValueError:
                        if q_val_str == m_val_str:
                            is_matched = True
            
            else:
                norm_query = normalize_text_param(q_val_str)
                norm_material = normalize_text_param(m_val_str)
                if norm_query == norm_material:
                    is_matched = True
        
        if is_matched:
            score += weight
        else:
            if material_value and str(material_value).strip() not in ['', '##']:
                score -= int(weight * 1.5)
            else:
                score -= weight
            
    return int(score)


def process_one_task(task: dict):
    original_query = task.get('original_query', '')
    base_name = task.get('base_name', '')
    query_params = task.get('params', {})

    if worker_materials_with_features is None or worker_materials_with_features.empty:
        return {'request_text': original_query, 'error': 'База материалов не загружена в воркере'}

    candidates_df = worker_materials_with_features[
        worker_materials_with_features['base_name'] == base_name
    ].copy()

    if candidates_df.empty:
        return {'request_text': original_query}

    candidates_df['score'] = candidates_df['params_json'].apply(
        lambda x: calculate_score(query_params, x)
    )
    
    top_results = candidates_df.sort_values(by="score", ascending=False).head(5)

    response_position = {'request_text': original_query}
    for i, (_, row_data) in enumerate(top_results.iterrows()):
        response_position[f'material{i+1}_id'] = row_data['Материал']
        response_position[f"weight_{i+1}"] = str(row_data['score'])
        
    return response_position