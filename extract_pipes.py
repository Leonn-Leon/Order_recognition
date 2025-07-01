# extract_pipes.py
import pandas as pd

# --- НАСТРОЙКИ ---
INPUT_FILE = r'order_recognition/data/Материалы с признаками.xlsx' 
OUTPUT_FILE = 'order_recognition/data/all_pipes_only_FINAL.csv'

# Колонки для поиска
COLUMN_NAME = 'Материал название'
COLUMN_HIERARCHY = 'Иерархия 0 уровень'

# --- СЛОВАРИ ДЛЯ ФИЛЬТРАЦИИ ---

# 1. Ключевые слова, которые ДОЛЖНЫ БЫТЬ, чтобы строка считалась трубой
# Мы используем более точные паттерны, а не просто 'тр'
PIPE_PATTERNS = [
    'тр проф', 'тр бш', 'тр хд', 'тр эс', 'тр вгп', 'тр оц',
    'тр нкт', 'труба вт', 'труба обсадная', 'diy тр', 'труба пэ'
]

# 2. Слова-исключения. Если они есть в названии, строка ТОЧНО НЕ ТРУБА.
# Список значительно расширен на основе анализа файла.
EXCLUSION_KEYWORDS = [
    'держатель', 'держ', 'колено', 'соединитель', 'соед', 
    'тройник', 'тройн', 'заглушка', 'загл', 'хомут', 'кронштейн', 'крншт',
    'ключ', 'упаковка', 'резка', 'рез ', 'изготовл', 'гибка',
    'снегозадержатель', 'снегозад', 'адаптер', 'уплотн', 'заготовка', 'лом',
    'резистор', 'излучающ', 'кабель-канал', 'гофр', 'клин', 'зонт',
    'декор', 'шпилька', 'рубеж', 'огражд'
]

def main():
    print(f"Загрузка данных из: {INPUT_FILE}")
    try:
        df = pd.read_excel(INPUT_FILE, dtype=str).fillna('')
        print(f"Загружено {len(df)} строк.")
    except FileNotFoundError:
        print(f"ОШИБКА: Файл не найден по пути '{INPUT_FILE}'.")
        return
    except Exception as e:
        print(f"Произошла ошибка при чтении файла: {e}")
        return

    # Проверка наличия колонок
    for col in [COLUMN_NAME, COLUMN_HIERARCHY]:
        if col not in df.columns:
            print(f"ОШИБКА: В файле не найдена колонка '{col}'.")
            return

    # --- ЛОГИКА ФИЛЬТРАЦИИ ---

    # 1. Маска для строк, которые ПОТЕНЦИАЛЬНО являются трубами
    # Строка считается потенциальной трубой, если:
    # (А) в названии есть один из наших точных паттернов ИЛИ
    # (Б) в иерархии прямо написано 'Труба'
    pipe_regex = '|'.join(PIPE_PATTERNS)
    is_potentially_pipe = df[COLUMN_NAME].str.contains(pipe_regex, case=False) | \
                          (df[COLUMN_HIERARCHY] == 'Труба')
    
    print(f"Найдено {is_potentially_pipe.sum()} строк, потенциально являющихся трубами.")

    # 2. Маска для строк, которые ТОЧНО являются "мусором"
    # Строка считается мусором, если:
    # (А) в названии есть слово-исключение ИЛИ
    # (Б) в иерархии указана категория-исключение
    exclusion_regex = '|'.join(EXCLUSION_KEYWORDS)
    is_junk = df[COLUMN_NAME].str.contains(exclusion_regex, case=False) | \
              df[COLUMN_HIERARCHY].str.startswith('Услуги') | \
              (df[COLUMN_HIERARCHY] == 'КиФ')

    print(f"Из них {is_junk.sum()} строк похожи на мусор.")

    # 3. Финальная маска: ПОТЕНЦИАЛЬНО труба И (НЕ МУСОР)
    final_mask = is_potentially_pipe & ~is_junk
    
    df_final = df[final_mask]
    found_count = len(df_final)

    print(f"\nИтог: После финальной очистки осталось {found_count} строк.")
    
    if found_count > 0:
        try:
            df_final.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
            print(f"Чистый список труб успешно сохранен в файл: {OUTPUT_FILE}")
        except Exception as e:
            print(f"Произошла ошибка при сохранении файла: {e}")
    else:
        print("Подходящих строк для сохранения не найдено.")

if __name__ == '__main__':
    main()