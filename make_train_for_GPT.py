import pandas as pd
import json
df = pd.read_csv("data/msgs_ei_marked.csv", index_col=0)
itog = {"request": [{"role":"system", "text":df.iloc[0].text}, {"role":"user", "text":""}], "response":""}
for i in df.to_numpy()[1:]:
    if i[0] == "user":
        _text = i[1].replace('"', "''").replace('\xa0', ' ')
        while '\n ' in _text:
            _text = _text.replace('\n ', '\n')
        while '\r\n' in _text:
            _text = _text.replace('\r\n', '\n')
        while '\n\n' in _text:
            _text = _text.replace('\n\n', '\n')
        itog["request"][1]["text"] = _text
    else:
        if type(i[1]) != type('ст9рока'):
            continue
        # print(i[0])
        # Нужно рекурсивно заменить \n\n на \n
        # В msgs дубликатов нет я проверил
        itog["response"] = i[1].replace('"', "''").replace('\r', ' ')
        print(json.dumps(itog, ensure_ascii=False))