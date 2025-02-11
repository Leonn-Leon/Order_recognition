import pandas as pd

df = pd.read_csv("order_recognition/data/mats.csv", index_col=0)

# Группируем данные
grouped = df.groupby('Название иерархии-0')['Название иерархии-1']

# Выводим результаты
for hierarchy_0, hierarchy_1 in grouped:
    print(f"Иерархия-0: {hierarchy_0}")
    print("Содержит Иерархии-1:")
    print(*hierarchy_1.unique(), sep="\n")
    print(f"Всего: {hierarchy_1.nunique()} уникальных элементов\n")
    print("-" * 50)