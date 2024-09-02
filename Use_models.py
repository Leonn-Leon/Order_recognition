import pandas as pd
from sklearn.svm import SVC
from sklearn.feature_extraction.text import TfidfVectorizer
import pickle
from split_by_keys import Key_words
import re
import os
from thread import Thread

class Use_models():
    def __init__(self):
        self.data_path_zero = 'data/for_zero.csv'
        self.data_path_first = 'data/for_firsts.csv'
        self.data_zero = pd.read_csv(self.data_path_zero)
        self.data_first = pd.read_csv(self.data_path_first)

        with open('data/main_model.pkl', 'rb') as f:
            self.main_model = pickle.load(f)

        X_zero = self.data_zero['Полное наименование материала']
        self.tfidf_zero = TfidfVectorizer()
        self.tfidf_zero.fit(X_zero)

        # X_first = self.data_first['Полное наименование материала']
        # self.tfidf_first = TfidfVectorizer()
        # self.tfidf_first.fit(X_first)

        self.all_zeros = sorted(list(set(self.data_zero['Название иерархии-0'].to_list())))

    def get_pred(self, text, bag=False):
        part = 'стальн'
        pattern = r'\b' + part + r'[а-яё]*\b'
        matches = re.findall(pattern, text)
        for match in matches:
            text = text.replace(match, '')

        x_pred = self.tfidf_zero.transform([text])
        y_pred = self.main_model.predict(x_pred)[0]

        with open('data/models/' + str(y_pred) + '_model.pkl', 'rb') as f:
            model_1 = pickle.load(f)

        zero = self.all_zeros[y_pred]
        if bag:
            print(self.main_model.predict_proba(x_pred))
            print(self.all_zeros)
            print('ИЕР-0 =', zero)

        sort_data = self.data_first[self.data_first['Название иерархии-0'] == zero]
        firsts = sorted(list(set(sort_data['Название иерархии-1'].to_list())))
        X_1 = sort_data['Полное наименование материала']
        tfidf_1 = TfidfVectorizer()
        tfidf_1.fit(X_1)
        x_pred_1 = tfidf_1.transform([text])
        # print(firsts[model_1.predict(x_pred_1)[0]])
        return firsts[model_1.predict(x_pred_1)[0]] # Возвращаем первую иерархию-1

    def fit(self, text, true_first, true_zero):
        # Thread(target=self.fit_zeros, args=[text, true_zero]).start()
        Thread(target=self.fit_first, args=[text, true_first]).start()

    def fit_first(self, text, true_first):
        if text in self.data_first.to_numpy()[:, 2]:
            print('Не дообучаем!', flush=True)
            return
        new_row = self.data_first[self.data_first['Название иерархии-1'] == true_first].iloc[0].to_list()[:-1]+[text]
        print('new_row - ', new_row, flush=True)
        self.data_first.loc[self.data_first.shape[0]] = new_row
        ind = self.all_zeros.index(new_row[0])
        self.data_first[['Название иерархии-0', 'Название иерархии-1', 'Полное наименование материала']].to_csv(self.data_path_first, index=False)

        sort_data = self.data_first[self.data_first['Название иерархии-0'] == new_row[0]]
        # print(sort_data.shape)
        # Выбор признаков и целевой переменной
        X = sort_data['Полное наименование материала']
        y = sort_data['Название иерархии-1']
        firsts = sorted(list(set(sort_data['Название иерархии-1'].to_list())))
        y = [firsts.index(i) for i in y]

        tfidf = TfidfVectorizer()
        X_tfidf = tfidf.fit_transform(X)

        print("Обучение ИЕР 1 уровня")
        svc_model = SVC(random_state=42)
        svc_model.fit(X_tfidf, y)

        with open('data/models/' + str(ind) + '_model.pkl', 'wb') as f:
            pickle.dump(svc_model, f)
        print('Done!!!', flush=True)

    def fit_zeros(self, true_zero:str):
        print("прум пум пум", true_zero)
        if text in self.data_zero.to_numpy()[:, 2]:
            print('Не дообучаем!', flush=True)
            return
        new_row = self.data_zero[self.data_zero['Название иерархии-0'] == true_zero].iloc[0].to_list()[:-1] + [text]
        print('new_row - ', new_row, flush=True)
        self.data_zero.loc[self.data_zero.shape[0]] = new_row
        self.data_zero[['Название иерархии-0', 'Полное наименование материала']].to_csv(
            self.data_path_zero, index=False)

        X = self.data_zero['Полное наименование материала']
        y = self.data_zero['Название иерархии-0']
        all_zeros = sorted(list(set(self.data_zero['Название иерархии-0'].to_list())))
        y = [all_zeros.index(i) for i in y]

        tfidf = TfidfVectorizer()
        X_tfidf = tfidf.fit_transform(X)

        print("Обучение ИЕР 0 уровня")
        svm = SVC(random_state=42, kernel='linear', probability=True)
        print('SVC start!')
        svm.fit(X_tfidf, y)
        with open('data/main_model.pkl', 'wb') as f:
            pickle.dump(svm, f)
        print('Done!!!', flush=True)

if __name__ == '__main__':
    text = "труба 60 60 2 6 "
    kw = Key_words()
    text = kw.split_numbers_and_words(text)
    print('Первая иерархия', Use_models().get_pred(text, bag=True))
    ##########
    print(Use_models().fit(text, true_first='Труба профильная', true_zero=''))
    # print(Use_models().get_pred(text))
    # Use_models().fit('Труба 50х20', 'Труба профильная')