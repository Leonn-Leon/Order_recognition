from Levenshtein import ratio
import pandas as pd
import uuid
import json
import base64
from datetime import datetime
from find_ei import find_quantities_and_units
from split_by_keys import Key_words
import re
import numpy as np

class Find_materials():
    def __init__(self):
        self.all_materials = pd.read_csv('data/mats.csv')
        self.method2 = pd.read_csv('data/method2.csv', index_col='question')
        self.saves = pd.read_csv('data/saves.csv', index_col='req_Number')
        self.all_materials['Полное наименование материала'] = self.all_materials['Полное наименование материала'].apply(
            lambda x: x.replace(', ', ' '))
        self.all_materials['Материал'] = self.all_materials['Материал'].apply(str)
        # Добавление длины названия
        self.all_materials["Name Length"] = self.all_materials["Полное наименование материала"].apply(len)
        kw = Key_words()
        self.all_materials["Полное наименование материала"] = self.all_materials["Полное наименование материала"].apply(kw.split_numbers_and_words)
        print('All materials opened!', flush=True)


    def write_logs(self, text, event=1):
        event = 'EVENT' if event == 1 else 'ERROR'
        date_time = datetime.now().astimezone()
        file_name = './logs/' + str(date_time.date()) + '.txt'
        log = open(file_name, 'a')
        log.write(str(date_time) + ' | ' + event + ' | ' + text + '\n')
        log.close()

    def jaccard_distance(self, str1, str2):
        a = set(str1)
        b = set(str2)
        intersection = len(a.intersection(b))
        union = len(a.union(b))
        return 1 - intersection / union

    def choose_based_on_similarity(self, text):
        nearest_mats = []
        for ind, material in enumerate(self.all_materials.iloc[59:].values):
            distance = ratio(text, material[1])
            # distance = self.jaccard_distance(text, material[1])
            try:
                nearest_mats += [[str(material[0]), material[1], distance, ind+59]]
            except:
                print(material)
        return nearest_mats

    def find_top_materials_advanced(self, query, materials_df, top_n=5):
        """
        Расширенная функция поиска материалов, которая отдаёт приоритет совпадениям по словам и учитывает числовые параметры.

        Аргументы:
        query (str): Строка запроса от клиента.
        materials_df (pd.DataFrame): DataFrame, содержащий данные о материалах.
        top_n (int): Количество лучших результатов для возврата.

        Возвращает:
        pd.DataFrame: DataFrame, содержащий топовые совпадающие материалы.
        """
        # Разделение запроса на слова и числа
        words = re.findall(r'\D+', query)  # Найти все нечисловые последовательности
        numbers = re.findall(r'\d+\.?\d*', query)  # Найти все числа, включая десятичные
        all = words + numbers
        # Функция для подсчёта совпадающих слов и проверки наличия числовых параметров
        def count_matches_and_numeric(query_words, query_numbers, material_name):
            material_words = set(material_name.lower().split())  # Разбиение названия материала на слова
            # match_count = sum(1 for word in query_words if word.lower().strip() in material_words)  # Подсчёт совпадений
            numeric_presence = sum(1 for num in query_numbers if num.strip() in material_words)  # Подсчёт совпадений
            # numeric_presence = any(
            #     num in material_name for num in query_numbers)  # Проверка наличия числовых параметров
            return numeric_presence

        # Применение функции подсчёта к каждому материалу
        materials_df["Numeric Presence"] = materials_df["Полное наименование материала"].apply(
            lambda x: count_matches_and_numeric(words, all, x))

        # Фильтрация материалов, которые имеют хотя бы одно словесное совпадение и числовые параметры
        # filtered_materials = materials_df[(materials_df["Matches"] > 0) & (materials_df["Numeric Presence"])]

        # Сортировка по количеству совпадений, наличию числовых параметров и, наконец, по длине названия
        sorted_materials = materials_df.sort_values(by=["Numeric Presence", "Name Length"],
                                                          ascending=[False, True])

        return sorted_materials.head(top_n)

    def find_mats(self, rows):
        results = []
        results += [{"req_Number": str(uuid.uuid4())}]
        poss = []
        no_numbers = False
        pos_id = 0
        for _, row in enumerate(rows):
            around_materials = {}
            min_dis = 1e5
            if len(row.split()) == 0 or row[0]=='+':
                continue
            new_row = ' '.join(row.split())
            if (ord(new_row[0]) > 65 and ord(new_row[0]) < 123):
                continue
            if new_row[0].isdigit():
                if len(new_row.split()) == 1:
                    continue
                if no_numbers:
                    new_mat = new_mat + new_row
                    no_numbers = False
                else:
                    new_mat = ' '.join(new_mat.split()[:-len(new_row.split())])+ ' ' + new_row
            else:
                new_mat = new_row
            new_mat = new_mat.lower()\
                .replace('(', '') \
                .replace(')', '') \
                .replace(' -', ' ')\
                .replace(' —', ' ')\
                .replace('оцинк ', 'оц ') \
                .replace(' оц.', ' оц ') \
                .replace(':', '')
            new_mat = new_mat.replace('шв ', 'швеллер ') \
                .replace('количестве', '') \
                .replace('гн ', 'гнутый ') \
                .replace('гнут ', 'гнутый ') \
                .replace('нут ', 'гнутый ') \
                .replace('гут ', 'гнутый ') \
                .replace('тр ', 'труба ') \
                .replace('тр. ', 'труба ') \
                .replace('проф ', 'профиль ')\
                .replace('профильная', 'проф') \
                .replace('оцинкованный', 'оц') \
                .replace('*', ' ') \
                .replace('метра', 'м ') \
                .replace('метров', 'м ')\
                .replace('мм', '')\
                .replace(' -', ' ')\
                .replace('м.', 'м') \
                .replace('шт', 'шт ') \
                .replace('мп.', 'мп') \
                .replace('кг', 'кг ') \
                .replace('  ', ' ')\
                .replace(' /к', ' х/к')\
                .replace('бу та', 'бухта') \
                .replace('гост', '') + ' '
            new_mat = new_mat.replace('профтруба', 'труба профил')
            if len([i for i in new_mat if i.isdigit()]) == 0:
                no_numbers = True
                continue
            if 'швеллер' in new_mat:
                new_mat = new_mat.replace('у ', ' у ')\
                    .replace('п ', ' п ')
            if 'арматура' in new_mat:
                new_mat = new_mat.replace(' i', ' a-i')
            val_ei, ei = find_quantities_and_units(new_mat)
            # print('Поиск едениц измерения -', end - start)
            poss+=[{'position_id':str(pos_id)}]
            pos_id += 1
            ress = sorted(self.choose_based_on_similarity(new_mat), key=lambda item: item[2])[-30:][::-1]
            ress = np.array(ress)
            advanced_search_results = self.find_top_materials_advanced(new_mat, self.all_materials.loc[ress[:, 3].astype(np.int32)])
            print('Advanced -', advanced_search_results.values)
            # ress = advanced_search_results.values
            if new_mat in self.method2.index:
                true_position = json.loads(base64.b64decode(self.method2.loc[new_mat].answer).decode('utf-8').replace("'", '"'))
                ei = true_position["true_ei"]
                val_ei = true_position["true_value"]
                ress = [(true_position["num_mat"], true_position["name_mat"])] + ress[:-1]
            else:
                poss[-1]['ei'] = ei.replace('тн', 'т')
                poss[-1]['value'] = str(val_ei)

            poss[-1]['request_text'] = new_mat
            print(new_mat, '=', ress[0][1]+'|'+ str(val_ei) +'-'+ ei +'|')
            print(ress, end ='\n----\n')

            for ind, pos in enumerate(ress):
                poss[-1]['material'+str(ind+1)+'_id'] = '0'*(18-len(str(pos[0])))+str(pos[0])

        results[0]["positions"] = poss
        self.saves.loc[results[0]["req_Number"]] = ["{'positions':"+str(results[0]["positions"])+"}"]
        self.saves.to_csv('data/saves.csv')
        print(results)
        return str(results)


if __name__ == '__main__':
    print('Введите наименования ниже для поиска их в базе:')
    rows = []
    find_mats  = Find_materials()
    while True:
        try:
            line = input()
            if line == '0':
                break
            line = ' '.join(line.split())
        except EOFError:
            break
        rows.append(line)
    print(f'Найдено {len(rows)} наименований')
    find_mats.find_mats(rows)