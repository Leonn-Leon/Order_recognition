import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import SVC
import pickle
import os
from split_by_keys import Key_words

# Загрузка данных
data_path = 'data/for_zero.csv'
if not os.path.isfile(data_path):
    file_path = 'data/Mats_with_eirar.csv'
    data = pd.read_csv(file_path)
    print('Data opened!')
    # data = data[['Название иерархии-0', 'Полное наименование материала']]
    data['Полное наименование материала'] = data['Полное наименование материала'].str.replace('DIY', ' ')
    # data = data[~data['Полное наименование материала'].str.contains("DIY")]
    kw = Key_words()
    data["Полное наименование материала"] = data["Полное наименование материала"].apply(
        kw.split_numbers_and_words)
    data["Полное наименование материала"] = data["Полное наименование материала"].apply(lambda x: x.replace('профильная', 'проф'))
    data[['Название иерархии-0', 'Название иерархии-1', 'Полное наименование материала']].iloc[1:].to_csv(
        'data/for_firsts.csv', index=False)
    data = data[['Название иерархии-0', 'Полное наименование материала']]
    data.iloc[1:].to_csv('data/for_zero.csv', index=False)
else:
    print('Берём сохранённые данные')
    data = pd.read_csv(data_path)

# Выбор признаков и целевой переменной
X = data['Полное наименование материала']
y = data['Название иерархии-0']
all_zeros = sorted(list(set(data['Название иерархии-0'].to_list())))
y = [all_zeros.index(i) for i in y]

# Преобразование текстовых данных в числовые признаки с помощью TF-IDF
tfidf = TfidfVectorizer()
X_tfidf = tfidf.fit_transform(X)
print('TF-Idf Done!')

with open('data/main_model.pkl', 'rb') as f:
    model = pickle.load(f)

try:
    model.predict(X_tfidf[0:1])
    raise 'Обучать не надо'
except Exception as exc:
    print(exc)
    pass

# Метод опорных векторов
svm = SVC(random_state=42, kernel='linear', probability=True)
print('SVC start!')
svm.fit(X_tfidf, y)
with open('data/main_model.pkl', 'wb') as f:
    pickle.dump(svm, f)
print('Done!!!')
