import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import SVC
import pickle

# Загрузка данных
# file_path = 'data/Mats_with_eirar.csv'
# data = pd.read_csv(file_path)
def train():
    data_path = 'data/for_firsts.csv'
    print('Берём сохранённые данные')
    data = pd.read_csv(data_path)

    all_zeros = sorted(list(set(data['Название иерархии-0'].to_list())))
    for ind, zero in enumerate(all_zeros):
        print(zero)
        sort_data = data[data['Название иерархии-0'] == zero]
        print(sort_data.shape)
        # Выбор признаков и целевой переменной
        X = sort_data['Полное наименование материала']
        y = sort_data['Название иерархии-1']
        firsts = sorted(list(set(sort_data['Название иерархии-1'].to_list())))
        y = [firsts.index(i) for i in y]

        # Преобразование текстовых данных в числовые признаки с помощью TF-IDF
        tfidf = TfidfVectorizer()
        cats = pd.read_csv('data/categories.csv')["Filtered_Description"]
        tfidf = tfidf.fit(cats)
        X_tfidf = tfidf.transform(X)

        try:
            with open('data/models/' + str(ind) + '_model.pkl', 'rb') as f:
                model_1 = pickle.load(f)
        except:
            print('Создаём новую модель', ind)

        try:
            model_1.predict(X_tfidf[0:1])
            continue
        except Exception as exc:
            print(exc)
            pass

        # Создание и обучение модели SVC
        svc_model = SVC(random_state=42, probability=True)
        svc_model.fit(X_tfidf, y)
        with open('data/models/'+str(ind)+'_model.pkl', 'wb') as f:
            pickle.dump(svc_model, f)
        print('Done!!!')

if __name__ == '__main__':
    train()