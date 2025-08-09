import pymorphy3
from order_recognition.utils.split_by_keys import Key_words
import re
from order_recognition.utils import logger
import nltk

class Data_text_processing:

    def find_ei(self, new_mat, val_ei, ei):
            try:
                val_ei = str(val_ei.split()[0])
            except:
                print('|'+val_ei+'|')
            ei = ei.split()[0].replace('тн', 'т').replace('.', '')
            if ei not in ['т', 'м', 'кг', 'м2', 'мп']:
                ei = 'шт'
            try:
                ind = [m.start() for m in re.finditer(f' {val_ei}{ei}', new_mat + ' ')][-1]
                new_mat = new_mat[:ind] + new_mat[ind:].replace(f' {val_ei}{ei}', ' ')
            except:
                try:
                    ind = [m.start() for m in re.finditer(f' {val_ei} {ei}', new_mat + ' ')][-1]
                    new_mat = new_mat[:ind] + new_mat[ind:].replace(f' {val_ei} {ei}', ' ')
                except:
                    try:
                        ind = [m.start() for m in re.finditer(f' {ei} {val_ei}', new_mat + ' ')][-1]
                        new_mat = new_mat[:ind] + new_mat[ind:].replace(f' {ei} {val_ei}', ' ')
                    except:
                        new_mat = new_mat.replace('рулон', 'лист').replace(f' {ei} ', ' ')
                        logger.write_logs('Ошибка с поиском ei', event=0)

            return new_mat.strip(), val_ei, ei

    def new_mat_prep(self, new_mat:str, val_ei:str=None, ei:str=None):
            morph = pymorphy3.MorphAnalyzer()

            kw = Key_words()

            new_mat = ' '.join(new_mat.split())
            new_mat = kw.split_numbers_and_words(new_mat)

            new_mat += ' '
            new_lines = ''
            for word in new_mat.split():
                new_word = word
                if new_word[-2:] == ".0":
                    new_word = new_word[:-2]
                if word.isdigit():
                    if int(word) % 50 == 0 and len(word) >= 4:
                        new_num = str(int(word) / 1000)
                        new_word = new_num
                elif word.isalpha() and len(word) > 3:
                    new_word = morph.parse(new_word)[0].normal_form
                new_lines += new_word + ' '
            new_mat = new_lines
            if val_ei and ei:
                return self.find_ei(new_mat, val_ei, ei)
            return new_mat.strip()

    def clean_text(self, text:str):
        text = text.replace("\xa0", ' ')
        while ' \n' in text or '\n ' in text or '\n\n' in text:
            text = text.replace(' \n', '\n').replace('\n ', '\n').replace('\n\n', '\n')
        return text.strip()

    def clean_email_content(self, text: str) -> str:
        """
        Очищает текст письма, сохраняя структуру позиций и удаляя служебные блоки.
        """
        # Удаление основных служебных блоков
        patterns_to_remove = [
            # Шапки писем
            r"(?i)^.*(отправлено из|пересланное письмо|от:|кому" + \
            "|дата:.*|тема::|наша компания|уважаемые|негативны|" + \
                "mail|претензии|тема|для android).*$",
            # Строки, начинающиеся с точки
            r'^\s*\.\s.*',
            # Номера телефонов 8-800
            r'\b8-800-',
            # Контактные данные
            r"\+\d[\d\s\(\)-]{8,}\d",
            r'\b\S+\.ru\S*\b',
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            # Стандартные фразы компании
            r"(?i)наша компания придерживается.*внутреннего аудита",
            r"(?i)претензии по качеству.*бесплатно",
            # Технические метки
            r"\[cynteka id \d+\]",
            r"ВНЕШНЯЯ ПОЧТА:.*",
            r"%-+%",
        ]
        
        text = text.lower()#.encode('utf-8').decode('windows-1251')

        # Удаляем паттерны построчно с сохранением структуры текста
        lines = []
        for line in text.split('\n'):
            line_clean = line.strip()
            if not line_clean:
                continue
                
            # Проверка на служебные паттерны
            remove_line = False
            for pattern in patterns_to_remove:
                if re.search(pattern, line_clean, re.IGNORECASE):
                    remove_line = True
                    break
                    
            if not remove_line:
                lines.append(line_clean)

        # Постобработка оставшегося текста
        cleaned_text = []
        for line in lines:
            # Удаляем оставшиеся артефакты
            line = re.sub(r'\s*[—-]{2,}\s*', ' ', line)  # Дефисы и тире
            line = re.sub(r'\s{2,}', ' ', line)          # Множественные пробелы
            line = re.sub(r'\u200b', '', line)           # Невидимые символы
            
            # Сохраняем только важные символы
            # line = re.sub(r'[^\w\s\d.,×xх/\-()]', '', line, flags=re.IGNORECASE)
            cleaned_text.append(line)

        return '\n'.join([line for line in cleaned_text if line])

if __name__ == '__main__':
    # Пример использования
    dirty_text = """
    --
    Отправлено из
    Mail
    для Android
    -------- Пересланное письмо --------
    От: Шарипов Дамир Ирекович
    sharipovdi@spk.ru
    Кому: Damir Sharipov
    damir.sharipov23@mail.ru
    Дата: пятница, 04 октября 2024г., 12:50 +05:00
    Тема: Уголок
    Уголок 100 100 8 12м ст3пс5/сп5 8509
    Уголок 100 63 6 12м ст3пс5/сп5 8510
    Уголок 110 110 7 12м ст3пс5/сп5 8509
    Уголок 125 125 10 12м ст3пс5/сп5 8509
    Уголок 25 25 4 6м ст3пс5/сп5 8509
    Уголок 32 32 3 6м ст3пс5/сп5 8509
    Уголок 32 32 4 6м ст3пс5/сп5 8509
    Уголок 35 35 4 6м ст3пс5/сп5 8509
    Уголок 40 40 3 6м ст3пс5/сп5 8509
    Уголок 40 40 4 12м ст3пс5/сп5 8509
    Уголок 40 40 4 6м ст3пс5/сп5 8509
    Уголок 45 45 4 12м ст3пс5/сп5 8509
    Уголок 45 45 4 6м ст3пс5/сп5 8509
    Уголок 45 45 5 12м ст3пс5/сп5 8509
    Уголок 50 50 4 12м ст3пс5/сп5 8509
    Уголок 75 75 6 12м ст3пс5/сп5 8509
    Уголок 75 75 7 12м ст3пс5/сп5 8509
    Уголок
    80 80 6 12
    м ст3пс5/сп5 8509
    Уголок
    80 80 8 12
    м ст3пс5/сп5 8509
    Уголок 90 90 6 12м ст3пс5/сп5 8509
    Уважаемые коллеги и партнеры,
    Наша Компания придерживается этических принципов ведения бизнеса и делает все для того, чтобы взаимоотношения с нашими партнерами строились на принципах открытости и прозрачности. Поэтому просим Вас сообщать нам обо всех
    негативных фактах во взаимоотношениях с нашей компанией по адресу
    doverie@scm.ru
    . Вся информация поступает в независимую службу внутреннего аудита.
    Претензии по качеству обслуживания или товара принимаются на телефон горячей линии
    8-800-7000-123
    . Звонки по России бесплатно
    """
    dp = Data_text_processing()
    clean_text = dp.clean_email_content(dirty_text)
    print(clean_text)