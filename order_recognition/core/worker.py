# order_recognition/core/worker.py
import pandas as pd
import os
import json
import re
from .utils import normalize_param

# --- КОНФИГУРАЦИЯ СКОРИНГА (ВЕСА) ---
WEIGHTS = {
    # Самые важные (определяют геометрию)
    'диаметр': 300, 
    'размер': 300, 
    'металл': 280,
    'толщина': 250, 
    'класс': 250, 
    'номер': 250,

    # Средней важности (материал, свойства)
    'марка стали': 150,
    'тип': 70,
    'покрытие': 60,
    'цвет_ral': 50,
    
    # Наименее важные (длина, стандарты, состояние)
    'длина': 40,
    'гост_ту': 30, 
    'состояние': 20,

    'default': 10
}

##### ИЗМЕНЕНИЕ 1: Переносим иерархию сюда, так как логика теперь будет жить в воркере #####
# Список от наименее важного к наиболее важному.
SACRIFICE_HIERARCHY = [
    'цвет_ral', 'покрытие', 'гост_ту', 'состояние',
    'марка стали', 'тип', 'длина', 'класс',
    'номер', 'толщина', 'размер', 'диаметр',
]

# Новые константы для управления штрафами
# Штраф, если значения параметра НЕ СОВПАЛИ (например, длина 0.41 vs 11.7)
MISMATCH_PENALTY_FACTOR = 1.0 # Отнимаем 100% от веса параметра
# Штраф, если параметр был в запросе, но ОТСУТСТВУЕТ в товаре
MISSING_PARAM_PENALTY_FACTOR = 1.2 # Отнимаем 120% от веса параметра
# Штраф, если в товаре есть "скрытое" состояние (неконд, б/у), которое не просили
HIDDEN_CONDITION_PENALTY = 50

PARTIAL_MATCH_BONUS_FACTOR = 0.6 # Начисляем 60% от веса за частичное совпадение

EXCESS_PARAM_PENALTY_FACTOR = 0.3 # Штраф = 30% от веса лишнего параметра

worker_materials_with_features = None

def init_worker(csv_path: str, csv_encoding: str):
    global worker_materials_with_features
    print(f"--- Инициализация воркера (PID: {os.getpid()}) ---")
    try:
        worker_materials_with_features = pd.read_csv(csv_path, dtype=str, encoding=csv_encoding)
        worker_materials_with_features['Материал'] = worker_materials_with_features['Материал'].str.zfill(18)
    except FileNotFoundError:
        print(f"ОШИБКА В ВОРКЕРЕ: Файл с признаками не найден по пути {csv_path}")
        worker_materials_with_features = pd.DataFrame()

def parse_length_range(value: str) -> tuple[float, float] | None:
    match = re.search(r'(\d+\.?\d*)\s*-\s*(\d+\.?\d*)', value)
    if match: return (min(float(match.group(1)), float(match.group(2))), max(float(match.group(1)), float(match.group(2))))
    return None

def calculate_score(query_params: dict, material_params_json: str) -> int:
    """
    ФИНАЛЬНАЯ УЛУЧШЕННАЯ ВЕРСИЯ.
    - Дает бонусы за совпадения.
    - Штрафует за несоответствия, отсутствующие и лишние параметры.
    """
    try:
        material_params = json.loads(material_params_json)
    except (json.JSONDecodeError, TypeError):
        return 0

    if not query_params:
        return 0

    max_possible_score = sum(WEIGHTS.get(p, WEIGHTS['default']) for p in query_params)
    if max_possible_score <= 0: return 0

    actual_score = 0

    # --- ЭТАП 1: Анализируем ЗАПРОШЕННЫЕ параметры ---
    for param_name, query_value in query_params.items():
        weight = WEIGHTS.get(param_name, WEIGHTS['default'])
        material_value = material_params.get(param_name)

        # Случай 1: Параметр есть и в запросе, и в товаре. Сравниваем их.
        if material_value and str(material_value).strip() not in ['', '##']:
            is_matched = False
            bonus_multiplier = 0.0 # 1.0 для полного совпадения, 0.8 для частичного (сталь)

            # --- Логика сравнения ---
            if param_name == 'марка стали':
                norm_q = normalize_param(str(query_value))
                norm_m = normalize_param(str(material_value))
                if norm_q == norm_m:
                    is_matched = True; bonus_multiplier = 1.0
                    
            elif param_name == 'состояние':
                norm_q = normalize_param(str(query_value))
                norm_m = normalize_param(str(material_value))
                if norm_q in norm_m or norm_m in norm_q:
                    is_matched = True; bonus_multiplier = 1.0
                    
            else:
                query_set = {normalize_param(str(v)) for v in query_value} if isinstance(query_value, list) else {normalize_param(str(query_value))}
                material_set = {normalize_param(str(v)) for v in material_value} if isinstance(material_value, list) else {normalize_param(str(material_value))}
                if query_set.issubset(material_set):
                    is_matched = True; bonus_multiplier = 1.0
            # --- Конец логики сравнения ---

            if is_matched:
                actual_score += int(weight * bonus_multiplier)
            else:
                is_partial_match = False
                if param_name in ['гост_ту', 'марка стали', 'класс']:
                    norm_q = normalize_param(str(query_value))
                    norm_m = normalize_param(str(material_value))
                    if norm_q in norm_m:
                        is_partial_match = True

                if is_partial_match:
                    actual_score += int(weight * PARTIAL_MATCH_BONUS_FACTOR)
                else:
                    actual_score -= int(weight * MISMATCH_PENALTY_FACTOR)
            # <<< КОНЕЦ ЗАМЕНЫ >>>

        # Случай 2: Параметр был в запросе, но ОТСУТСТВУЕТ в товаре.
        else:
            actual_score -= int(weight * MISSING_PARAM_PENALTY_FACTOR) # ШТРАФ за отсутствие

    # --- ЭТАП 2: Штрафуем за ЛИШНИЕ (избыточные) параметры в товаре ---
    for material_param_name in material_params:
        if material_param_name not in query_params and material_param_name != 'состояние':
            weight = WEIGHTS.get(material_param_name, WEIGHTS['default'])
            actual_score -= int(weight * EXCESS_PARAM_PENALTY_FACTOR)

    # --- ЭТАП 3: Отдельный штраф за "скрытое" состояние ---
    if 'состояние' not in query_params and material_params.get('состояние'):
        actual_score -= HIDDEN_CONDITION_PENALTY

    # --- Финальный расчет ---
    final_score = max(0, actual_score) # Не даем уйти в минус
    percentage = (final_score / max_possible_score) * 100
    
    return int(percentage)


