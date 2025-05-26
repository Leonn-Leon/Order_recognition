from Levenshtein import ratio
import pandas as pd
import uuid
import json
import base64
from order_recognition.utils.data_text_processing import Data_text_processing
import numpy as np
from order_recognition.work_with_models.models_manager import Use_models
from multiprocessing import Process, Pool

class Find_materials():
    def __init__(self):
        pd.options.mode.copy_on_write = True
        self.models = Use_models()
        self.all_materials = pd.read_csv('order_recognition/data/mats.csv', dtype=str)
        self.otgruzki = pd.read_csv('order_recognition/data/otgruzki.csv', sep=';')
        self.otgruzki['Код материала'] = self.otgruzki['Код материала'].astype(int)
        self.method2 = pd.read_csv('order_recognition/data/method2.csv')
        self.saves = pd.read_csv('order_recognition/data/saves.csv', index_col='req_Number')
        # Добавление длины названия
        self.all_materials["Name Length"] = self.all_materials["Полное наименование материала"].str.len()
        print('All materials opened!', flush=True)
        self.dp = Data_text_processing()

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
        materials_df = materials_df.assign(
            **{"Numeric Presence": materials_df["Полное наименование материала"].apply(
                lambda x: count_matches_and_numeric(all, x)
            )}
        )
        try:
            materials_df.loc[materials_df["Материал"].isin(self.otgruzki['Код материала'].tolist()), "Numeric Presence"] += 200
            if not materials_df.empty: # Проверка, что DataFrame не пустой
                scores = materials_df["Numeric Presence"]
                min_score = scores.min()
                max_score = scores.max()
                if max_score > min_score:
                    materials_df["Numeric Presence"] = (scores - min_score) / (max_score - min_score)
                else: # Все значения одинаковы
                    materials_df["Numeric Presence"] = 1.0 if max_score > 0 else 0.0
        except Exception as exc:
            print(exc)
        max_similarity_idxs = np.argsort(materials_df["Numeric Presence"])
        # Отправить также и отсортированные materials_df["Numeric Presence"]materials_df.iloc[max_similarity_idxs[::-1]]
        return materials_df.iloc[max_similarity_idxs[::-1]]

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
        
        tasks = [[row, val_ei, ei, idx] for idx, (row, ei, val_ei) in enumerate(rows)]
        
        with Pool(5) as pool:
            result_from_processes = pool.map(self.find_mats, tasks)
            
        for res in result_from_processes:
            self.poss[int(res["position_id"])] = res

        # print("вот тут", self.poss)
        self.results[0]["positions"] = self.poss
        self.saves.loc[self.results[0]["req_Number"]] = ["{'positions':" + str(self.results[0]["positions"]) + "}"]
        self.saves.to_csv('order_recognition/data/saves.csv')
        # print("results -", self.results)
        return str(self.results)

    def find_mats(self, args):
        row, val_ei, ei, idx = args
        local_poss = {'position_id': str(idx)}
        local_poss['request_text'] = row
        ###############################
        new_mat, val_ei, ei = self.dp.new_mat_prep(row, val_ei, ei)
        print('--', new_mat)


        local_poss['value'] = val_ei
        local_poss['ei'] = ei

        materials_df = self.all_materials#[tr]
        advanced_search_results = self.find_top_materials_advanced(new_mat,
                                materials_df[['Материал', "Полное наименование материала"]])
        # ress = advanced_search_results.values
        ress = advanced_search_results[:5]
        ress = ress.values
        # print(ress)
        # print('Вот это ищем', new_mat)
        if new_mat in self.method2.question.to_list():
            print('Нашёл', new_mat)
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
                ress += [[tp["num_mat"], tp["name_mat"], "0.95"]]
            ress += itog
            ress = ress[:5]
        # print(new_mat, '=', ress[0][1]+'|'+ str(val_ei) +'-'+ ei +'|')
        # print(ress, end ='\n----\n')
        for ind, pos in enumerate(ress):
            local_poss['material'+str(ind+1)+'_id'] = '0'*(18-len(str(pos[0])))+str(pos[0])
            local_poss["weight_"+str(ind+1)+""] = str(pos[2])
        return local_poss


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