from models_manager import Use_models
import pandas as pd
import json
import base64
from utils.split_by_keys import Key_words
import pymorphy3

def new_mat_prep(new_mat: str):
    # new_mat = new_mat.replace('/', '')

    morph = pymorphy3.MorphAnalyzer()

    new_mat = ' '.join(new_mat.split())
    new_mat = Key_words().replace_words(new_mat)
    new_mat = Key_words().split_numbers_and_words(new_mat)
    # print('Поиск едениц измерения -', end - start)

    new_mat += ' '
    new_lines = ''
    for word in new_mat.split():
        new_word = word
        if word.isdigit():
            if int(word) % 100 == 0 and len(word) >= 4:
                new_num = str(int(word) / 1000)
                new_word = new_num
        elif word.isalpha():
            new_word = morph.parse(new_word)[0].normal_form
        new_lines += new_word + ' '
    new_mat = new_lines
    return new_mat.strip()

def add_method2():
    data = pd.read_csv('data/mats.csv')

    method2 = pd.read_csv('data/method2.csv')
    method2.reset_index(drop=True, inplace=True)
    method2['question'] = method2['question'].apply(lambda x: new_mat_prep(x))
    method2 = method2.to_numpy()

    data_path_zero = 'data/for_zero.csv'
    data_path_first = 'data/for_firsts.csv'
    data_zero  = pd.read_csv(data_path_zero)
    data_first = pd.read_csv(data_path_first)
    for mat, answer in method2:
        answer = json.loads(base64.b64decode(answer).decode('utf-8').replace("'", '"'))
        try:
            first_right = data[data['Материал'].apply(str) == answer['num_mat']]['Название иерархии-1'].values[0]
            zero_right = data[data['Материал'].apply(str) == answer['num_mat']]['Название иерархии-0'].values[0]
        except:
            print(answer)
            continue
        data_zero.loc[data_zero.shape[0]] = [zero_right, mat]
        data_first.loc[data_first.shape[0]] = [zero_right, first_right, mat]

    data_zero.to_csv(data_path_zero, index=False)
    data_first.to_csv(data_path_first, index=False)
    print('All data from method2 added!')
