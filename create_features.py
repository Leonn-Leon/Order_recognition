# scripts/create_features.py
import pandas as pd
import json
from tqdm import tqdm
from order_recognition.core.param_mapper import PARAM_MAP
import re

tqdm.pandas()

# --- Константы ---
INPUT_FILE = 'order_recognition/data/Материалы с признаками.xlsx'
OUTPUT_FILE = 'order_recognition/data/mats_with_features.csv'
NAME_COLUMN = 'Материал название'
HIERARCHY_COLUMN = 'Иерархия 0 уровень'
NULL_VALUE = "##"

def get_base_name(row):
    """
    Определяет базовое имя товара по его названию и иерархии.
    Сначала отсекает мусор, потом классифицирует известные типы.
    """
    title_lower = str(row[NAME_COLUMN]).lower()
    
    # 1. Отсекаем мусор по ключевым словам. Если нашли - сразу выходим.
    EXCLUSION_KEYWORDS = [
        'держатель', 'держ', 'колено', 'соединитель', 'соед', 'тройник', 
        'заглушка', 'хомут', 'ключ', 'упаковка', 'резка', 'рез ', 
        'изготовл', 'снегозадержатель', 'адаптер', 'заготовка', 'лом', 
        'ассортимент', 'кабель-канал'
    ]
    if any(keyword in title_lower for keyword in EXCLUSION_KEYWORDS):
        return None

    # 2. Классифицируем ТРУБЫ (самые специфичные)
    if 'проф' in title_lower:
        return 'труба_профильная'
    
    ROUND_PIPE_KEYWORDS = [
        'тр бш', 'тр хд', 'тр эс', 'тр вгп', 'тр оц', 'тр нкт', 'труба вт', 
        'труба обсадная', 'diy тр'
    ]
    if any(keyword in title_lower for keyword in ROUND_PIPE_KEYWORDS):
        return 'труба_круглая'
    
    if str(row[HIERARCHY_COLUMN]) == 'Труба' and (' тр ' in title_lower or title_lower.startswith('труба ')):
         return 'труба_круглая'

    # 3. Классифицируем ШВЕЛЛЕР в первую очередь
    if 'двутавр' in title_lower or title_lower.startswith('б '):
        return 'балка'
    
    if 'швеллер' in title_lower or title_lower.startswith('шв '):
        return 'швеллер'
    
    if 'круг' in title_lower or title_lower.startswith('кр '):
        return 'круг'

    if 'арматура' in title_lower or title_lower.startswith('а '):
        return 'арматура'
    
    if 'уголок' in title_lower or title_lower.startswith('у '):
        return 'уголок'
        
    if 'лист' in title_lower or title_lower.startswith('л '):
        return 'лист'

    return None


# create_features.py

