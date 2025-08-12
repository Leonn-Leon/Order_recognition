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

    # 2. Классифицируем ТРУБЫ
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
    

    CIRCLE_TRIGGERS = ['КРУГ', 'КР ', 'ПОКОВКА']
    if any(trigger in str(row[NAME_COLUMN]).upper() for trigger in CIRCLE_TRIGGERS):

        EXCLUSION_KEYWORDS_CIRCLE = [
            'АЛМАЗНЫЙ', 'ЛЕПЕСТКОВ', 'ОТРЕЗНОЙ', 'ШЛИФОВАЛЬН', 'ЗАЧИСТНОЙ', 'КОНЬК'
        ]
        if any(keyword in str(row[NAME_COLUMN]).upper() for keyword in EXCLUSION_KEYWORDS_CIRCLE):
            return None
        
        return 'круг'

    if 'арматура' in title_lower or title_lower.startswith('а '):
        return 'арматура'
    
    if 'уголок' in title_lower or title_lower.startswith('у '):
        return 'уголок'
        
    if 'лист' in title_lower or title_lower.startswith('л '):
        return 'лист'

    return None


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
                
                if value.endswith('.0'):
                    value = value[:-2]
                
                if 'длина' in param_name:
                    value = value.upper().replace('М', '')
                params[param_name] = value

    if 'длина' in params and params['длина'] == 'НЕЕР':
        params['длина'] = 'НЕМЕР'
    
    for key in ['длина', 'толщина']:
        alt_key = f"{key}_альт"
        if alt_key in params:
            if key not in params:
                params[key] = params[alt_key]
            del params[alt_key]

    title_lower = str(row[NAME_COLUMN]).lower()

    if base_name == 'труба_профильная':
        if 'размер_a' in params and 'размер_b' in params:
            params['размер'] = f"{params['размер_a']}x{params['размер_b']}"
            del params['размер_a']
            del params['размер_b']
        
        if 'нерж' in title_lower:
            params['металл'] = 'нержавеющая'
        else:
            params['металл'] = 'черный'
            
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
            params['тип'] = sorted(list(set(found_types)))

    elif base_name == 'уголок':
        # Собираем размер из двух полок
        if 'полка_a' in params and 'полка_b' in params:
            params['размер'] = f"{params['полка_a']}x{params['полка_b']}"
            del params['полка_a']
            del params['полка_b']

        title_upper = str(row[NAME_COLUMN]).upper()

        # 1. Определяем тип металла
        if 'НЕРЖ' in title_upper:
            params['металл'] = 'нержавеющая'
            
        # 2. Определяем тип уголка
        if 'ГН' in title_upper and 'тип' not in params:
            params['тип'] = 'гнутый' # ГН - гнутый
            
        # 3. Определяем состояние из названия
        if 'НЛГ' in title_upper and 'состояние' not in params:
            params['состояние'] = 'нлг'

    elif base_name == 'арматура':
        if 'терм' in title_lower and 'тип' not in params:
            params['тип'] = 'терм'
    
    elif base_name == 'швеллер':
            if 'номер' in params:
                params['номер'] = params['номер'].lower()
            if 'тип' in params:
                params['тип'] = params['тип'].lower()

    elif base_name == 'балка':
            if 'номер' in params:
                params['номер'] = params['номер'].lower()
            if 'тип' in params:
                params['тип'] = params['тип'].lower()
                
    elif base_name == 'круг':
        title_upper = str(row[NAME_COLUMN]).upper()

        # 1. Определяем тип металла
        if title_upper.startswith('КР НЕРЖ'):
            params['металл'] = 'нержавеющая'
        elif title_upper.startswith('КР АЛ'):
            params['металл'] = 'алюминий'
        elif title_upper.startswith('КР БР'):
            params['металл'] = 'бронза'
        elif title_upper.startswith('КР ЛАТ'):
            params['металл'] = 'латунь'
        elif title_upper.startswith('КР МЕД'):
            params['металл'] = 'медь'
        elif title_upper.startswith('КР ЧУГ'):
            params['металл'] = 'чугун'
        elif title_upper.startswith('КР ТИТАН'):
            params['металл'] = 'титан'

        # 2. Определяем тип обработки/свойства
        if 'КАЛИБР' in title_upper and 'тип' not in params:
            params['тип'] = 'калиброванный'
        if 'ВЛГ' in title_upper and 'тип' not in params:
            params['тип'] = 'высоколегированный'
        if 'КНСТР' in title_upper and 'тип' not in params:
            params['тип'] = 'конструкционный'
            
        # 3. Определяем покрытие и цвет
        if 'ОЦ' in title_upper and 'покрытие' not in params:
            params['покрытие'] = 'оцинкованный'
        elif 'ПОЛИМ' in title_upper and 'покрытие' not in params:
            params['покрытие'] = 'полимерное'

            ral_match = re.search(r'RAL(\d+)', title_upper)
            if ral_match:
                params['цвет_ral'] = ral_match.group(1)

    if 'состояние' not in params:
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
    
    df_filtered = df.dropna(subset=['base_name']).copy()
    print(f"Осталось {len(df_filtered)} релевантных позиций (арматура, уголок, трубы и т.д.).")

    print("\nЭтап 2: Извлечение и очистка параметров...")
    tqdm.pandas(desc="Извлечение параметров")
    df_filtered[['base_name_final', 'params_json']] = df_filtered.progress_apply(process_row, axis=1, result_type='expand')

    df_final = df_filtered.dropna(subset=['params_json']).copy()
    
    if df_final.empty:
        print("\nОШИБКА: Не найдено ни одной строки для сохранения. Проверьте правила и данные.")
        return

    df_final = df_final[[
        'Материал номер',
        NAME_COLUMN,
        'base_name_final',
        'params_json'
    ]]
    
    df_final = df_final.rename(columns={
        'Материал номер': 'Материал',
        NAME_COLUMN: 'Полное наименование материала',
        'base_name_final': 'base_name'
    })
    
    print("\nСортировка данных для сохранения...")
    df_final = df_final.sort_values(by=['base_name', 'Полное наименование материала'])
    
    print(f"\nСохранение {len(df_final)} обработанных позиций в {OUTPUT_FILE}...")
    df_final.to_csv(OUTPUT_FILE, index=False, encoding='utf-8')
    print("Готово!")

if __name__ == '__main__':
    main()