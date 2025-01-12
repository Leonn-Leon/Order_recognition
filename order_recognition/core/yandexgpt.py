import os
from hash2text import text_from_hash
import json
import time
import pandas as pd
import requests
from datetime import datetime
from order_recognition.confs.config import Authorization_AIM, xfolderid, gpt_version_id, gpt_url
import jwt
from thread import Thread
from order_recognition.utils import logger


class custom_yandex_gpt():
    def __init__(self):
        self.headers = {"Authorization": "Bearer " + Authorization_AIM,
                   "x-folder-id": xfolderid }
        df = pd.read_csv("data/msgs_ei.csv", index_col=0).tail(3)
        self.msgs = df.to_numpy()
        self.msgs = [{"role":i[0], "text":i[1].replace('\xa0', ' ').replace('"', "''")} for i in self.msgs]
        self.req = {
            "modelUri": "ds://"+gpt_version_id,
            "completionOptions": {
                "stream": False,
                "temperature": 0.1,
                "maxTokens": "4000"
            },
            "messages": [
                {
                    "role": "system",
                    "text": self.msgs[0]['text']
                }
            ]
        }

        with open('order_recognition/confs/ygpt_keys.json', 'r') as f:
            obj = f.read()
            obj = json.loads(obj)
            self.private_key = obj['private_key']
            self.key_id = obj['id']
            self.service_account_id = obj['service_account_id']


    def get_iam_token(self):
        # Replace the next line with your service account ID and private key.
        now = int(time.time())
        payload = {
            'aud': 'https://iam.api.cloud.yandex.net/iam/v1/tokens',
            'iss': self.service_account_id,
            'iat': now,
            'exp': now + 3600
        }
        jwt_token = jwt.encode(
            payload, self.private_key, algorithm="PS256", headers={"kid": self.key_id}
        )
        headers = {"Content-Type": "application/json"}
        data = {"jwt": jwt_token}
        # swapping JWT token to IAM
        response = requests.post('https://iam.api.cloud.yandex.net/iam/v1/tokens', headers=headers, json=data)
        if response.status_code // 100 == 2:
            return response.json()['iamToken']
        else:
            print("Не получилось обменять токены", response.status_code)
            return None  # Handle error appropriately

    def update_token(self):
        self.iam_token = self.get_iam_token()
        self.headers["Authorization"] = "Bearer " + self.iam_token

    def big_mail(self, text):
        text = text.split('\n')

        kols = len(text)//30+1
        self.ress = [""]*kols
        my_threads = []
        for i in range(kols):
            my_threads += [Thread(target=self.get_pos, args=['\n'.join(text[max(0, i*27-3):(i+1)*27]), i, False])]

            my_threads[-1].start()

        for ind, thread in enumerate(my_threads):
            thread.join()
            print(f"Завершили {ind+1} поток")

        self.ress = [mini_r for r in self.ress for mini_r in r if r != '']
        return self.ress

    def get_pos(self, text:str, idx:int):
        """
        Описание функции: 
        
    
        Args:
            text (str): _description_ - 
            idx (int): _description_
        """
        self.update_token()
        text = text.replace('"', "''")
        self.msgs += [{"role": "user", "text": text}]
        if len(self.msgs[-1]['text'])<10:
            self.ress[idx] = ""
        prompt = self.req.copy()
        # print(prompt['messages'][0])
        prompt['messages'] = [prompt['messages'][0], self.msgs[-1]]
        # start = time.time()
        _try = 0
        while _try<45:
            start = time.time()
            try:
                res = requests.post(gpt_url,
                                    headers=self.headers, json=prompt)
            except Exception as exc:
                logger.write_logs("Не получилось отправить запрос в YaGPT"+str(exc))
                print("Не получилось отправить запрос в YaGPT"+str(exc), flush=True)
            # print(str(res.text))
            if 'error' not in res.text:
                print('Вышел!', idx, 'try -', _try)
                break
            elif res.status_code == 400:
                print('Ошибка в письме', _try, prompt['messages'][-1])
                break
            else:
                print("Ошибка у YandexGPT:", idx, 'try -', _try, res.text)
            time.sleep(1)
            _try += 1
        logger.write_logs('Время на запрос, ' + str(time.time() - start))
        print('Время на запрос, ', time.time() - start, flush=True)
        try:
            answer = json.loads(res.text)['result']['alternatives'][0]['message']['text']
        except:
            logger.write_logs(res.text, event=0)
            print(res.text)
        try:
            self.ress[idx] = self.split_answer(answer, text)
            # return self.split_answer(answer)
        except:
            print('Не получилось распознать')
            self.ress[idx] = ""
            # return []

    def has_no_numbers(self, inputString):
        return not any(char.isdigit() for char in inputString)

    def split_answer(self, answer):
        """
        Разбивает ответ на список позиций
        Разбивает на 3 поля: наименование, ед.изм, кол-во

        Args:
            answer (str): расшифрованное письмо

        Returns:
            list: _description_ - список позиций
        """
        answer = answer.split('\n')
        answer_ei = []
        filter = ['телефон', 'товар', 'письмо', 'звонк', 'ооо', 'г.', 'служба', '@', 'город', '.ru', 'сообщ', 'комп', 'качеств']
        was_poss = []
        for pos in answer:
            s = pos.split('|')
            s[0] = s[0].lower()
            if any(i in s[0] for i in filter):
                continue
            if len(s) < 3:
                if len(pos) != 0:
                    answer_ei += [(pos, 'шт', '1')]
            else:
                if s[0] in was_poss or self.has_no_numbers(s[0]):
                    continue
                if len(s[-2].split()) < 1:
                    s[-2] = 'шт'
                if len(s[-1].split()) < 1:
                    s[-1] = '1'
                answer_ei += [(s[-3], s[-2], s[-1])]
                was_poss += [s[0]]
        return answer_ei


