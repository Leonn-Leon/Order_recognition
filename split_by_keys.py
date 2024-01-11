import pandas as pd
import re
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import os



class Key_words():

    def __init__(self):
        try:
            nltk.data.find('corpora/stopwords')
        except LookupError:
            nltk.download('stopwords')
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt')
        # Загрузка русских стоп-слов
        self.stop_words = stopwords.words('russian')
        # Загрузка списка уникальных ассортиментных групп
        unique_words_path = 'data/categories.csv'
        unique_words_df = pd.read_csv(unique_words_path)
        self.key_words = unique_words_df['Filtered_Description'].tolist()

# Функция для предварительной обработки текста: удаление стоп-слов и знаков препинания
    def preprocess_text(self, text):
        # Удаление знаков препинания
        text = re.sub(r'[^\w\s]', ' ', text)
        # Токенизация и фильтрация стоп-слов
        words = word_tokenize(text)
        filtered_words = [word for word in words if word not in self.stop_words]
        return ' '.join(filtered_words)

    def find_key_words(self, text):
        text = text.lower()  # Приведение текста к нижнему регистру
        text = self.preprocess_text(text)
        requests = []
        positions = []
        for word in self.key_words:
            for match in re.finditer(r'\b' + re.escape(word) + r'\b', text):
                positions.append((match.start(), word))
        positions.sort()

        for i in range(len(positions)):
            start, word = positions[i]
            end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
            request_text = text[start:end].strip()
            requests.append((word, request_text))

        return requests

if __name__ == '__main__':

    # Обработка письма клиента
    client_message = "Арматура A-III 0.7м или балка 35Б1 С245 12 м."
    cl = Key_words()
    client_requests = cl.find_key_words(client_message)

    print("Заявки клиента:", client_requests)
