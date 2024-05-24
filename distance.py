from Levenshtein import ratio
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import SVC
from sklearn.metrics.pairwise import pairwise_distances
import pandas as pd
import uuid
import pickle
import json
import base64
from datetime import datetime
from find_ei import find_quantities_and_units
from split_by_keys import Key_words
import re
import numpy as np

class Find_materials():
    def __init__(self):
        self.all_materials = pd.read_csv('data/mats3.csv')
        self.method2 = pd.read_csv('data/method2.csv')
        self.kw = Key_words()
        self.method2['question'] = self.method2['question'].apply(lambda x: self.new_mat_prep(x)[0])
        self.method2.reset_index(drop=True, inplace=True)
        # self.method2.index = self.method2['question']
        # self.method2.drop(['question'], axis=1, inplace=True)
        self.saves = pd.read_csv('data/saves.csv', index_col='req_Number')
        self.all_materials = self.all_materials[~self.all_materials['Полное наименование материала'].str.contains('НЕКОНД')]
        self.all_materials.reset_index(inplace=True)
        del self.all_materials['index']
        self.all_materials['Материал'] = self.all_materials['Материал'].apply(str)
        # Добавление длины названия
        self.all_materials["Name Length"] = self.all_materials["Полное наименование материала"].apply(len)
        self.all_materials["Полное наименование материала"] = self.all_materials["Полное наименование материала"].apply(self.kw.split_numbers_and_words)
        self.vectorizer = TfidfVectorizer()
        self.tfidf_matrix = self.vectorizer.fit_transform(self.all_materials["Полное наименование материала"])
        # self.model = SVC()
        # with open("data/model.pkl", "wb") as f:
        #     pickle.dump(self.vectorizer, f)
        # with open('data/model.pkl', 'rb') as fp:
        #     self.vectorizer = pickle.load(fp)
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

    # def choose_based_on_similarity(self, text, cat):
    #     tfidf_query = self.vectorizer.transform([text])
    #     euclidean = pairwise_distances(tfidf_query, self.tfidf_matrix, metric='euclidean').flatten()
    #     tr = self.all_materials["Полное наименование материала"].str.split().apply(lambda x: x[0]) == cat
    #     # print(self.all_materials[tr])
    #     # print(self.all_materials["Полное наименование материала"].str.split())
    #     # print('Вот тут -', tr.sum())
    #     if tr.sum() > 0:
    #         euclidean[self.all_materials[~tr].index] = 1e3
    #     max_similarity_idxs = np.argsort(euclidean)
    #     return max_similarity_idxs

    def choose_based_on_similarity(self, text):
        Levenstain = self.all_materials["Полное наименование материала"].apply(lambda x: ratio(text, x))
        # Jacaard = self.all_materials["Полное наименование материала"].apply(lambda x: self.jaccard_distance(text, x[:len(text)]))
        # tr = self.all_materials["Полное наименование материала"].str.split().apply(lambda x: x[0]) == cat
        # if tr.sum() > 0:
        #     Jacaard[self.all_materials[~tr].index] = 1e3
        max_similarity_idxs = np.argsort(Levenstain)
        return max_similarity_idxs[::-1]

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
        # words = re.findall(r'\D+', query)  # Найти все нечисловые последовательности
        # numbers = re.findall(r'\d+\.?\d*', query)  # Найти все числа, включая десятичные
        # all = words + numbers
        all = query.split()
        print('second metric -', all)
        # Функция для подсчёта совпадающих слов и проверки наличия числовых параметров
        def count_matches_and_numeric(query_numbers, material_name):
            material_words = set(material_name.lower().split())  # Разбиение названия материала на слова
            # match_count = sum(1 for word in query_words if word.lower().strip() in material_words)  # Подсчёт совпадений
            numeric_presence = sum(1 for num in query_numbers if num.strip() in material_words)  # Подсчёт совпадений
            # numeric_presence = any(
            #     num in material_name for num in query_numbers)  # Проверка наличия числовых параметров
            return numeric_presence

        # Применение функции подсчёта к каждому материалу
        materials_df["Numeric Presence"] = materials_df["Полное наименование материала"].apply(
            lambda x: count_matches_and_numeric(all, x))

        # Фильтрация материалов, которые имеют хотя бы одно словесное совпадение и числовые параметры
        # filtered_materials = materials_df[(materials_df["Matches"] > 0) & (materials_df["Numeric Presence"])]

        # Сортировка по количеству совпадений, наличию числовых параметров и, наконец, по длине названия
        sorted_materials = materials_df.sort_values(by=["Numeric Presence"],#, "Name Length"],
                                                          ascending=[False])

        return sorted_materials.head(top_n)

    def new_mat_prep(self, new_mat):
        # new_mat = new_mat.replace('/', '')
        new_mat = self.kw.split_numbers_and_words(new_mat)
        val_ei, ei = find_quantities_and_units(new_mat)
        # print('Поиск едениц измерения -', end - start)

        new_mat += ' '
        new_mat = new_mat.replace('рулон', 'лист').replace(f' {ei} ', ' ')
        try:
            ind = [m.start() for m in re.finditer(f' {val_ei} ', new_mat + ' ')][-1]
            new_mat = new_mat[:ind] + new_mat[ind:].replace(f' {val_ei} ', ' ')
        except:
            self.write_logs('Ошибка с поиском ei', event=0)
        new_lines = ''
        for word in new_mat.split():
            new_word = word
            if word.isdigit():
                if int(word) % 100 == 0 and len(word) >= 4:
                    new_num = str(int(word) / 1000)
                    new_word = new_num
            new_lines += new_word + ' '
        new_mat = new_lines
        return new_mat, val_ei, ei

    def find_mats(self, rows):
        results = []
        results += [{"req_Number": str(uuid.uuid4())}]
        poss = []
        pos_id = 0
        for _, (row, ei, val_ei) in enumerate(rows):
            if len(row.split()) == 0 or row[0]=='+':
                continue
            new_row = ' '.join(row.split())
            new_mat = new_row
            poss += [{'position_id': str(pos_id)}]
            poss[-1]['request_text'] = new_mat
            poss[-1]['value'] = str(val_ei.split()[0])
            ei = ei.split()[0].replace('тн', 'т').replace('.', '')
            if ei not in ['т', 'м', 'кг', 'м2', 'мп']:
                ei = 'шт'
            poss[-1]['ei'] = ei
            new_mat = self.kw.replace_words(new_mat)
            pos_id += 1
            ###############################
            # new_mat, val_ei, ei = self.new_mat_prep(new_mat)
            #################################
            # ress = self.model.predict_proba(new_mat)
            # ress = np.array(ress)[:50]
            ress = self.choose_based_on_similarity(new_mat)
            ress = np.array(ress)
            advanced_search_results = self.find_top_materials_advanced(new_mat, self.all_materials.iloc[ress[:25]])
            # advanced_search_results = self.find_top_materials_advanced(new_mat, self.all_materials)
            # print('Advanced -', advanced_search_results.values)
            ress = advanced_search_results.values
            # poss[-1]['request_text'] = new_mat
            # if poss[-1]['request_text'] in self.method2.index:
            if new_mat in self.method2.question.to_list():
                print('Нашёл')
                foundes = self.method2[self.method2.question == new_mat].answer.to_list()
                true_positions = []
                for pos in foundes[::-1]:
                    temp = json.loads(base64.b64decode(pos).decode('utf-8').replace("'", '"'))
                    if temp not in true_positions:
                        true_positions += [temp]
                itog = []
                for ind, i in enumerate(ress):
                    for tp in true_positions:
                        if i[0] == tp["num_mat"]:
                            break
                    else:
                        itog += [i]
                ress = []
                for tp in true_positions:
                    ress += [[tp["num_mat"], tp["name_mat"]]]
                ress += itog
                ress = ress[:5]
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