import pandas as pd
from sklearn.svm import SVC
from sklearn.feature_extraction.text import TfidfVectorizer
import pickle
from utils.split_by_keys import Key_words
import re
import os
from thread import Thread
from datetime import datetime

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

    def write_logs(self, text, event=1):
        event = 'EVENT' if event == 1 else 'ERROR'
        date_time = datetime.now().astimezone()
        file_name = './logs/' + str(date_time.date()) + '.txt'
        with open(file_name, 'a', encoding="utf-8") as file:
            file.write(str(date_time) + ' | ' + event + ' | ' + text + '\n')

    def get_pred(self, text, bag=False):
        part = 'стальн'
        pattern = r'\b' + part + r'[а-яё]*\b'
        matches = re.findall(pattern, text)
        for match in matches:
            text = text.replace(match, '')
        try:
            x_pred = self.tfidf_zero.transform([text])
            y_pred = self.main_model.predict(x_pred)[0]
        except Exception as exc:
            print("ошибка главной модели", exc)
            self.write_logs("ошибка главной модели", 0)

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

    def fit(self, text, true_first, true_zero, fit_zero, fit_first):
        # if fit_zero:
            # Thread(target=self.fit_zeros, args=[text, true_zero]).start()
        if fit_first:
            Thread(target=self.fit_first, args=[text, true_first]).start()

    def fit_first(self, text, true_first):
        if text in self.data_first.to_numpy()[:, 2]:
            print('Не дообучаем!', flush=True)
            self.write_logs('Не дообучаем! First', 0)
            return
        new_row = self.data_first[self.data_first['Название иерархии-1'] == true_first].iloc[0].to_list()[:-1]+[text]
        print('new_row - ', new_row, flush=True)
        self.data_first.loc[self.data_first.shape[0]] = new_row
        ind = self.all_zeros.index(new_row[0])

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
        svc_model = SVC(random_state=42, probability=True)
        self.write_logs('SVC FIRST start!', 1)
        svc_model.fit(X_tfidf, y)

        with open('data/models/' + str(ind) + '_model.pkl', 'wb') as f:
            pickle.dump(svc_model, f)

        self.data_first[['Название иерархии-0', 'Название иерархии-1', 'Полное наименование материала']].to_csv(
            self.data_path_first, index=False)

        print('Done!!!', flush=True)
        self.write_logs('SVC FIRST DONE!', 1)

    def fit_zeros(self, text, true_zero:str):
        print("ИЕР-0", true_zero)
        if text in self.data_zero.to_numpy()[:, 1]:
            print('Не дообучаем! ИЕР-0', flush=True)
            self.write_logs('Не дообучаем! ИЕР-0', 0)
            return
        new_row = self.data_zero[self.data_zero['Название иерархии-0'] == true_zero].iloc[0].to_list()[:-1] + [text]
        print('new_row - ', new_row, flush=True)
        self.data_zero.loc[self.data_zero.shape[0]] = new_row

        X = self.data_zero['Полное наименование материала']
        y = self.data_zero['Название иерархии-0']
        all_zeros = sorted(list(set(self.data_zero['Название иерархии-0'].to_list())))
        y = [all_zeros.index(i) for i in y]

        print("TF-IDF для ИЕР-0")
        tfidf = TfidfVectorizer()
        X_tfidf = tfidf.fit_transform(X)

        print("Обучение ИЕР 0 уровня")
        svm = SVC(random_state=42, kernel='linear', probability=True)
        print('SVC start!')
        self.write_logs('SVC ZERO start!', 1)
        try:
            svm.fit(X_tfidf, y)
            self.main_model = svm
            with open('data/main_model.pkl', 'wb') as f:
                pickle.dump(svm, f)
        except Exception as exc:
            print(exc)
            self.write_logs('Не получилось обучить ZEROS', 0)
            self.data_zero.drop(self.data_zero.tail(1).index, inplace=True)
            return

        self.data_zero[['Название иерархии-0', 'Полное наименование материала']].to_csv(
            self.data_path_zero, index=False)

        print('Done!!!', flush=True)
        self.write_logs('SVC ZERO DONE!', 1)

if __name__ == '__main__':
    print(Use_models().fit(text, true_first='Труба профильная', true_zero=''))
    # print(Use_models().get_pred(text))
    # Use_models().fit('Труба 50х20', 'Труба профильная')