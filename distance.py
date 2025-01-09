from Levenshtein import ratio
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import pairwise_distances
import pandas as pd
import uuid
import pickle
import json
import base64
from datetime import datetime
from thread import Thread
from split_by_keys import Key_words
import re
import numpy as np
from Use_models import Use_models
import pymorphy3

class Find_materials():
    def __init__(self):
        pd.options.mode.copy_on_write = True
        self.models = Use_models()
        self.all_materials = pd.read_csv('data/mats.csv', dtype=str)
        self.otgruzki = pd.read_csv('data/otgruzki.csv', sep=';')
        self.otgruzki['Код материала'] = self.otgruzki['Код материала'].astype(int)
        self.method2 = pd.read_csv('data/method2.csv')
        self.kw = Key_words()
        self.method2['question'] = self.method2['question'].apply(self.new_mat_prep)
        self.method2.reset_index(drop=True, inplace=True)
        self.saves = pd.read_csv('data/saves.csv', index_col='req_Number')
        self.all_materials.reset_index(drop=True, inplace=True)
        # Добавление длины названия
        self.all_materials["Name Length"] = self.all_materials["Полное наименование материала"].str.len()
        print('All materials opened!', flush=True)


    def write_logs(self, text, event=1):
        event = 'EVENT' if event == 1 else 'ERROR'
        date_time = datetime.now().astimezone()
        file_name = './logs/' + str(date_time.date()) + '.txt'
        with open(file_name, 'a', encoding="utf-8") as file:
            file.write(str(date_time) + ' | ' + event + ' | ' + text + '\n')

    def jaccard_distance(self, str1, str2):
        a = set(str1)
        b = set(str2)
        intersection = len(a.intersection(b))
        union = len(a.union(b))
        return 1 - intersection / union

    def choose_based_on_similarity(self, text, first_ierar, ress=None):
        materials_df = self.all_materials[['Материал', "Полное наименование материала", "Название иерархии-1"]].iloc[ress[:15]]
        materials_df["Levenstain"] = materials_df["Полное наименование материала"].apply(lambda x: ratio(text, x))
        tr = materials_df['Название иерархии-1'] == first_ierar
        if tr.sum() > 0:
            materials_df.loc["Levenstain", materials_df[~tr].index] = 0
        sorted_materials = materials_df.sort_values(by=["Levenstain"],#, "Name Length"],
                                                          ascending=[False])
        print("Simularity5")
        return sorted_materials[['Материал', "Полное наименование материала"]].head(5)
        # max_similarity_idxs = np.argsort(Levenstain)
        # return max_similarity_idxs[::-1]

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
        # all = [(i[:-2] if i[-2:]==".0" else i) for i in all]
        print('second metric -', all)
        # Функция для подсчёта совпадающих слов и проверки наличия числовых параметров
        def count_matches_and_numeric(query_numbers, material_name):
            material_words = material_name.lower().split()  # Разбиение названия материала на слова
            coincidences = []
            k = 0
            for num in query_numbers:
                num = num.strip()
                if num in material_words:
                    ind = material_words.index(num)
                    coincidences += [[ind, num]]
                    material_words[ind] = ""
                    k+=1
                    # continue
                elif num.isdigit():
                    coincidences += [""]
                    # continue
                elif num[:-1].isdigit():
                    if num[:-1] in material_words:
                        ind = material_words.index(num[:-1])
                        coincidences += [[ind, num[:-1]]]
                        material_words[ind] = ""
                        k += 1
                        # continue
                elif num[1:].isdigit():
                    if num[1:] in material_words:
                        ind = material_words.index(num[1:])
                        coincidences += [[ind, num[1:]]]
                        material_words[ind] = ""
                        k += 1
                        # continue
                else:
                    coincidences += [""]

            _size = len(coincidences)
            numeric_presence = sum(((_size-ind)/(abs(num[0]-ind)+1))**0.1
                                   for ind, num in enumerate(coincidences) if num != "")

            # if 'труба' in material_name and "труба" in query_numbers:
            #     print(coincidences, numeric_presence)
            return numeric_presence

        # Применение функции подсчёта к каждому материалу
        materials_df["Numeric Presence"] = materials_df["Полное наименование материала"].apply(
            lambda x: count_matches_and_numeric(all, x))
        try:
            # print(materials_df["Материал"].tolist()[:5], self.otgruzki['Код материала'].tolist()[:5])
            materials_df.loc[~materials_df["Материал"].isin(self.otgruzki['Код материала'].tolist()),
                                                            "Numeric Presence"] -= 200

            # print(materials_df[materials_df["Полное наименование материала"].str.contains('арматура 30')])
        except Exception as exc:
            print(exc)
        max_similarity_idxs = np.argsort(materials_df["Numeric Presence"])
        return max_similarity_idxs[::-1]

    def new_mat_prep(self, new_mat:str, val_ei:str=None, ei:str=None):
        # new_mat = new_mat.replace('/', '')

        morph = pymorphy3.MorphAnalyzer()

        new_mat = ' '.join(new_mat.split())
        new_mat = self.kw.replace_words(new_mat)
        new_mat = self.kw.split_numbers_and_words(new_mat)
        # print('Поиск едениц измерения -', end - start)

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
                    self.write_logs('Ошибка с поиском ei', event=0)

        return new_mat.strip(), val_ei, ei

    def paralell_rows(self, rows):
        # Удаление элементов с дублирующимися нулевыми значениями
        seen = set()
        unique_rows = []
        for row in rows:
            if row[0] not in seen:
                unique_rows.append(row)
                seen.add(row[0])

        print(f'Удалено {len(rows) - len(unique_rows)} дубликатов, осталось {len(unique_rows)} уникальных позиций.')
        rows = [(i, i2, i3) for i, i2, i3 in rows if len(i) > 5 and i[0] != '+']
        kols = len(rows)
        my_threads = []
        self.results = [""]
        self.poss = [""]*kols
        self.results[0] = {"req_Number": str(uuid.uuid4())}
        for idx, (row, ei, val_ei) in enumerate(rows):
            try:
                my_threads += [Thread(target=self.find_mats, args=[row, val_ei, ei, idx])]
                my_threads[-1].start()
            except Exception as exc:
                print(exc)

        for ind, thread in enumerate(my_threads):
            thread.join()
            print(f"Завершили {ind + 1} поток")

        print("вот тут", self.poss)
        self.results[0]["positions"] = self.poss
        self.saves.loc[self.results[0]["req_Number"]] = ["{'positions':" + str(self.results[0]["positions"]) + "}"]
        self.saves.to_csv('data/saves.csv')
        # print("results -", self.results)
        return str(self.results)

    def find_mats(self, row:str, val_ei:str, ei:str, idx:int):
        self.poss[idx] = {'position_id': str(idx)}
        self.poss[idx]['request_text'] = row
        ###############################
        new_mat, val_ei, ei = self.new_mat_prep(row, val_ei, ei)
        print('--', new_mat)


        self.poss[idx]['value'] = val_ei
        self.poss[idx]['ei'] = ei

        #################################
        try:
            first_ierar = self.models.get_pred(new_mat)
        except Exception as exc:
            print('Ошибка', exc)
        print(new_mat, "ИЕР-1", first_ierar)
        tr = self.all_materials['Название иерархии-1'] == first_ierar
        materials_df = self.all_materials#[tr]
        advanced_search_results = self.find_top_materials_advanced(new_mat,
                                materials_df[['Материал', "Полное наименование материала"]])
        # materials_df.iloc[:, -1] = materials_df.iloc[: -1].astype(float)
        materials_df.loc[tr, materials_df.columns[-1]] *= 0.7
        ress = advanced_search_results.values
        ress = materials_df[['Материал', "Полное наименование материала"]].iloc[ress[:5]]
        ress = ress.values
        print(ress)
        print('Вот это ищем', new_mat)
        if new_mat in self.method2.question.to_list():
            print('Нашёл')
            foundes = self.method2[self.method2.question == new_mat].answer.to_list()
            true_positions = []
            for pos in foundes[::-1]:
                temp = json.loфds(base64.b64decode(pos).decode('utf-8').replace("'", '"'))
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
        # print(new_mat, '=', ress[0][1]+'|'+ str(val_ei) +'-'+ ei +'|')
        # print(ress, end ='\n----\n')
        for ind, pos in enumerate(ress):
            self.poss[idx]['material'+str(ind+1)+'_id'] = '0'*(18-len(str(pos[0])))+str(pos[0])


if __name__ == '__main__':
    print('Введите наименования ниже для поиска их в базе:')
    rows = []
    find_mats = Find_materials()
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
    find_mats.paralell_rows(rows)