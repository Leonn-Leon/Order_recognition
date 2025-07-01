# debug_data.py
import pandas as pd
import json

# Теперь ID уже будет 18-значным
TARGET_MATERIAL_ID = '000000000000007939' 

try:
    df = pd.read_csv('order_recognition/data/mats_with_features.csv', dtype=str)
    
    # ИЗМЕНЕНИЕ: Нам больше не нужно дополнять нулями ID в скрипте,
    # так как они уже должны быть в файле. Мы просто ищем.
    
    target_row = df[df['Материал'] == TARGET_MATERIAL_ID]
    
    if not target_row.empty:
        print(f"--- Проверка данных для материала {TARGET_MATERIAL_ID} ---")
        
        base_name = target_row['base_name'].iloc[0]
        params_json = target_row['params_json'].iloc[0]
        
        print(f"  base_name в файле: {base_name}")
        print(f"  params_json в файле: {params_json}")
        
        try:
            params = json.loads(params_json)
            if 'размер' in params and 'толщина стенки' in params:
                print("\n[ВЕРДИКТ]: ✅ Данные выглядят ПРАВИЛЬНО. Проблема где-то еще.")
            else:
                print("\n[ВЕРДИКТ]: ❌ ОШИБКА! В файле отсутствуют 'размер' и/или 'толщина стенки'. Файл устарел!")
        except (json.JSONDecodeError, TypeError):
             print("\n[ВЕРДИКТ]: ❌ ОШИБКА! Поле params_json пустое или некорректное. Файл устарел!")

    else:
        print(f"ОШИБКА: Материал с ID {TARGET_MATERIAL_ID} не найден в mats_with_features.csv")

except FileNotFoundError:
    print("ОШИБКА: Файл 'order_recognition/data/mats_with_features.csv' не найден.")
except Exception as e:
    print(f"Произошла непредвиденная ошибка: {e}")