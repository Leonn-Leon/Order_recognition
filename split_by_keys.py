import pandas as pd
import re
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize


class Key_words():

    def __init__(self):
        self.need_to_replace = {}
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

    def find_category_in_line(self, line, categories, _split=True, past_category=None):
        if _split:
            for word in line.split():
                if word in categories:
                    return word
            return None
        else:
            min_start = 1e5
            cat = ''
            for category in categories:
                start = line.find(category)
                if start!= -1 and category == 'сталь' and past_category in ('труба', 'уголок'):
                    past_category = category
                    line = line[start+5:]
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
            line = self.replace_words(line)
            category = self.find_category_in_line(line, self.key_words)
            cat = category
            if category:
                # Находим описание категории в строке
                start = line.find(category)
                cat, end = self.find_category_in_line(line[start+len(category):], self.key_words, _split=False,
                                                    past_category=cat)
                current_words = line[start:(start+len(category)+end if end is not None else None)]
                current_category_description = " ".join(word for word in current_words.split() if not word.isdigit())
                current_words = self.return_replace(current_words)
                orders.append((category, current_words))
                if end:
                    line = line[(start+len(category)+end if end is not None else None):]
                line = self.return_replace(line)
            elif current_category_description:
                # Добавляем описание категории к строке, если она не содержит категории
                order_detail = f"{current_category_description} {line.strip()}"
                orders.append((current_category_description.split()[0], self.return_replace(order_detail)))
                self.need_to_replace = {}

        return orders

    def split_numbers_and_words(self, s):
        # Разделяем числа и буквы
        s = s.lower()+' '
        s = self.replace_words(s)
        s = s.replace('/', '').replace(' шт', 'шт')
        matches = re.findall(r'\bст\w*\d+\b', s)
        for i in matches:
            s = s.replace(i, '')
        s = re.sub(r'(\d)x(\d)', r'\1 \2', s)
        s = re.sub(r'(\d)х(\d)', r'\1 \2', s)
        s = re.sub(r'(\d)м ', r'\1', s)
        # s = re.sub(r'(?<=\d)(?=[а-яА-Яa-zA-Z])', ' ', s)
        # Разделяем буквы и числа
        # s = re.sub(r'(?<=[а-яА-Яa-zA-Z])(?=\d)', ' ', s)
        s = re.sub(r'(\d+),(\d+)', r'\1.\2', s)
        s = re.sub(r'([а-яА-Яa-zA-Z])\.', r'\1 ', s)
        s = re.sub(r'[^\w\s.]', ' ', s)
        s = s.replace(' м п ', 'мп')
        for i in matches:
            s += ' ' + i
        return s

    def replace_words(self, text):
        # Шаблон для поиска слов с корнем
        changes = {'профильн':'проф',
                   'тр': 'труба',
                   'арм': 'арматура',
                   'балк': 'балка',
                   'лист': 'лист',
                   'угол': 'уголок',
                   'шв': 'швеллер',
                   'штук': 'шт',
                   'метр': 'м',
                   'тон': 'тн',
                   'колич': 'шт',
                   'оц': 'оц'
                }
        replaced_text = text
        # self.need_to_replace = {}
        for part, category in changes.items():
            pattern = r'\b'+part+r'[а-яё]*\b'
            matches = re.findall(pattern, replaced_text)
            for match in matches:
                replaced_text = replaced_text.replace(match, category)
                self.need_to_replace[match] = category
        return replaced_text

    def return_replace(self, text):
        for match, category in self.need_to_replace.items():
            text = text.replace(category+' ', match+' ')
            # text = self.replace_first(text, category+' ', match+' ')
        return text

    # def replace_first(self, input_string, old_word, new_word):
    #     # Ищем первое вхождение слова в строке
    #     index = input_string.find(old_word)
    #     if index != -1:
    #         # Заменяем только первое вхождение
    #         new_string = input_string[:index] + new_word + input_string[index + len(old_word):]
    #         return new_string
    #     else:
    #         # Если слово не найдено, возвращаем исходную строку
    #         return input_string

    def find_key_words(self, text):
        text = text.lower()  # Приведение текста к нижнему регистру
        # text = self.split_numbers_and_words(text)
        # text = self.replace_words(text)
        print('Я тут -', text)
        return self.process_order(text)

if __name__ == '__main__':

    # Обработка письма клиента
    client_message = """
    Армат A-III 0.7м или балку 35Б1 С245 12 м.
    балка 35Б1 С245 12 м.
    """
    cl = Key_words()
    client_requests = cl.find_key_words(client_message)

    print("Заявки клиента:", client_requests)
