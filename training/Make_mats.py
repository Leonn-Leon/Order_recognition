import os

os.environ["PANDARALLEL_USE_TQDM_WIDGET"] = "0"

import pandas as pd

from pandarallel import pandarallel
from src.distance import Find_materials
fm = Find_materials()
import subprocess
import re


def main():
    # Инициализация pandarallel с прогресс-баром и увеличенным количеством потоков
    pandarallel.initialize(progress_bar=True, nb_workers=14)

    file_path = 'data/Mats_with_eirar.csv'
    data = pd.read_csv(file_path)
    print("Файл открыт")
    data = data[['Материал', 'Название иерархии-0', 'Название иерархии-1', 'Название иерархии-2',
                 'Полное наименование материала']]
    data = data[~data['Полное наименование материала'].str.contains("DIY")]
    data = data[~data['Полное наименование материала'].str.contains("Заготовка")]
    data = data[~data['Полное наименование материала'].str.contains('НЕКОНД')]
    print("Начинаем обрабатывать строки")

    data["Полное наименование материала"] = data["Полное наименование материала"].parallel_apply(fm.new_mat_prep)

    print("Сохраняем результат")
    data['Материал'] = data['Материал'].apply(str)
    data.iloc[1:].to_csv('data/mats.csv', index=False)


if __name__ == '__main__':
    main()
