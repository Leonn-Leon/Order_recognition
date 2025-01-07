import pandas as pd

data = pd.read_csv('data/mats.csv')['Полное наименование материала'].to_list()
_dictionary = []
for line in data:
    words = line.split()
    for word in words:
        if word not in _dictionary:
            _dictionary += [word]

print(_dictionary)
pd.DataFrame(_dictionary, columns=['Filtered_Description']).to_csv('data/categories2.csv', index=False)
