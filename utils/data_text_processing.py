import pymorphy3
from split_by_keys import Key_words
import re
import logger

def find_ei(new_mat, val_ei, ei):
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

def new_mat_prep(new_mat:str, val_ei:str=None, ei:str=None):
        morph = pymorphy3.MorphAnalyzer()

        kw = Key_words()

        new_mat = ' '.join(new_mat.split())
        new_mat = kw.replace_words(new_mat)
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
            return find_ei(new_mat, val_ei, ei)
        return new_mat.strip()

def clean_text(text:str):
    text = text.replace("\xa0", ' ')
    while ' \n' in text or '\n ' in text or '\n\n' in text:
        text = text.replace(' \n', '\n').replace('\n ', '\n').replace('\n\n', '\n')
    return text.strip()
