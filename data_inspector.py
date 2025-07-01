import pandas as pd

# Укажи правильный путь к твоему основному файлу с материалами
INPUT_FILE = 'order_recognition/data/mats.csv' 
# Если файл называется иначе или лежит в другом месте - поправь путь.

try:
    # Загружаем данные, предполагая, что заголовков нет
    df = pd.read_csv(INPUT_FILE, dtype=str, encoding='utf-8', header=None)
    
    # Даем столбцам временные имена, если их меньше 5, чтобы избежать ошибок
    num_columns = len(df.columns)
    df.columns = [f'col_{i}' for i in range(num_columns)]

    # Переименовываем основные столбцы, которые мы ожидаем увидеть
    # id, cat1, cat2, cat3, full_name
    column_map = {
        'col_0': 'id',
        'col_1': 'cat1',
        'col_2': 'cat2',
        'col_3': 'cat3',
        'col_4': 'full_name'
    }
    df.rename(columns={k: v for k, v in column_map.items() if k in df.columns}, inplace=True)
    
    print("--- 1. Общая информация о файле ---")
    print(f"Путь к файлу: {INPUT_FILE}")
    print(f"Всего строк: {len(df)}")
    print(f"Колонки: {df.columns.tolist()}")
    print("\n")

    # Проверяем, есть ли нужные колонки для анализа
    if 'cat1' in df.columns:
        print("--- 2. Анализ категорий верхнего уровня (cat1) ---")
        unique_cat1 = df['cat1'].unique()
        print(f"Уникальные значения ({len(unique_cat1)}): {unique_cat1.tolist()}")
        print("\n")
    
    if 'cat2' in df.columns:
        print("--- 3. Анализ подкатегорий (cat2) ---")
        unique_cat2 = df['cat2'].unique()
        print(f"Всего уникальных значений: {len(unique_cat2)}")
        print("Примеры (первые 30):")
        print(unique_cat2[:30].tolist())
        print("\n")

    if 'cat3' in df.columns:
        print("--- 4. Анализ самых детальных категорий (cat3) ---")
        unique_cat3 = df['cat3'].unique()
        print(f"Всего уникальных значений: {len(unique_cat3)}")
        print("Примеры (первые 30):")
        print(unique_cat3[:30].tolist())
        print("\n")

    print("--- 5. Примеры полных наименований для ключевых категорий ---")
    if 'cat2' in df.columns and 'full_name' in df.columns:
        # Найдем примеры для самых частых категорий
        top_categories = df['cat2'].value_counts().nlargest(10).index.tolist()
        
        for cat in top_categories:
            print(f"\nПримеры для категории '{cat}':")
            sample = df[df['cat2'] == cat]['full_name'].head(3).tolist()
            for s in sample:
                print(f"  - {s}")
    else:
        print("Не удалось найти колонки 'cat2' и 'full_name' для отображения примеров.")


except FileNotFoundError:
    print(f"ОШИБКА: Файл не найден по пути '{INPUT_FILE}'. Пожалуйста, проверь путь в скрипте.")
except Exception as e:
    print(f"Произошла непредвиденная ошибка: {e}")