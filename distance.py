from Levenshtein import ratio
from difflib import SequenceMatcher
import re
import jellyfish
import pandas as pd
import uuid
import time
from datetime import datetime
from find_ei import find_quantities_and_units
from fuzzywuzzy import process, fuzz

class Find_materials():
    def __init__(self):
        self.all_materials = pd.read_csv('data/mats.csv')
        print('All materials opened!')

    def write_logs(self, text, event=1):
        event = 'EVENT' if event == 1 else 'ERROR'
        date_time = datetime.now().astimezone()
        file_name = './logs/' + str(date_time.date()) + '.txt'
        log = open(file_name, 'a')
        log.write(str(date_time) + ' | ' + event + ' | ' + text + '\n')
        log.close()

    # def choose_based_on_similarity(self, text):
    #     # query = vector_to_text(query_vector)  # Преобразование вектора обратно в текст
    #     # Использование FuzzyWuzzy для нахождения топ-5 наиболее подходящих продуктов
    #     top_matches = process.extract(text, self.all_materials.iloc[:, 1], scorer=fuzz.ratio, limit=5)
    #     # Получаем индексы этих продуктов
    #     print(top_matches)
    #     top_indices = [(match[0], match[1]) for match in top_matches]
    #     return top_indices

    def jaccard_distance(self, str1, str2):
        a = set(str1)
        b = set(str2)
        intersection = len(a.intersection(b))
        union = len(a.union(b))
        return 1 - intersection / union

    def choose_based_on_similarity(self, text):
        nearest_mats = []
        for material in self.all_materials.iloc[59:].values:
            distance = ratio(text, material[1])
            # distance = self.jaccard_dastance(text, material[1])
            nearest_mats += [(material[0], material[1], distance)]
        return nearest_mats


    def find_mats(self, rows):
        results = []
        around_material = ''
        results += [{"req_Number": str(uuid.uuid4())}]
        poss = []
        ei = 'шт'
        val_ei = 1.0
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
            new_row = new_row.replace(' -', ' ')\
                .replace(' — ', ' ') \
                .replace(' м', 'м')\
                .replace(' кг', 'кг')\
                .replace(' мл', 'мл') \
                .replace(' шт', 'шт') \
                .replace(' тн', 'тн')\
                .replace(' т', 'т')
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
            new_mat = new_mat.lower().replace('х', ' ') \
                .replace('(', '') \
                .replace(')', '') \
                .replace(' оц.', ' оц') \
                .replace('x', ' ')\
                .replace(':', '')
            new_mat = new_mat.replace('шв ', 'швеллер ') \
                .replace('рифл ', 'рифленый ') \
                .replace('гн ', 'гнутый ') \
                .replace('гнут ', 'гнутый ') \
                .replace('нут ', 'гнутый ') \
                .replace('гут ', 'гнутый ') \
                .replace('тр ', 'труба ') \
                .replace('тр. ', 'труба ') \
                .replace('проф ', 'профиль')\
                .replace('*', ' ') \
                .replace('метра', 'м') \
                .replace('метров', 'м')\
                .replace('мм', '')\
                .replace(' -', ' ')\
                .replace('м.', 'м') \
                .replace('шт.', 'шт') \
                .replace('мп.', 'мп') \
                .replace('кг.', 'кг') \
                .replace('тн', 'тн')\
                .replace('-шт', 'шт') \
                .replace('-мп', 'мп') \
                .replace('-кг', 'кг') \
                .replace('-т', 'т')\
                .replace('  ', ' ')\
                .replace(' /к', ' х/к')\
                .replace('бу та', 'бухта') \
                .replace('гост', '')\
                .replace(' — ', ' ') + ' '
            new_mat = new_mat.replace('профтруба', 'труба профил')
            if len([i for i in new_mat if i.isdigit()]) == 0:
                no_numbers = True
                continue
            if 'ооо' in new_mat or 'г.' in new_mat or 'ул.' in new_mat:
                continue
            if 'привет' in new_mat or '&' in new_mat or '{' in new_mat or '}' in new_mat:
                continue
            if 'добрый' in new_mat or 'прошу' in new_mat or 'здравс' in new_mat or\
                    'тел' in new_mat or 'часовой' in new_mat or 'достав' in new_mat or 'нужн' in new_mat:
                continue
            if 'швеллер' in new_mat:
                new_mat = new_mat.replace('у ', ' у ')\
                    .replace('п ', ' п ')\
                    .replace('п, ', ' п ')
            if 'арматура' in new_mat:
                new_mat = new_mat.replace(' i', ' a-i')
            val_ei, ei = find_quantities_and_units(new_mat)
            # print('Поиск едениц измерения -', end - start)
            poss+=[{'position_id':str(pos_id)}]
            pos_id += 1
            ress = sorted(self.choose_based_on_similarity(new_mat), key=lambda item:item[2])[-5:][::-1]
            print(new_mat, ' =', ress[0][0]+'|'+ str(val_ei) +'-'+ ei +'|')
            print(ress, end ='\n----\n')
            poss[-1]['request_text'] = new_mat
            poss[-1]['ei'] = ei
            poss[-1]['value'] = str(val_ei)
            for ind, pos in enumerate(ress):
                poss[-1]['material'+str(ind+1)+'_id'] = '0'*(18-len(pos[0]))+pos[0]

        results[0]["positions"] = poss
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
'''
@page wordsection1 
@list l0 
@list l0level1 
@list l0level1 
швеллер 16 п – 28,116т 
0
'''
'''
труба 20 2,8 гост 3262-75 
30
0

'''
'''
Арматура 6 бухта А500 С 34028-16	3 кг
Арматура 8 6м А-III 25Г2С 5781-82	8шт
Арматура 8 бухта А-III 25Г2С 5781-82 21.2тн
Арматура 8 бухта А500 С 34028-16	15метров
уголок ст3  90 90 7 20м.
               шв нут  140 60 4 12 11.0 3 м
0
'''
'''
уголок ст3  90 90 7
               шв нут  140 60 4 12
шв гут 100 50 4 12 м
 тр. проф 60 60 2
 60 40 2
60 40 3
40 40 2
40 20 2
20 20 
 лист 3 1250 2500
лист рифл 4 чечевицa
труба вгп 32*3,2
'''

'''
Балка 20Б1
Швеллер 20у
Швеллер 14у
Швеллер 12у
Швеллер 10у
шв гн  160*60
шв гн 140*60
лист рифл 5*1500*6000
'''
'''
Добрый день!
Прошу рассчитать стоимость и срок изготовления: 
 
Уголок оц. 50х430х0,7мм — 1800м.
Уголок оц. 50х460х0,7мм — 176м
Уголок оц. 50х280х0,7мм — 265м
 
Длина 1,25м допускается.
'''
'''
Профиль горизонтaльный ПН-6 (100х40х3000) 0,5мм  - 224шт/1 пал,

 Профиль стоечный ПС-6 (100х50х3000) 0,5мм  - 336шт/2 пал ,

  Профиль горизонтальный ПН-2 (50х40х3000) 0,5мм - 1440шт/ 3 пал,

 Профиль потолочный ПП-1 (60х27х3000) 0,5мм  -1728шт/ 3 пал,

 Профиль (50х40х3000)  горизонтальный ПН-2   0,45мм -480шт/1 пал  ,

Профиль (50х50х3000) стоечный ПС-2   0,45мм - 360шт/ 1 пал  ,

  Профиль (60х27х3000) потолочный ПП-1  0,45мм -576шт/ 1 пал ,

 Профиль (75х50х3000) стоечный ПС-4 0,6мм 240шт/ 1 пал.
0
'''