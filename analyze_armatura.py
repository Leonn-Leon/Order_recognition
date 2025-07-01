# analyze_armatura.py
import pandas as pd

# Загружаем наш отфильтрованный файл с арматурой
try:
    df_armatura = pd.read_excel('C:/Users/Hasee/Documents/AKSON/Order_recognition/order_recognition/data/Материалы с признаками.xlsx', dtype=str).fillna('')
except FileNotFoundError:
    print("Положи файл armatura_data.xlsx в папку со скриптом!")
    exit()

print(f"Анализируем {len(df_armatura)} позиций арматуры.\n")

# --- 1. АНАЛИЗ ДИАМЕТРА ---
# Предполагаем, что диаметр в 'Материал. Размер 1'
col_diametr = 'Материал. Размер 1'
if col_diametr in df_armatura:
    unique_diameters = df_armatura[col_diametr].unique()
    print(f"--- Диаметр (из '{col_diametr}') ---")
    print(f"Уникальные значения ({len(unique_diameters)}): {list(unique_diameters)}\n")

# --- 2. АНАЛИЗ КЛАССА ПРОЧНОСТИ (А500С, А240 и т.д.) ---
# Предполагаем, что класс в 'Материал. Признак 1'
col_class = 'Материал. Признак 1'
if col_class in df_armatura:
    unique_classes = df_armatura[col_class].str.lower().unique()
    print(f"--- Класс (из '{col_class}') ---")
    print(f"Уникальные значения ({len(unique_classes)}): {list(unique_classes)}\n")

# --- 3. АНАЛИЗ ДЛИНЫ ---
# Предполагаем, что длина в 'Материал. Размер 10'
col_length = 'Материал. Размер 10'
if col_length in df_armatura:
    unique_lengths = df_armatura[col_length].unique()
    print(f"--- Длина (из '{col_length}') ---")
    print(f"Уникальные значения ({len(unique_lengths)}): {list(unique_lengths)}\n")

# --- 4. АНАЛИЗ МАРКИ СТАЛИ (ст3, 09г2с и т.д.) ---
# Ищем, в какой колонке лежит марка стали
col_steel = 'Материал. Признак 8' # Это предположение, может быть другая
if col_steel in df_armatura and df_armatura[col_steel].nunique() > 1:
    unique_steels = df_armatura[col_steel].unique()
    print(f"--- Марка стали (из '{col_steel}') ---")
    print(f"Уникальные значения ({len(unique_steels)}): {list(unique_steels)}\n")

# --- 5. АНАЛИЗ ГОСТ/ТУ ---
col_gost = 'Материал. Признак 9' # Предположение
if col_gost in df_armatura and df_armatura[col_gost].nunique() > 1:
    unique_gosts = df_armatura[col_gost].unique()
    print(f"--- ГОСТ/ТУ (из '{col_gost}') ---")
    print(f"Уникальные значения ({len(unique_gosts)}): {list(unique_gosts)}\n")