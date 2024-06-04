import pandas as pd
from sklearn.svm import SVC
from sklearn.feature_extraction.text import TfidfVectorizer
import pickle
from split_by_keys import Key_words
import re

class Use_models():
    def __init__(self):
        self.data_path = 'data/for_zero.csv'
        self.data = pd.read_csv(self.data_path)

        with open('data/main_model.pkl', 'rb') as f:
            self.main_model = pickle.load(f)

        X = self.data['Полное наименование материала']
        self.tfidf = TfidfVectorizer()
        self.tfidf.fit(X)
        self.all_zeros = sorted(list(set(self.data['Название иерархии-0'].to_list())))

    def get_pred(self, text, bag=False):
        part = 'стальн'
        pattern = r'\b' + part + r'[а-яё]*\b'
        matches = re.findall(pattern, text)
        for match in matches:
            text = text.replace(match, '')


        x_pred = self.tfidf.transform([text])
        y_pred = self.main_model.predict(x_pred)[0]

        with open('data/models/' + str(y_pred) + '_model.pkl', 'rb') as f:
            model_1 = pickle.load(f)

        zero = self.all_zeros[y_pred]
        if bag:
            print(self.main_model.predict_proba(x_pred))
            print(self.all_zeros)
            print('ИЕР-0 =', zero)
        sort_data = self.data[self.data['Название иерархии-0'] == zero]
        firsts = sorted(list(set(sort_data['Название иерархии-1'].to_list())))
        X_1 = sort_data['Полное наименование материала']
        tfidf_1 = TfidfVectorizer()
        tfidf_1.fit(X_1)
        x_pred_1 = tfidf_1.transform([text])
        # print(firsts[model_1.predict(x_pred_1)[0]])
        return firsts[model_1.predict(x_pred_1)[0]] # Возвращаем первую иерархию-1

    def fit(self, text, true_first):
        if text in self.data.to_numpy()[:, 3]:
            print('Не дообучаем!')
            return
        new_row = self.data[self.data['Название иерархии-1'] == true_first].iloc[0].to_list()[:-1]+[text]
        self.data.iloc[self.data.shape[0]] = new_row
        ind = self.all_zeros.index(new_row[0])
        self.data.to_csv(self.data_path)

        sort_data = self.data[self.data['Название иерархии-0'] == new_row[0]]
        print(sort_data.shape)
        # Выбор признаков и целевой переменной
        X = sort_data['Полное наименование материала']
        y = sort_data['Название иерархии-1']
        firsts = sorted(list(set(sort_data['Название иерархии-1'].to_list())))
        y = [firsts.index(i) for i in y]

        tfidf = TfidfVectorizer()
        X_tfidf = tfidf.fit_transform(X)

        svc_model = SVC(random_state=42)
        svc_model.fit(X_tfidf, y)

        with open('data/models/' + str(ind) + '_model.pkl', 'wb') as f:
            pickle.dump(svc_model, f)
        print('Done!!!')

    def fit_zeros(self):
        # Обучается долго!!!
        X = self.data['Полное наименование материала']
        y = self.data['Название иерархии-0']
        self.all_zeros = sorted(list(set(self.data['Название иерархии-0'].to_list())))
        y = [self.all_zeros.index(i) for i in y]
        tfidf = TfidfVectorizer()
        X_tfidf = tfidf.fit_transform(X)
        print('TF-Idf Done!')
        svm = SVC(random_state=42, kernel='linear', probability=True)
        print('SVC start!')
        svm.fit(X_tfidf, y)
        with open('data/main_model.pkl', 'wb') as f:
            pickle.dump(svm, f)
        print('Done!!!')

if __name__ == '__main__':
    text = 'Труба стальная 159*4 (6метров) 2 шт'
    kw = Key_words()
    text = kw.split_numbers_and_words(text)
    print(text[:-15])
    print(Use_models().get_pred(text, bag=True))
    # Use_models().fit('Труба 50х20', 'Труба профильная')