def process_row(row):
    """Извлекает и очищает параметры для ОДНОЙ строки на основе ее base_name."""
    base_name = row['base_name']
    
    if not base_name or base_name not in PARAM_MAP:
        return None, None 

    map_for_category = PARAM_MAP[base_name]
    
    params = {}
    for column_name, param_name in map_for_category.items():
        if column_name in row and pd.notna(row[column_name]):
            value = str(row[column_name]).strip()
            if value and value != NULL_VALUE:
                # Убираем ".0" из целых чисел, которые pandas мог прочитать как float
                if value.endswith('.0'):
                    value = value[:-2]
                
                if 'длина' in param_name:
                    value = value.upper().replace('М', '')
                params[param_name] = value

    # --- ПОСТОБРАБОТКА И УНИФИКАЦИЯ ПАРАМЕТРОВ ---
    
    # 1. Объединяем альтернативные поля...
    for key in ['длина', 'толщина']:
        alt_key = f"{key}_альт"
        if alt_key in params:
            if key not in params:
                params[key] = params[alt_key]
            del params[alt_key]

    # 2. Логика для конкретных base_name
    title_lower = str(row[NAME_COLUMN]).lower()

    if base_name == 'труба_профильная':
        if 'размер_a' in params and 'размер_b' in params:
            params['размер'] = f"{params['размер_a']}x{params['размер_b']}"
            del params['размер_a']
            del params['размер_b']
        
        # Определяем тип металла
        if 'нерж' in title_lower:
            params['металл'] = 'нержавеющая'
        else:
            params['металл'] = 'черный'
            
        # Дополнительно извлекаем тип обработки (х/к), если он есть
        if 'х/к' in title_lower and 'тип' not in params:
            params['тип'] = 'х/к'

    elif base_name == 'труба_круглая':
        if 'диаметр' in params:
            params['диаметр'] = params['диаметр'].lower().replace('ду', '').strip()
        
        found_types = []
        if 'тип' in params: found_types.append(params['тип'].lower())
        if 'вгп' in title_lower: found_types.append('вгп')
        if 'эс' in title_lower: found_types.append('эс')
        if 'оц' in title_lower or 'оцинк' in title_lower: found_types.append('оц')
        if 'бш' in title_lower: found_types.append('бш')
        if 'хд' in title_lower: found_types.append('хд')
        if 'изоляц' in str(row['Материал. Признак 2']).lower(): found_types.append('изоляц')

        if found_types:
            # Теперь мы сохраняем как список, чтобы соответствовать выводу Gemini
            params['тип'] = sorted(list(set(found_types)))

    elif base_name == 'уголок':
        if 'полка_a' in params and 'полка_b' in params:
            params['размер'] = f"{params['полка_a']}x{params['полка_b']}"
            del params['полка_a']
            del params['полка_b']

    elif base_name == 'арматура':
        if 'терм' in title_lower and 'тип' not in params:
            params['тип'] = 'терм'
    
    # >>>>> ИЗМЕНЕНИЕ 2: Улучшенная логика для швеллера и балки <<<<<
    elif base_name == 'швеллер':
            # Приводим все параметры к нижнему регистру для единообразия
            if 'номер' in params:
                params['номер'] = params['номер'].lower()
            if 'тип' in params:
                params['тип'] = params['тип'].lower()

    elif base_name == 'балка':
            # Приводим все параметры к нижнему регистру для единообразия
            if 'номер' in params:
                params['номер'] = params['номер'].lower()
            if 'тип' in params:
                params['тип'] = params['тип'].lower()

    ##### НОВЫЙ БЛОК: ОБЩАЯ ПРОВЕРКА НА СОСТОЯНИЕ ДЛЯ ВСЕХ ТИПОВ #####
    # Этот блок должен идти в конце, чтобы обработать все товары
    if 'состояние' not in params: # Проверяем, не было ли оно уже извлечено из колонки
        if 'неконд' in title_lower:
            params['состояние'] = 'неконд'
        elif 'нлг' in title_lower:
            params['состояние'] = 'нлг'
        elif 'б/у' in title_lower:
            params['состояние'] = 'б/у'
            
            
    if not params:
        return base_name, None

    params_json = json.dumps(params, ensure_ascii=False)
    return base_name, params_json

def main():
    print(f"Загрузка данных из {INPUT_FILE}...")
    df = pd.read_excel(INPUT_FILE, dtype=str).fillna('')
    print(f"Загружено {len(df)} всего строк.")
    
    print("\nЭтап 1: Классификация всех позиций...")
    tqdm.pandas(desc="Определение категорий")
    df['base_name'] = df.progress_apply(get_base_name, axis=1)
    
    # Отфильтровываем строки, для которых категория не определилась (мусор и ненужные нам товары)
    df_filtered = df.dropna(subset=['base_name']).copy()
    print(f"Осталось {len(df_filtered)} релевантных позиций (арматура, уголок, трубы и т.д.).")

    print("\nЭтап 2: Извлечение и очистка параметров...")
    tqdm.pandas(desc="Извлечение параметров")
    df_filtered[['base_name_final', 'params_json']] = df_filtered.progress_apply(process_row, axis=1, result_type='expand')

    # Финальная очистка: убираем строки, где не удалось извлечь параметры
    df_final = df_filtered.dropna(subset=['params_json']).copy()
    
    if df_final.empty:
        print("\nОШИБКА: Не найдено ни одной строки для сохранения. Проверьте правила и данные.")
        return

    # Шаг 1: Выбираем только нужные колонки, используя их ТЕКУЩИЕ, уникальные имена
    df_final = df_final[[
        'Материал номер',
        NAME_COLUMN,
        'base_name_final',
        'params_json'
    ]]
    
    # Шаг 2: Теперь, когда дубликатов нет, переименовываем выбранные колонки в финальные имена
    df_final = df_final.rename(columns={
        'Материал номер': 'Материал',
        NAME_COLUMN: 'Полное наименование материала',
        'base_name_final': 'base_name'
    })
    
        # >>>>> НАЧАЛО НОВОГО БЛОКА: СОРТИРОВКА ДАННЫХ <<<<<
    print("\nСортировка данных для сохранения...")
    df_final = df_final.sort_values(by=['base_name', 'Полное наименование материала'])
    # >>>>> КОНЕЦ НОВОГО БЛОКА <<<<<
    
    print(f"\nСохранение {len(df_final)} обработанных позиций в {OUTPUT_FILE}...")
    df_final.to_csv(OUTPUT_FILE, index=False, encoding='utf-8')
    print("Готово!")

if __name__ == '__main__':
    main()