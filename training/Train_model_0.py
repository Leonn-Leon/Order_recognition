import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import SVC
import pickle
import os
from utils.split_by_keys import Key_words
import Train_model_1
import utils.Fit_method2 as Fit_method2
import pymorphy3


def new_mat_prep(new_mat: str):
    # new_mat = new_mat.replace('/', '')

    morph = pymorphy3.MorphAnalyzer()

    new_mat = ' '.join(new_mat.split())
    new_mat = Key_words().replace_words(new_mat)
    new_mat = Key_words().split_numbers_and_words(new_mat)
    # print('Поиск едениц измерения -', end - start)

    new_mat += ' '
    new_lines = ''
    for word in new_mat.split():
        new_word = word
        if word.isdigit():
            if int(word) % 100 == 0 and len(word) >= 4:
                new_num = str(int(word) / 1000)
                new_word = new_num
        elif word.isalpha():
            new_word = morph.parse(new_word)[0].normal_form
        new_lines += new_word + ' '
    new_mat = new_lines
    return new_mat.strip()

# Загрузка данных
def fit_0():
    data_path = 'data/for_zero.csv'
    if not os.path.isfile(data_path):
        file_path = 'data/mats.csv'
        data = pd.read_csv(file_path)
        print('Data opened!')
        data1 = data[['Название иерархии-0', 'Название иерархии-1', 'Полное наименование материала']]
        data1.to_csv('data/for_firsts.csv', index=False)
        data = data[['Название иерархии-0', 'Полное наименование материала']]
        data.to_csv(data_path, index=False)
        Fit_method2.add_method2()
        del data
    print('Берём сохранённые данные')
    data = pd.read_csv(data_path)

    # Выбор признаков и целевой переменной
    X = data['Полное наименование материала']
    y = data['Название иерархии-0']
    all_zeros = sorted(list(set(data['Название иерархии-0'].to_list())))
    y = [all_zeros.index(i) for i in y]

    # Преобразование текстовых данных в числовые признаки с помощью TF-IDF
    tfidf = TfidfVectorizer()
    tfidf = tfidf.fit(X)
    X_tfidf = tfidf.transform(X)

    print('TF-Idf Done!')

    if os.path.isfile('data/main_model.pkl'):
        with open('data/main_model.pkl', 'rb') as f:
            model = pickle.load(f)
    else:
        print("Модели нет, создаём новую")

    try:
        model.predict(X_tfidf[0:1])
        raise 'Обучать не надо'
    except Exception as exc:
        print(exc)
        print("Обучаем")
        pass

    # Метод опорных векторов
    svm = SVC(random_state=42, kernel='linear', probability=True)
    print('SVC start!')
    svm.fit(X_tfidf, y)
    with open('data/main_model.pkl', 'wb') as f:
        pickle.dump(svm, f)
    print('Done Train 0!!!')
    Train_model_1.train()

if __name__ == "__main__":
    fit_0()