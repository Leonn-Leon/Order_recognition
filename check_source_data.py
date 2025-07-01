# check_source_data.py
import pandas as pd

# ID нашей трубы
TARGET_MATERIAL_ID = '000000000000007939' 

try:
    # Загружаем ИСХОДНЫЙ файл
    df = pd.read_csv('order_recognition/data/mats.csv', dtype=str, encoding='utf-8', header=None)
    df.columns = ['id', 'cat1', 'cat2', 'cat3', 'full_name']
    
    # Находим нашу трубу
    target_row = df[df['id'] == TARGET_MATERIAL_ID]
    
    if not target_row.empty:
        print(f"--- Исходные данные для материала {TARGET_MATERIAL_ID} ---")
        print(target_row.to_markdown(index=False))
    else:
        print(f"ОШИБКА: Материал с ID {TARGET_MATERIAL_ID} не найден даже в исходном mats.csv")

except FileNotFoundError:
    print("ОШИБКА: Исходный файл 'order_recognition/data/mats.csv' не найден.")
except Exception as e:
    print(f"Произошла непредвиденная ошибка: {e}")