def _search_single_pass_in_worker(base_name: str, query_params: dict):
    """
    Вспомогательная функция для ОДНОГО прохода поиска внутри воркера.
    Возвращает словарь с результатами и лучшим скором.
    """
    candidates_df = worker_materials_with_features[worker_materials_with_features['base_name'] == base_name].copy()
    
    if candidates_df.empty:
        return {'best_score': -9999}

    candidates_df['score'] = candidates_df['params_json'].apply(
        lambda x: calculate_score(query_params, x)
    )
    
    top_results = candidates_df.sort_values(by="score", ascending=False).head(5)
    
    response_position = {}
    if not top_results.empty:
        response_position['best_score'] = top_results.iloc[0]['score']
    
    for i, (_, row_data) in enumerate(top_results.iterrows()):
        response_position[f'material{i+1}_id'] = row_data['Материал']
        response_position[f"weight_{i+1}"] = str(row_data['score'])
        
    return response_position

def process_one_task(task: dict):
    """
    ФИНАЛЬНАЯ ВЕРСИЯ. Выполняет исчерпывающий поиск по всем уровням "жертв"
    и возвращает абсолютно лучший из найденных результатов.
    """
    original_query = task.get('original_query', '')
    
    if worker_materials_with_features is None or worker_materials_with_features.empty:
        return {'request_text': original_query, 'error': 'База материалов не загружена в воркере'}

    base_name = task.get('base_name', '')
    original_params = task.get('params', {}).copy()
    
    # --- Шаг 1: Первый проход и инициализация лучшего результата ---
    best_result_so_far = _search_single_pass_in_worker(base_name, original_params)
    best_result_so_far['request_text'] = original_query
    
    # --- Шаг 2: Последовательно "жертвуем" параметрами ---
    params_to_sacrifice = original_params.copy()
    
    for param_to_remove in SACRIFICE_HIERARCHY:
        if param_to_remove in params_to_sacrifice:
            del params_to_sacrifice[param_to_remove]
            
            # Если параметров для поиска не осталось, выходим
            if not params_to_sacrifice:
                break
                
            current_result = _search_single_pass_in_worker(base_name, params_to_sacrifice)
            
            # --- Шаг 3: Сравнение и обновление лучшего результата ---
            # Сравниваем лучший балл из текущего прохода с лучшим из всех предыдущих
            # Примечание: 'weight_1' теперь содержит процент совпадения
            
            # Проверяем, есть ли вообще результаты в текущем проходе
            if 'weight_1' in current_result:
                # Если в "лучшем результате" еще нет ничего, или текущий результат лучше - обновляемся
                if 'weight_1' not in best_result_so_far or int(current_result['weight_1']) > int(best_result_so_far['weight_1']):
                    current_result['request_text'] = original_query
                    best_result_so_far = current_result
                    
    # --- Шаг 4: Возвращаем самый лучший из всех найденных результатов ---
    if 'best_score' in best_result_so_far:
        del best_result_so_far['best_score']
        
    return best_result_so_far