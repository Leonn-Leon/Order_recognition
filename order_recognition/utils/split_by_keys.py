import pandas as pd
import re


class Key_words():

    def __init__(self):
        self.need_to_replace = {}

    def split_numbers_and_words(self, s):
        # Разделяем числа и буквы
        s = s.lower()+' '
        s = self.replace_words(s)
        s = s.replace(' по ', ' ')
        if 'уголок' in s:
            s = s.replace('гост', '')
        # matches = re.findall(r'\bст\w*\d+\b', s)
        # for i in matches:
        #     s = s.replace(i, '')
        s = re.sub(r'(\d)x(\d)', r'\1 \2', s)
        s = re.sub(r'(\d)х(\d)', r'\1 \2', s)
        s = re.sub(r'(\d)х(\d)', r'\1 \2', s)
        s = re.sub(r'(\d)/(\d)', r'\1 \2', s)
        # s = re.sub(r'(\d)м ', r'\1 ', s)
        # s = re.sub(r'(\d)мм ', r'\1 ', s)
        # s = re.sub(r'(\d) п ', r'\1п ', s)
        # s = re.sub(r'(\d) шт', r'\1шт ', s)
        # s = re.sub(r'(\d)ду', r'\1 ду ', s)
        # s = re.sub(r'(\d) у ', r'\1у ', s)
        # s = re.sub(r'(?<=\d)(?=[а-яА-Яa-zA-Z])', ' ', s)
        # Разделяем буквы и числа
        # s = re.sub(r'(?<=[а-яА-Яa-zA-Z])(?=\d)', ' ', s)
        s = re.sub(r'(\d+),(\d+)', r'\1.\2', s)
        s = re.sub(r'(ст)\s+(\d+)', r'\1\2', s) # Заменяем найденные совпадения на "ст" и число без пробела
        # s = re.sub(r'([а-яА-Яa-zA-Z])\.', r'\1 ', s)
        s = re.sub(r'[^\w\s.]', ' ', s)
        s = s.replace(' м п ', 'мп').replace('/', '')
        s = s.replace('бш', 'б ш').replace('гк', 'г к').replace('гк', 'г к')
        return s

    def replace_words(self, text):
        # Шаблон для поиска слов с корнем
        changes = {'профильн':'проф',
                   'профлист': 'профнастил',
                   'двутавр': 'балка',
                   'тр ': 'труба ',
                   'арм': 'арматура',
                   'лист': 'лист',
                   'угол': 'уголок',
                   'рифл': 'рифл',
                   'шв': 'швеллер',
                   'штук': 'шт',
                   'метр': 'м',
                   'тон': 'тн',
                   'колич': 'шт',
                   'оц': 'оц',
                   'эсв': 'э с',
        }
        starts ={
            'а ': 'арматура ',
            'балк': 'балка',
            'б ': 'балка ',
            'у ': 'уголок ',
            'л ': 'лист ',
        }

        # pattern = r'\b(?:СТ|ст)?(\d+г\d+с)\b'  # Шаблон поиска
        # text = re.sub(pattern, r'\1', text)

        for part, answer in starts.items():
            if text.startswith(part):
                text = text.replace(part, answer)
                break
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

if __name__ == '__main__':

    # Обработка письма клиента
    client_message = """
    Армат A-III 0.7м или балку 35Б1 С245 12 м.
    балка 35Б1 С245 12 м.
    """
    cl = Key_words()
    client_requests = cl.split_numbers_and_words(client_message)

    print("Заявки клиента:", client_requests)
