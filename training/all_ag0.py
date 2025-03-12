import pandas as pd

# Загружаем CSV-файл
file_path = "order_recognition/data/mats.csv"  # Укажите путь к файлу, если он в другой директории
df = pd.read_csv(file_path)

# Проверяем, есть ли нужный столбец
if "Название иерархии-0" in df.columns:
    # Получаем уникальные значения из столбца "Название иерархии-0"
    unique_hierarchy_0 = df["Название иерархии-0"].unique()
    print(len(unique_hierarchy_0))
    
    # Выводим найденные уникальные иерархии
    print("Иерархии 0 уровня:")
    for hierarchy in unique_hierarchy_0:
        print(hierarchy)
else:
    print("Ошибка: столбец 'Название иерархии-0' не найден в файле.")
