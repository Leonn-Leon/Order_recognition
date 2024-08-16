import pandas as pd
from distance import Find_materials
import subprocess
import re

file_path = 'data/Mats_with_eirar.csv'
data = pd.read_csv(file_path)
data = data[['Материал', 'Название иерархии-0',  'Название иерархии-1', 'Название иерархии-2', 'Полное наименование материала']]
# data['Полное наименование материала'] = data['Полное наименование материала'].str.replace('DIY', ' ')
data = data[~data['Полное наименование материала'].str.contains("DIY")]
fm = Find_materials()
data["Полное наименование материала"] = data["Полное наименование материала"].apply(
    fm.new_mat_prep)
# otgruzki = pd.read_csv('data/otgruzki.csv', sep=';')
# otgruzki['Код материала'] = otgruzki['Код материала'].apply(lambda x: str(int(x)))
data = data[~data['Полное наименование материала'].str.contains('НЕКОНД')]
data['Материал'] = data['Материал'].apply(str)
# data = data[data['Материал'].apply(lambda x: x in otgruzki['Код материала'].values)]
data.iloc[1:].to_csv('data/mats.csv', index=False)
##########################

# all_materials = pd.read_csv('data/mats5.csv')
# otgruzki = pd.read_csv('data/otgruzki.csv', sep=';')
# all_materials = all_materials[~all_materials['Полное наименование материала'].str.contains('НЕКОНД')]
# otgruzki['Код материала'] = otgruzki['Код материала'].apply(int)


# replaced_text = 'Уголок стальной 50х50х4 мм  50 м'
# part = 'стальн'
# pattern = r'\b'+part+r'[а-яё]*\b'
# matches = re.findall(pattern, replaced_text)
# for match in matches:
#     replaced_text = replaced_text.replace(match, '')
#
# print(replaced_text)