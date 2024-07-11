from Use_models import Use_models
import pandas as pd
import json
import base64

data = pd.read_csv('data/mats5.csv')

models = Use_models()
method2 = pd.read_csv('data/method2.csv')
method2.reset_index(drop=True, inplace=True)
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
print('Done!')
