import pandas as pd
import re
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize


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
        # text = re.sub(r'[^\w\s]', ' ', text)
        text = text.replace(',', '.').replace('двутавр', 'профиль')
        # Токенизация и фильтрация стоп-слов
        words = word_tokenize(text)
        filtered_words = [word for word in words if word not in self.stop_words]
        return ' '.join(filtered_words).replace(' . ', ' ')

    def find_category_in_line(self, line, categories, _split=True):
        if _split:
            for word in line.split():
                if word in categories:
                    return word, word
                if word[-1] == 'ы':
                    if word[:-1] in categories:
                        return word[:-1], word
                if word[-1] == 'и':
                    if word[:-1] + 'а' in categories:
                        return word[:-1] + 'а', word
            return None, None
        else:
            min_start = 1e5
            cat = ''
            for category in categories:
                start = line.find(category)
                if start != -1:
                    if start < min_start:
                        min_start=start
                        cat = category
            return (None, None) if min_start == 1e5 else (cat, min_start)


    def process_order(self, input_order):
        lines = input_order.split("\n")
        orders = []
        current_category_description = ""
        indx = 0
        end = None
        while indx < len(lines) or end is not None:
            if end is None:
                line = lines[indx]
                indx += 1
            else:
                end = None
            if len(line.split()) == 0 or not any(chr.isdigit() for chr in line):
                current_category_description = ''
            if line.strip() == "":
                continue
            cat, category = self.find_category_in_line(line, self.key_words)
            if category:
                # Находим описание категории в строке
                start = line.find(category)
                _, end = self.find_category_in_line(line[start+len(category):], self.key_words, _split=False)
                current_words = line[start:(start+len(category)+end if end is not None else None)]
                current_category_description = " ".join(word for word in current_words.split() if not word.isdigit())
                orders.append((cat, current_words.strip()))
                if end:
                    line = line[(start+len(category)+end if end is not None else None):]
                print(line)
            elif current_category_description:
                # Добавляем описание категории к строке, если она не содержит категории
                order_detail = f"{current_category_description} {line.strip()}"
                orders.append((current_category_description.split()[0], order_detail))

        return orders

    def split_numbers_and_words(self, s):
        # Разделяем числа и буквы
        s = s.lower()
        s = re.sub(r'(?<=\d)(?=[а-яА-Яa-zA-Z])', ' ', s)
        # Разделяем буквы и числа
        s = re.sub(r'(?<=[а-яА-Яa-zA-Z])(?=\d)', ' ', s)
        s = re.sub(r'(\d+),(\d+)', r'\1.\2', s)
        s = s.replace(' -', ' ')
        return s

    def replace_words(self, text, part, category):
        # Шаблон для поиска слов с корнем "тр"
        pattern = r'\b'+part+r'[а-яё]*\b'
        # Замена найденных слов на "труба"
        replaced_text = re.sub(pattern, category, text)
        return replaced_text

    def find_key_words(self, text):
        text = text.lower()  # Приведение текста к нижнему регистру
        text = self.split_numbers_and_words(text).replace('пр ', 'профиль ') \
            .replace('?', '').replace('-', ' ')
        text = self.replace_words(text, 'тр', 'труба')
        text = self.replace_words(text, 'арм', 'арматура')
        # text = self.replace_words(text, 'проф', 'профиль')
        text = self.replace_words(text, 'лист', 'лист')
        text = self.replace_words(text, 'угол', 'уголок')
        text = self.replace_words(text, 'шв', 'швеллер')
        text = self.replace_words(text, 'штук', 'шт')
        text = self.replace_words(text, 'метр', 'м')
        text = self.replace_words(text, 'колич', 'шт')
        text = self.replace_words(text, 'оц', 'оц')
        ind = text.find('с уваж')
        text = text[:ind]
        print('Я тут -', text)
        # text = self.preprocess_text(text)
        return self.process_order(text)

if __name__ == '__main__':

    # Обработка письма клиента
    client_message = "Арматура A-III 0.7м или балка 35Б1 С245 12 м."
    cl = Key_words()
    client_requests = cl.find_key_words(client_message)

    print("Заявки клиента:", client_requests)