if __name__ == "__main__":
    ygpt = custom_yandex_gpt()
    ygpt.get_pos("лист нлг 6 2 6 09г2с 19281 ф 6.00")
    # hashs = ["UEQ5NGJXd2dkbVZ5YzJsdmJqMG5NUzR3SnlCbGJtTnZaR2x1WnowbmRYUm1MVGduUHo0OGMyOWhjR1Z1ZGpwRmJuWmxiRzl3WlNCNGJXeHVjenB6YjJGd1pXNTJQU0pvZEhSd09pOHZjMk5vWlcxaGN5NTRiV3h6YjJGd0xtOXlaeTl6YjJGd0wyVnVkbVZzYjNCbEx5SStQSE52WVhCbGJuWTZRbTlrZVQ0OGFuTnZiazlpYW1WamRENDhiMkpxWldOMFRtRnRaVDV0YzJkZk56TmxNVFF6TW1Wa01tRXdZbVZsTTJNMFl6WXpaakF6WWpFM1lXRXhNMk04TDI5aWFtVmpkRTVoYldVK1BHSjFZMnRsZEU1aGJXVStZM0p0TFdWdFlXbHNQQzlpZFdOclpYUk9ZVzFsUGp4bWFXeGxRMjl1ZEdWdWRENG1iSFE3YUhSdGJENG1JM2hrT3dvbWJIUTdhR1ZoWkQ0bUkzaGtPd29tYkhRN2JXVjBZU0JvZEhSd0xXVnhkV2wyUFNKRGIyNTBaVzUwTFZSNWNHVWlJR052Ym5SbGJuUTlJblJsZUhRdmFIUnRiRHNnWTJoaGNuTmxkRDExZEdZdE9DSStKaU40WkRzS0pteDBPeTlvWldGa1BpWWplR1E3Q2lac2REdGliMlI1UGlZamVHUTdDaVpzZER0d0lITjBlV3hsUFNKbWIyNTBMWE5wZW1VNk1UQndkRHNnWTI5c2IzSTZJekF3TURCbVppSStKbXgwTzJrKzBKTFFuZENWMEtqUW5kQ3YwSzhnMEovUW50Q24wS0xRa0RvZzBKWFJnZEM3MExnZzBMN1JndEMvMFlEUXNOQ3kwTGpSZ3RDMTBMdlJqQ0RRdmRDMTBMalF0OUN5MExYUmdkR0MwTFhRdlN3ZzBMM1F0U0RRdjlDMTBZRFF0ZEdGMEw3UXROQzQwWUxRdFNEUXY5QytJTkdCMFlIUmk5QzcwTHJRc05DOExDRFF2ZEMxSU5DKzBZTFF2OUdBMExEUXN0QzcwWS9RdWRHQzBMVWcwTC9Rc05HQTBMN1F1OUM0TENEUmdTRFF2dEdCMFlMUXZ0R0EwTDdRdHRDOTBMN1JnZEdDMFl6UmppRFF2dEdDMExyUmdOR0wwTExRc05DNTBZTFF0U0RRc3RDNzBMN1F0dEMxMEwzUXVOR1BMaVpzZERzdmFUNG1iSFE3TDNBK0ppTjRaRHNLSm14ME8ySnlQaVlqZUdRN0NpWnNkRHRpY2o0bUkzaGtPd29tYkhRN1luSStKaU40WkRzS0pteDBPMkp5UGlZamVHUTdDaVpzZER0a2FYWStKaU40WkRzS0pteDBPMlJwZGlCemRIbHNaVDBpWm05dWRDMW1ZVzFwYkhrNklHRnlhV0ZzTENCb1pXeDJaWFJwWTJFc0lITmhibk10YzJWeWFXWTdJR1p2Ym5RdGMybDZaVG9nTVRKd2REc2dZMjlzYjNJNklDTXdNREF3TURBaVBpWWplR1E3Q2lac2REdGthWFkrMEpUUXZ0Q3gwWURRdnRDMUlOR0QwWUxSZ05DK0lTRWhJU0VtWVcxd08yNWljM0E3SU5DbTBMWFF2ZEN3Sm1GdGNEdHVZbk53T3lEUXVDRFF2ZEN3MEx2UXVOR0gwTGpRdFRvbWJIUTdMMlJwZGo0bUkzaGtPd29tYkhRN1pHbDJQaVpzZER0emNHRnVJSE4wZVd4bFBTSmpiMnh2Y2pvZ0l6QXdNREF3TURzZ1ptOXVkQzFtWVcxcGJIazZJR0Z5YVdGc0xDQm9aV3gyWlhScFkyRXNJSE5oYm5NdGMyVnlhV1k3SUdadmJuUXRjMmw2WlRvZ01UWndlRHNnWm05dWRDMXpkSGxzWlRvZ2JtOXliV0ZzT3lCbWIyNTBMWGRsYVdkb2REb2dOREF3T3lCc1pYUjBaWEl0YzNCaFkybHVaem9nYm05eWJXRnNPeUIwWlhoMExXbHVaR1Z1ZERvZ01IQjRPeUIwWlhoMExYUnlZVzV6Wm05eWJUb2dibTl1WlRzZ2QyOXlaQzF6Y0dGamFXNW5PaUF3Y0hnN0lIZG9hWFJsTFhOd1lXTmxPaUJ1YjNKdFlXdzdJR0poWTJ0bmNtOTFibVF0WTI5c2IzSTZJQ05tWm1abVptWTdJR1pzYjJGME9pQnViMjVsT3lCa2FYTndiR0Y1T2lCcGJteHBibVVnSVdsdGNHOXlkR0Z1ZERzaUlHUmhkR0V0YldObExYTjBlV3hsUFNKamIyeHZjam9nSXpBd01EQXdNRHNnWm05dWRDMW1ZVzFwYkhrNklHRnlhV0ZzTENCb1pXeDJaWFJwWTJFc0lITmhibk10YzJWeWFXWTdJR1p2Ym5RdGMybDZaVG9nTVRad2VEc2dabTl1ZEMxemRIbHNaVG9nYm05eWJXRnNPeUJtYjI1MExYZGxhV2RvZERvZ05EQXdPeUJzWlhSMFpYSXRjM0JoWTJsdVp6b2dibTl5YldGc095QjBaWGgwTFdsdVpHVnVkRG9nTUhCNE95QjBaWGgwTFhSeVlXNXpabTl5YlRvZ2JtOXVaVHNnZDI5eVpDMXpjR0ZqYVc1bk9pQXdjSGc3SUhkb2FYUmxMWE53WVdObE9pQnViM0p0WVd3N0lHSmhZMnRuY205MWJtUXRZMjlzYjNJNklDTm1abVptWm1ZN0lHWnNiMkYwT2lCdWIyNWxPeUJrYVhOd2JHRjVPaUJwYm14cGJtVWdJV2x0Y0c5eWRHRnVkRHNpUHRDUTBZRFF2TkN3MFlMUmc5R0EwTEFtSTNoa093b2cwWVEySU5DUU1qUXcwS0VnTVRMUXZDWmhiWEE3Ym1KemNEc2dMU0F3TERQUmd0QzlKbXgwT3k5emNHRnVQaVpzZER0aWNqNG1JM2hrT3dvbWJIUTdMMlJwZGo0bUkzaGtPd29tYkhRN1pHbDJQaVpzZER0emNHRnVJSE4wZVd4bFBTSmpiMnh2Y2pvZ0l6QXdNREF3TURzZ1ptOXVkQzFtWVcxcGJIazZJR0Z5YVdGc0xDQm9aV3gyWlhScFkyRXNJSE5oYm5NdGMyVnlhV1k3SUdadmJuUXRjMmw2WlRvZ01UWndlRHNnWm05dWRDMXpkSGxzWlRvZ2JtOXliV0ZzT3lCbWIyNTBMWGRsYVdkb2REb2dOREF3T3lCc1pYUjBaWEl0YzNCaFkybHVaem9nYm05eWJXRnNPeUIwWlhoMExXbHVaR1Z1ZERvZ01IQjRPeUIwWlhoMExYUnlZVzV6Wm05eWJUb2dibTl1WlRzZ2QyOXlaQzF6Y0dGamFXNW5PaUF3Y0hnN0lIZG9hWFJsTFhOd1lXTmxPaUJ1YjNKdFlXdzdJR0poWTJ0bmNtOTFibVF0WTI5c2IzSTZJQ05tWm1abVptWTdJR1pzYjJGME9pQnViMjVsT3lCa2FYTndiR0Y1T2lCcGJteHBibVVnSVdsdGNHOXlkR0Z1ZERzaUlHUmhkR0V0YldObExYTjBlV3hsUFNKamIyeHZjam9nSXpBd01EQXdNRHNnWm05dWRDMW1ZVzFwYkhrNklHRnlhV0ZzTENCb1pXeDJaWFJwWTJFc0lITmhibk10YzJWeWFXWTdJR1p2Ym5RdGMybDZaVG9nTVRad2VEc2dabTl1ZEMxemRIbHNaVG9nYm05eWJXRnNPeUJtYjI1MExYWmhjbWxoYm5RdGJHbG5ZWFIxY21Wek9pQnViM0p0WVd3N0lHWnZiblF0ZG1GeWFXRnVkQzFqWVhCek9pQnViM0p0WVd3N0lHWnZiblF0ZDJWcFoyaDBPaUEwTURBN0lHeGxkSFJsY2kxemNHRmphVzVuT2lCdWIzSnRZV3c3SUc5eWNHaGhibk02SURJN0lIUmxlSFF0WVd4cFoyNDZJSE4wWVhKME95QjBaWGgwTFdsdVpHVnVkRG9nTUhCNE95QjBaWGgwTFhSeVlXNXpabTl5YlRvZ2JtOXVaVHNnZDJsa2IzZHpPaUF5T3lCM2IzSmtMWE53WVdOcGJtYzZJREJ3ZURzZ0xYZGxZbXRwZEMxMFpYaDBMWE4wY205clpTMTNhV1IwYURvZ01IQjRPeUIzYUdsMFpTMXpjR0ZqWlRvZ2JtOXliV0ZzT3lCaVlXTnJaM0p2ZFc1a0xXTnZiRzl5T2lBalptUm1aR1prT3lCMFpYaDBMV1JsWTI5eVlYUnBiMjR0ZEdocFkydHVaWE56T2lCcGJtbDBhV0ZzT3lCMFpYaDBMV1JsWTI5eVlYUnBiMjR0YzNSNWJHVTZJR2x1YVhScFlXdzdJSFJsZUhRdFpHVmpiM0poZEdsdmJpMWpiMnh2Y2pvZ2FXNXBkR2xoYkRzZ1pHbHpjR3hoZVRvZ2FXNXNhVzVsSUNGcGJYQnZjblJoYm5RN0lHWnNiMkYwT2lCdWIyNWxPeUlnWkdGMFlTMXRZMlV0YzNSNWJHVTlJbU52Ykc5eU9pQWpNREF3TURBd095Qm1iMjUwTFdaaGJXbHNlVG9nWVhKcFlXd3NJR2hsYkhabGRHbGpZU3dnYzJGdWN5MXpaWEpwWmpzZ1ptOXVkQzF6YVhwbE9pQXhObkI0T3lCbWIyNTBMWE4wZVd4bE9pQnViM0p0WVd3N0lHWnZiblF0ZG1GeWFXRnVkQzFzYVdkaGRIVnlaWE02SUc1dmNtMWhiRHNnWm05dWRDMTJZWEpwWVc1MExXTmhjSE02SUc1dmNtMWhiRHNnWm05dWRDMTNaV2xuYUhRNklEUXdNRHNnYkdWMGRHVnlMWE53WVdOcGJtYzZJRzV2Y20xaGJEc2diM0p3YUdGdWN6b2dNanNnZEdWNGRDMWhiR2xuYmpvZ2MzUmhjblE3SUhSbGVIUXRhVzVrWlc1ME9pQXdjSGc3SUhSbGVIUXRkSEpoYm5ObWIzSnRPaUJ1YjI1bE95QjNhV1J2ZDNNNklESTdJSGR2Y21RdGMzQmhZMmx1WnpvZ01IQjRPeUF0ZDJWaWEybDBMWFJsZUhRdGMzUnliMnRsTFhkcFpIUm9PaUF3Y0hnN0lIZG9hWFJsTFhOd1lXTmxPaUJ1YjNKdFlXdzdJR0poWTJ0bmNtOTFibVF0WTI5c2IzSTZJQ05tWkdaa1ptUTdJSFJsZUhRdFpHVmpiM0poZEdsdmJpMTBhR2xqYTI1bGMzTTZJR2x1YVhScFlXdzdJSFJsZUhRdFpHVmpiM0poZEdsdmJpMXpkSGxzWlRvZ2FXNXBkR2xoYkRzZ2RHVjRkQzFrWldOdmNtRjBhVzl1TFdOdmJHOXlPaUJwYm1sMGFXRnNPeUJrYVhOd2JHRjVPaUJwYm14cGJtVWdJV2x0Y0c5eWRHRnVkRHNnWm14dllYUTZJRzV2Ym1VN0lqN1F2OUdBMEw3UXN0QyswTHZRdnRDNjBMQW1JM2hrT3dvZzBMTFJqOUMzMExEUXU5R00wTDNRc05HUElERXNNdEM4MEx3Z0xTQXlNemZRdXRDekpteDBPeTl6Y0dGdVBpWnNkRHNoTFMxRmJtUkdjbUZuYldWdWRDMHRQaVlqZUdRN0NpWnNkRHRrYVhZZ2MzUjViR1U5SW1Oc1pXRnlPaUJpYjNSb095SWdaR0YwWVMxdFkyVXRjM1I1YkdVOUltTnNaV0Z5T2lCaWIzUm9PeUkrSm14ME8ySnlJR1JoZEdFdGJXTmxMV0p2WjNWelBTSXhJajRtSTNoa093b21iSFE3TDJScGRqNG1JM2hrT3dvbWJIUTdMMlJwZGo0bUkzaGtPd29tYkhRN1pHbDJJR1JoZEdFdGJXRnlhMlZ5UFNKZlgxTkpSMTlRVDFOVVgxOGlQaTB0SUNac2REdGljajRtSTNoa093b21iSFE3TDJScGRqNG1JM2hrT3dvbWJIUTdaR2wyUHRDaElOR0QwTExRc05DMjBMWFF2ZEM0MExYUXZDd2cwTHZRdnRDejBMalJnZEdDSm14ME8ySnlQaVlqZUdRN0N0QzYwTDdRdk5DLzBMRFF2ZEM0MExnZ0ptRnRjRHR4ZFc5ME85Q2EwWURRdnRDeTBMWFF1OUdNMEwzUmk5QzVJTkNtMExYUXZkR0MwWUFtWVcxd08zRjFiM1E3Sm14ME8ySnlQaVlqZUdRN0N0Q2EwTERRdWRDMDBMRFF1OUM0MEwzUXNDRFFudEM2MFlIUXNOQzkwTEFnMEozUXVOQzYwTDdRdTlDdzBMWFFzdEM5MExBbWJIUTdZbkkrSmlONFpEc0swTE11SU5DYTBZRFFzTkdCMEwzUXZ0R1AwWURSZ2RDNkpteDBPMkp5UGlZamVHUTdDdEdDMExYUXV5NGdPRGs0TXpJMk5qUXpNekFtYkhRN1luSStKaU40WkRzSzBMclJnTkMrMExMUXRkQzcwWXpRdmRHTDBMblJodEMxMEwzUmd0R0FMdEdBMFlRdkpteDBPeTlrYVhZK0ppTjRaRHNLSm14ME95OWthWFkrSmlONFpEc0tKbXgwT3k5a2FYWStKaU40WkRzS0pteDBPeTlpYjJSNVBpWWplR1E3Q2lac2REc3ZhSFJ0YkQ0bUkzaGtPd284TDJacGJHVkRiMjUwWlc1MFBqd3Zhbk52Yms5aWFtVmpkRDQ4TDNOdllYQmxiblk2UW05a2VUNDhMM052WVhCbGJuWTZSVzUyWld4dmNHVSs="]
    # for h in hashs:
    #     text = text_from_hash(h)
    #     print(ygpt.get_pos(text, bag=False))
    #     break
    # print(y_gpt().get_pos(text))