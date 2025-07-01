# scripts/generate_mapper.py
import pandas as pd
import json
import re
from tqdm import tqdm

# --- НАСТРОЙКИ ---
INPUT_FILE = r'C:\Users\Hasee\Documents\AKSON\Order_recognition\order_recognition\data\Материалы с признаками.xlsx' # <-- Убедись, что путь верный!
OUTPUT_FILE = 'order_recognition/core/param_mapper.py'
HIERARCHY_LEVEL_FOR_CATEGORY = 'Иерархия 2 уровень' # Колонка для определения категории товара
COLUMN_WITH_FULL_NAME = 'Материал название' # Колонка с полным текстовым названием
NULL_VALUE = "##"

# Словарь для нормализации и определения типа параметра.
# Ключ - осмысленное имя параметра.
# Значение - список regex-паттернов для поиска этого параметра в полном названии.
PARAM_REGEX_MAP = {
    'класс': [r'\b(а-?[ivx]+|а\d{3}с?|ат\d+)\b'],
    'марка стали': [r'\b(ст\s?)?(\d{1,2}[а-я]{1,3}[а-я0-9]{0,2})\b'],
    'гост_ту': [r'\b(гост|ту|сто)\b'],
    'длина': [r'\b\d+[\.,]?\d*\s?[мM]\b'],
    'диаметр': [r'\bф\s?\d+\b'],
    # ... можно добавлять более сложные правила
}

def find_all_params_in_text(text):
    """Находит все возможные параметры в текстовой строке с помощью regex."""
    found = {}
    text_lower = text.lower()
    for param_name, patterns in PARAM_REGEX_MAP.items():
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                # Запоминаем найденное значение, чтобы потом сравнивать
                found[param_name] = match.group(0).replace('ст', '').strip()
    return found

def main():
    print(f"Загрузка данных из {INPUT_FILE}...")
    try:
        df = pd.read_excel(INPUT_FILE, dtype=str)
    except FileNotFoundError:
        print(f"ОШИБКА: Файл не найден по пути: {INPUT_FILE}")
        print("Пожалуйста, исправьте путь в переменной INPUT_FILE в скрипте.")
        return

    # Заполняем пропуски, чтобы избежать ошибок
    df = df.fillna(NULL_VALUE)

    feature_cols = [col for col in df.columns if 'Материал. Признак' in col or 'Материал. Размер' in col]
    
    grouped = df.groupby(HIERARCHY_LEVEL_FOR_CATEGORY)
    final_map = {}

    print(f"Анализ {len(grouped)} категорий для создания карты сопоставления...")
    for category, group_df in tqdm(grouped):
        if len(group_df) < 10: continue # Пропускаем слишком маленькие категории

        # Для каждой категории находим все параметры в текстовом названии
        # и все значения в колонках с признаками
        text_params = find_all_params_in_text(" ".join(group_df[COLUMN_WITH_FULL_NAME]))
        
        category_map = {}
        for col_name in feature_cols:
            col_values_str = " ".join(v.lower() for v in group_df[col_name].unique() if v != NULL_VALUE)
            if not col_values_str: continue

            # Ищем, какому параметру из текста соответствуют значения в колонке
            for param_name, found_value in text_params.items():
                # Если значение из текста (например, "а500с") содержится в значениях колонки...
                if found_value in col_values_str:
                    category_map[col_name] = param_name
                    break # Нашли соответствие, переходим к следующей колонке

        if category_map:
            # Важный трюк: заменяем код категории на человеческое имя из колонки "Иерархия 3 уровень"
            # для большей читаемости. Берем первое попавшееся имя из группы.
            human_readable_category_name = group_df['Иерархия 3 уровень'].iloc[0]
            final_map[human_readable_category_name] = category_map

    print(f"Генерация завершена. Сохранение карты в {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("# -*- coding: utf-8 -*-\n")
        f.write("# АВТОМАТИЧЕСКИ СГЕНЕРИРОВАННАЯ КАРТА ПАРАМЕТРОВ\n")
        f.write("# Создана путем сопоставления значений из колонок с полным названием материала.\n\n")
        f.write("PARAM_MAP = ")
        f.write(json.dumps(final_map, ensure_ascii=False, indent=4))
    
    print("\nГотово! Создан файл:")
    print(f"===> {OUTPUT_FILE}")
    print("Теперь проверьте его и приступайте к следующему шагу.")

if __name__ == "__main__":
    main()