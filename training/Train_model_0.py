import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import SVC
import pickle
import os
from order_recognition.utils.split_by_keys import Key_words
from order_recognition.utils.data_text_processing import new_mat_prep
import Train_model_1
import Fit_method2 as Fit_method2
import pymorphy3


# Загрузка данных
def fit_0():
    data_path = 'order_recognition/work_with_models/for_zero.csv'
    if not os.path.isfile(data_path):
        file_path = 'order_recognition/data/mats.csv'
        data = pd.read_csv(file_path)
        print('Data opened!')
        data1 = data[['Название иерархии-0', 'Название иерархии-1', 'Полное наименование материала']]
        data1.to_csv('order_recognition/work_with_models/for_firsts.csv', index=False)
        data = data[['Название иерархии-0', 'Полное наименование материала']]
        data.to_csv(data_path, index=False)
        Fit_method2.add_method2()
        del data
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
    tfidf = tfidf.fit(X)
    X_tfidf = tfidf.transform(X)

    print('TF-Idf Done!')

    if os.path.isfile('order_recognition/work_with_models/models/main_model.pkl'):
        with open('order_recognition/work_with_models/models/main_model.pkl', 'rb') as f:
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
    with open('order_recognition/work_with_models/models/main_model.pkl', 'wb') as f:
        pickle.dump(svm, f)
    print('Done Train 0!!!')
    Train_model_1.train()

if __name__ == "__main__":
    fit_0()