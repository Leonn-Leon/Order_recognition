# from yandex_gpt import YandexGPTConfigManagerForAPIKey, YandexGPT, YandexGPTThread
import os
from hash2text import text_from_hash
import json
import time
import pandas as pd
import requests
from datetime import datetime
from config import Authorization_AIM, xfolderid, gpt_version_id, gpt_url
import jwt
from thread import Thread


class custom_yandex_gpt():
    def __init__(self):
        self.headers = {"Authorization": "Bearer " + Authorization_AIM,
                   "x-folder-id": xfolderid }
        df = pd.read_csv("data/msgs_ei.csv", index_col=0)
        self.msgs = df.to_numpy()
        self.msgs = [{"role":i[0], "text":i[1].replace('\xa0', ' ').replace('"', "''")} for i in self.msgs]
        self.req = {
            "modelUri": "ds://"+gpt_version_id,
            "completionOptions": {
                "stream": False,
                "temperature": 0.3,
                "maxTokens": "4000"
            },
            "messages": [
                {
                    "role": "system",
                    "text": self.msgs[0]['text']
                }
            ]
        }

        with open('data/ygpt_keys.json', 'r') as f:
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

    def write_logs(self, text, event=1):
        event = 'EVENT' if event == 1 else 'ERROR'
        date_time = datetime.now().astimezone()
        file_name = './logs/' + str(date_time.date()) + '.txt'
        with open(file_name, 'a', encoding="utf-8") as file:
            file.write(str(date_time) + ' | ' + event + ' | ' + text + '\n')

    def big_mail(self, text, save=False):
        while '\n\n' in text:
            text = text.replace('\n\n', '\n')
        text = text.split('\n')

        kols = len(text)//15+1
        self.ress = [""]*kols
        my_threads = []
        for i in range(kols):
            my_threads += [Thread(target=self.get_pos, args=['\n'.join(text[i*15:(i+1)*15]), i, save, False])]
            my_threads[-1].start()
            # res = self.get_pos('\n'.join(text[i*20:(i+1)*20]), save=save)
            # if len(res) != 0:
            #     ress += res

        for ind, thread in enumerate(my_threads):
            thread.join()
            print(f"Завершили {ind+1} поток")

        self.ress = [mini_r for r in self.ress for mini_r in r if r != '']
        print("RESSS", self.ress)
        return self.ress

    def get_pos(self, text:str, idx:int, save=False, bag=False):
        self.update_token()
        text = text.replace('\xa0', ' ').replace('"', "''")
        self.msgs += [{"role": "user", "text": text}]
        if len(self.msgs[-1]['text'])<10:
            self.ress[idx] = ""
        if bag:
            print('bag - ',self.msgs[-1]['text'])
            print('-' * 15)
        prompt = self.req.copy()
        # print(prompt['messages'][0])
        prompt['messages'] = [prompt['messages'][0], self.msgs[-1]]
        # start = time.time()
        _try = 0
        while _try<40:
            start = time.time()
            try:
                res = requests.post(gpt_url,
                                    headers=self.headers, json=prompt)
            except Exception as exc:
                self.write_logs("Не получилось отправить запрос в YaGPT"+str(exc))
                print("Не получилось отправить запрос в YaGPT"+str(exc), flush=True)
            # print(str(res.text))
            if 'error' not in res.text:
                print('Вышел!', _try)
                break
            elif res.status_code == 400:
                print('Ошибка в письме', _try, prompt['messages'][-1])
                break
            else:
                print("Ошибка у YandexGPT:", _try, res.text)
            time.sleep(1)
            _try += 1
        self.write_logs('Время на запрос, ' + str(time.time() - start))
        self.write_logs(str(res.text))
        print('Время на запрос, ', time.time() - start, flush=True)
        try:
            answer = json.loads(res.text)['result']['alternatives'][0]['message']['text']
        except:
            self.write_logs(res.text, event=0)
            print(res.text)
        if save:
            self.msgs += [{"role": "assistant", "text": answer}]
            pd.DataFrame(self.msgs).to_csv("data/msgs_ei.csv")
        try:
            self.ress[idx] = self.split_answer(answer, text)
            # return self.split_answer(answer)
        except:
            print('Не получилось распознать')
            self.ress[idx] = ""
            # return []

    def split_answer(self,answer, text):
        answer = answer.split('\n')
        answer_ei = []
        for pos in answer:
            s = pos.split('|')
            if len(s) < 3:
                if len(pos) != 0:
                    answer_ei += [(pos, 'шт', '1')]
                # continue
            else:
                if s[0].split()[0].lower() in text.lower() and "телефон" not in s[0] and 'письмо' not in s[0]:
                    if len(s[-2].split()) < 1:
                        s[-2] = 'шт'
                    if len(s[-1].split()) < 1:
                        s[-1] = '1'
                    answer_ei += [(s[-3], s[-2], s[-1])]
        return answer_ei

if __name__ == "__main__":
    ygpt = custom_yandex_gpt()
    ygpt.get_pos("лист нлг 6 2 6 09г2с 19281 ф 6.00")
    # hashs = ["UEQ5NGJXd2dkbVZ5YzJsdmJqMG5NUzR3SnlCbGJtTnZaR2x1WnowbmRYUm1MVGduUHo0OGMyOWhjR1Z1ZGpwRmJuWmxiRzl3WlNCNGJXeHVjenB6YjJGd1pXNTJQU0pvZEhSd09pOHZjMk5vWlcxaGN5NTRiV3h6YjJGd0xtOXlaeTl6YjJGd0wyVnVkbVZzYjNCbEx5SStQSE52WVhCbGJuWTZRbTlrZVQ0OGFuTnZiazlpYW1WamRENDhiMkpxWldOMFRtRnRaVDV0YzJkZk56TmxNVFF6TW1Wa01tRXdZbVZsTTJNMFl6WXpaakF6WWpFM1lXRXhNMk04TDI5aWFtVmpkRTVoYldVK1BHSjFZMnRsZEU1aGJXVStZM0p0TFdWdFlXbHNQQzlpZFdOclpYUk9ZVzFsUGp4bWFXeGxRMjl1ZEdWdWRENG1iSFE3YUhSdGJENG1JM2hrT3dvbWJIUTdhR1ZoWkQ0bUkzaGtPd29tYkhRN2JXVjBZU0JvZEhSd0xXVnhkV2wyUFNKRGIyNTBaVzUwTFZSNWNHVWlJR052Ym5SbGJuUTlJblJsZUhRdmFIUnRiRHNnWTJoaGNuTmxkRDExZEdZdE9DSStKaU40WkRzS0pteDBPeTlvWldGa1BpWWplR1E3Q2lac2REdGliMlI1UGlZamVHUTdDaVpzZER0d0lITjBlV3hsUFNKbWIyNTBMWE5wZW1VNk1UQndkRHNnWTI5c2IzSTZJekF3TURCbVppSStKbXgwTzJrKzBKTFFuZENWMEtqUW5kQ3YwSzhnMEovUW50Q24wS0xRa0RvZzBKWFJnZEM3MExnZzBMN1JndEMvMFlEUXNOQ3kwTGpSZ3RDMTBMdlJqQ0RRdmRDMTBMalF0OUN5MExYUmdkR0MwTFhRdlN3ZzBMM1F0U0RRdjlDMTBZRFF0ZEdGMEw3UXROQzQwWUxRdFNEUXY5QytJTkdCMFlIUmk5QzcwTHJRc05DOExDRFF2ZEMxSU5DKzBZTFF2OUdBMExEUXN0QzcwWS9RdWRHQzBMVWcwTC9Rc05HQTBMN1F1OUM0TENEUmdTRFF2dEdCMFlMUXZ0R0EwTDdRdHRDOTBMN1JnZEdDMFl6UmppRFF2dEdDMExyUmdOR0wwTExRc05DNTBZTFF0U0RRc3RDNzBMN1F0dEMxMEwzUXVOR1BMaVpzZERzdmFUNG1iSFE3TDNBK0ppTjRaRHNLSm14ME8ySnlQaVlqZUdRN0NpWnNkRHRpY2o0bUkzaGtPd29tYkhRN1luSStKaU40WkRzS0pteDBPMkp5UGlZamVHUTdDaVpzZER0a2FYWStKaU40WkRzS0pteDBPMlJwZGlCemRIbHNaVDBpWm05dWRDMW1ZVzFwYkhrNklHRnlhV0ZzTENCb1pXeDJaWFJwWTJFc0lITmhibk10YzJWeWFXWTdJR1p2Ym5RdGMybDZaVG9nTVRKd2REc2dZMjlzYjNJNklDTXdNREF3TURBaVBpWWplR1E3Q2lac2REdGthWFkrMEpUUXZ0Q3gwWURRdnRDMUlOR0QwWUxSZ05DK0lTRWhJU0VtWVcxd08yNWljM0E3SU5DbTBMWFF2ZEN3Sm1GdGNEdHVZbk53T3lEUXVDRFF2ZEN3MEx2UXVOR0gwTGpRdFRvbWJIUTdMMlJwZGo0bUkzaGtPd29tYkhRN1pHbDJQaVpzZER0aWNpQmtZWFJoTFcxalpTMWliMmQxY3owaU1TSStKaU40WkRzS0pteDBPeTlrYVhZK0ppTjRaRHNLSm14ME8yUnBkajRtYkhRN0lTMHRVM1JoY25SR2NtRm5iV1Z1ZEMwdFBpWWplR1E3Q2lac2REdGthWFlnYzNSNWJHVTlJbU52Ykc5eU9pQWpNREF3TURBd095Qm1iMjUwTFdaaGJXbHNlVG9nWVhKcFlXd3NJR2hsYkhabGRHbGpZU3dnYzJGdWN5MXpaWEpwWmpzZ1ptOXVkQzF6YVhwbE9pQXhNbkIwT3lCbWIyNTBMWE4wZVd4bE9pQnViM0p0WVd3N0lHWnZiblF0ZG1GeWFXRnVkQzFzYVdkaGRIVnlaWE02SUc1dmNtMWhiRHNnWm05dWRDMTJZWEpwWVc1MExXTmhjSE02SUc1dmNtMWhiRHNnWm05dWRDMTNaV2xuYUhRNklEUXdNRHNnYkdWMGRHVnlMWE53WVdOcGJtYzZJRzV2Y20xaGJEc2diM0p3YUdGdWN6b2dNanNnZEdWNGRDMWhiR2xuYmpvZ2MzUmhjblE3SUhSbGVIUXRhVzVrWlc1ME9pQXdjSGc3SUhSbGVIUXRkSEpoYm5ObWIzSnRPaUJ1YjI1bE95QjNhV1J2ZDNNNklESTdJSGR2Y21RdGMzQmhZMmx1WnpvZ01IQjRPeUF0ZDJWaWEybDBMWFJsZUhRdGMzUnliMnRsTFhkcFpIUm9PaUF3Y0hnN0lIZG9hWFJsTFhOd1lXTmxPaUJ1YjNKdFlXdzdJR0poWTJ0bmNtOTFibVF0WTI5c2IzSTZJQ05tWkdaa1ptUTdJSFJsZUhRdFpHVmpiM0poZEdsdmJpMTBhR2xqYTI1bGMzTTZJR2x1YVhScFlXdzdJSFJsZUhRdFpHVmpiM0poZEdsdmJpMXpkSGxzWlRvZ2FXNXBkR2xoYkRzZ2RHVjRkQzFrWldOdmNtRjBhVzl1TFdOdmJHOXlPaUJwYm1sMGFXRnNPeUlnWkdGMFlTMXRZMlV0YzNSNWJHVTlJbU52Ykc5eU9pQWpNREF3TURBd095Qm1iMjUwTFdaaGJXbHNlVG9nWVhKcFlXd3NJR2hsYkhabGRHbGpZU3dnYzJGdWN5MXpaWEpwWmpzZ1ptOXVkQzF6YVhwbE9pQXhNbkIwT3lCbWIyNTBMWE4wZVd4bE9pQnViM0p0WVd3N0lHWnZiblF0ZG1GeWFXRnVkQzFzYVdkaGRIVnlaWE02SUc1dmNtMWhiRHNnWm05dWRDMTJZWEpwWVc1MExXTmhjSE02SUc1dmNtMWhiRHNnWm05dWRDMTNaV2xuYUhRNklEUXdNRHNnYkdWMGRHVnlMWE53WVdOcGJtYzZJRzV2Y20xaGJEc2diM0p3YUdGdWN6b2dNanNnZEdWNGRDMWhiR2xuYmpvZ2MzUmhjblE3SUhSbGVIUXRhVzVrWlc1ME9pQXdjSGc3SUhSbGVIUXRkSEpoYm5ObWIzSnRPaUJ1YjI1bE95QjNhV1J2ZDNNNklESTdJSGR2Y21RdGMzQmhZMmx1WnpvZ01IQjRPeUF0ZDJWaWEybDBMWFJsZUhRdGMzUnliMnRsTFhkcFpIUm9PaUF3Y0hnN0lIZG9hWFJsTFhOd1lXTmxPaUJ1YjNKdFlXdzdJR0poWTJ0bmNtOTFibVF0WTI5c2IzSTZJQ05tWkdaa1ptUTdJSFJsZUhRdFpHVmpiM0poZEdsdmJpMTBhR2xqYTI1bGMzTTZJR2x1YVhScFlXdzdJSFJsZUhRdFpHVmpiM0poZEdsdmJpMXpkSGxzWlRvZ2FXNXBkR2xoYkRzZ2RHVjRkQzFrWldOdmNtRjBhVzl1TFdOdmJHOXlPaUJwYm1sMGFXRnNPeUkrSmlONFpEc0tKbXgwTzJScGRqN1FrTkdBMEx6UXNOR0MwWVBSZ05Dd0lOR0VNVFlnMEpBMU1ERFFvU0F4TXRDOEptRnRjRHR1WW5Od095QXRJREV5TERnMk5OR0MwTDBtYkhRN0wyUnBkajRtSTNoa093b21iSFE3WkdsMlBpWnNkRHR6Y0dGdUlITjBlV3hsUFNKamIyeHZjam9nSXpBd01EQXdNRHNnWm05dWRDMW1ZVzFwYkhrNklHRnlhV0ZzTENCb1pXeDJaWFJwWTJFc0lITmhibk10YzJWeWFXWTdJR1p2Ym5RdGMybDZaVG9nTVRad2VEc2dabTl1ZEMxemRIbHNaVG9nYm05eWJXRnNPeUJtYjI1MExYZGxhV2RvZERvZ05EQXdPeUJzWlhSMFpYSXRjM0JoWTJsdVp6b2dibTl5YldGc095QjBaWGgwTFdsdVpHVnVkRG9nTUhCNE95QjBaWGgwTFhSeVlXNXpabTl5YlRvZ2JtOXVaVHNnZDI5eVpDMXpjR0ZqYVc1bk9pQXdjSGc3SUhkb2FYUmxMWE53WVdObE9pQnViM0p0WVd3N0lHSmhZMnRuY205MWJtUXRZMjlzYjNJNklDTm1abVptWm1ZN0lHWnNiMkYwT2lCdWIyNWxPeUJrYVhOd2JHRjVPaUJwYm14cGJtVWdJV2x0Y0c5eWRHRnVkRHNpSUdSaGRHRXRiV05sTFhOMGVXeGxQU0pqYjJ4dmNqb2dJekF3TURBd01Ec2dabTl1ZEMxbVlXMXBiSGs2SUdGeWFXRnNMQ0JvWld4MlpYUnBZMkVzSUhOaGJuTXRjMlZ5YVdZN0lHWnZiblF0YzJsNlpUb2dNVFp3ZURzZ1ptOXVkQzF6ZEhsc1pUb2dibTl5YldGc095Qm1iMjUwTFhkbGFXZG9kRG9nTkRBd095QnNaWFIwWlhJdGMzQmhZMmx1WnpvZ2JtOXliV0ZzT3lCMFpYaDBMV2x1WkdWdWREb2dNSEI0T3lCMFpYaDBMWFJ5WVc1elptOXliVG9nYm05dVpUc2dkMjl5WkMxemNHRmphVzVuT2lBd2NIZzdJSGRvYVhSbExYTndZV05sT2lCdWIzSnRZV3c3SUdKaFkydG5jbTkxYm1RdFkyOXNiM0k2SUNObVptWm1abVk3SUdac2IyRjBPaUJ1YjI1bE95QmthWE53YkdGNU9pQnBibXhwYm1VZ0lXbHRjRzl5ZEdGdWREc2lQdENRMFlEUXZOQ3cwWUxSZzlHQTBMQW1JM2hrT3dvZzBZUXhNaURRa0RVd01OQ2hJREV5MEx3bVlXMXdPMjVpYzNBN0lDMGdOU3d3T0RqUmd0QzlKbXgwT3k5emNHRnVQaVpzZER0aWNqNG1JM2hrT3dvbWJIUTdMMlJwZGo0bUkzaGtPd29tYkhRN1pHbDJQaVpzZER0emNHRnVJSE4wZVd4bFBTSmpiMnh2Y2pvZ0l6QXdNREF3TURzZ1ptOXVkQzFtWVcxcGJIazZJR0Z5YVdGc0xDQm9aV3gyWlhScFkyRXNJSE5oYm5NdGMyVnlhV1k3SUdadmJuUXRjMmw2WlRvZ01UWndlRHNnWm05dWRDMXpkSGxzWlRvZ2JtOXliV0ZzT3lCbWIyNTBMWGRsYVdkb2REb2dOREF3T3lCc1pYUjBaWEl0YzNCaFkybHVaem9nYm05eWJXRnNPeUIwWlhoMExXbHVaR1Z1ZERvZ01IQjRPeUIwWlhoMExYUnlZVzV6Wm05eWJUb2dibTl1WlRzZ2QyOXlaQzF6Y0dGamFXNW5PaUF3Y0hnN0lIZG9hWFJsTFhOd1lXTmxPaUJ1YjNKdFlXdzdJR0poWTJ0bmNtOTFibVF0WTI5c2IzSTZJQ05tWm1abVptWTdJR1pzYjJGME9pQnViMjVsT3lCa2FYTndiR0Y1T2lCcGJteHBibVVnSVdsdGNHOXlkR0Z1ZERzaUlHUmhkR0V0YldObExYTjBlV3hsUFNKamIyeHZjam9nSXpBd01EQXdNRHNnWm05dWRDMW1ZVzFwYkhrNklHRnlhV0ZzTENCb1pXeDJaWFJwWTJFc0lITmhibk10YzJWeWFXWTdJR1p2Ym5RdGMybDZaVG9nTVRad2VEc2dabTl1ZEMxemRIbHNaVG9nYm05eWJXRnNPeUJtYjI1MExYZGxhV2RvZERvZ05EQXdPeUJzWlhSMFpYSXRjM0JoWTJsdVp6b2dibTl5YldGc095QjBaWGgwTFdsdVpHVnVkRG9nTUhCNE95QjBaWGgwTFhSeVlXNXpabTl5YlRvZ2JtOXVaVHNnZDI5eVpDMXpjR0ZqYVc1bk9pQXdjSGc3SUhkb2FYUmxMWE53WVdObE9pQnViM0p0WVd3N0lHSmhZMnRuY205MWJtUXRZMjlzYjNJNklDTm1abVptWm1ZN0lHWnNiMkYwT2lCdWIyNWxPeUJrYVhOd2JHRjVPaUJwYm14cGJtVWdJV2x0Y0c5eWRHRnVkRHNpUHRDUTBZRFF2TkN3MFlMUmc5R0EwTEFtSTNoa093b2cwWVEySU5DUU1qUXcwS0VnTVRMUXZDWmhiWEE3Ym1KemNEc2dMU0F3TERQUmd0QzlKbXgwT3k5emNHRnVQaVpzZER0aWNqNG1JM2hrT3dvbWJIUTdMMlJwZGo0bUkzaGtPd29tYkhRN1pHbDJQaVpzZER0emNHRnVJSE4wZVd4bFBTSmpiMnh2Y2pvZ0l6QXdNREF3TURzZ1ptOXVkQzFtWVcxcGJIazZJR0Z5YVdGc0xDQm9aV3gyWlhScFkyRXNJSE5oYm5NdGMyVnlhV1k3SUdadmJuUXRjMmw2WlRvZ01UWndlRHNnWm05dWRDMXpkSGxzWlRvZ2JtOXliV0ZzT3lCbWIyNTBMWGRsYVdkb2REb2dOREF3T3lCc1pYUjBaWEl0YzNCaFkybHVaem9nYm05eWJXRnNPeUIwWlhoMExXbHVaR1Z1ZERvZ01IQjRPeUIwWlhoMExYUnlZVzV6Wm05eWJUb2dibTl1WlRzZ2QyOXlaQzF6Y0dGamFXNW5PaUF3Y0hnN0lIZG9hWFJsTFhOd1lXTmxPaUJ1YjNKdFlXdzdJR0poWTJ0bmNtOTFibVF0WTI5c2IzSTZJQ05tWm1abVptWTdJR1pzYjJGME9pQnViMjVsT3lCa2FYTndiR0Y1T2lCcGJteHBibVVnSVdsdGNHOXlkR0Z1ZERzaUlHUmhkR0V0YldObExYTjBlV3hsUFNKamIyeHZjam9nSXpBd01EQXdNRHNnWm05dWRDMW1ZVzFwYkhrNklHRnlhV0ZzTENCb1pXeDJaWFJwWTJFc0lITmhibk10YzJWeWFXWTdJR1p2Ym5RdGMybDZaVG9nTVRad2VEc2dabTl1ZEMxemRIbHNaVG9nYm05eWJXRnNPeUJtYjI1MExYZGxhV2RvZERvZ05EQXdPeUJzWlhSMFpYSXRjM0JoWTJsdVp6b2dibTl5YldGc095QjBaWGgwTFdsdVpHVnVkRG9nTUhCNE95QjBaWGgwTFhSeVlXNXpabTl5YlRvZ2JtOXVaVHNnZDI5eVpDMXpjR0ZqYVc1bk9pQXdjSGc3SUhkb2FYUmxMWE53WVdObE9pQnViM0p0WVd3N0lHSmhZMnRuY205MWJtUXRZMjlzYjNJNklDTm1abVptWm1ZN0lHWnNiMkYwT2lCdWIyNWxPeUJrYVhOd2JHRjVPaUJwYm14cGJtVWdJV2x0Y0c5eWRHRnVkRHNpUHRHRTBMalF1dEdCMExEUmd0QyswWUFtSTNoa093b2cwTERSZ05DODBMRFJndEdEMFlEUml5RFF2OUMrMFlMUXZ0QzcwTDdSaDlDOTBMRFJqeURRdnRDLzBMN1JnTkN3SURZd01ERFJpTkdDSm14ME95OXpjR0Z1UGlac2REc3ZaR2wyUGlZamVHUTdDaVpzZERzdlpHbDJQaVlqZUdRN0NpWnNkRHR6Y0dGdUlITjBlV3hsUFNKamIyeHZjam9nSXpBd01EQXdNRHNnWm05dWRDMW1ZVzFwYkhrNklHRnlhV0ZzTENCb1pXeDJaWFJwWTJFc0lITmhibk10YzJWeWFXWTdJR1p2Ym5RdGMybDZaVG9nTVRad2VEc2dabTl1ZEMxemRIbHNaVG9nYm05eWJXRnNPeUJtYjI1MExYWmhjbWxoYm5RdGJHbG5ZWFIxY21Wek9pQnViM0p0WVd3N0lHWnZiblF0ZG1GeWFXRnVkQzFqWVhCek9pQnViM0p0WVd3N0lHWnZiblF0ZDJWcFoyaDBPaUEwTURBN0lHeGxkSFJsY2kxemNHRmphVzVuT2lCdWIzSnRZV3c3SUc5eWNHaGhibk02SURJN0lIUmxlSFF0WVd4cFoyNDZJSE4wWVhKME95QjBaWGgwTFdsdVpHVnVkRG9nTUhCNE95QjBaWGgwTFhSeVlXNXpabTl5YlRvZ2JtOXVaVHNnZDJsa2IzZHpPaUF5T3lCM2IzSmtMWE53WVdOcGJtYzZJREJ3ZURzZ0xYZGxZbXRwZEMxMFpYaDBMWE4wY205clpTMTNhV1IwYURvZ01IQjRPeUIzYUdsMFpTMXpjR0ZqWlRvZ2JtOXliV0ZzT3lCaVlXTnJaM0p2ZFc1a0xXTnZiRzl5T2lBalptUm1aR1prT3lCMFpYaDBMV1JsWTI5eVlYUnBiMjR0ZEdocFkydHVaWE56T2lCcGJtbDBhV0ZzT3lCMFpYaDBMV1JsWTI5eVlYUnBiMjR0YzNSNWJHVTZJR2x1YVhScFlXdzdJSFJsZUhRdFpHVmpiM0poZEdsdmJpMWpiMnh2Y2pvZ2FXNXBkR2xoYkRzZ1pHbHpjR3hoZVRvZ2FXNXNhVzVsSUNGcGJYQnZjblJoYm5RN0lHWnNiMkYwT2lCdWIyNWxPeUlnWkdGMFlTMXRZMlV0YzNSNWJHVTlJbU52Ykc5eU9pQWpNREF3TURBd095Qm1iMjUwTFdaaGJXbHNlVG9nWVhKcFlXd3NJR2hsYkhabGRHbGpZU3dnYzJGdWN5MXpaWEpwWmpzZ1ptOXVkQzF6YVhwbE9pQXhObkI0T3lCbWIyNTBMWE4wZVd4bE9pQnViM0p0WVd3N0lHWnZiblF0ZG1GeWFXRnVkQzFzYVdkaGRIVnlaWE02SUc1dmNtMWhiRHNnWm05dWRDMTJZWEpwWVc1MExXTmhjSE02SUc1dmNtMWhiRHNnWm05dWRDMTNaV2xuYUhRNklEUXdNRHNnYkdWMGRHVnlMWE53WVdOcGJtYzZJRzV2Y20xaGJEc2diM0p3YUdGdWN6b2dNanNnZEdWNGRDMWhiR2xuYmpvZ2MzUmhjblE3SUhSbGVIUXRhVzVrWlc1ME9pQXdjSGc3SUhSbGVIUXRkSEpoYm5ObWIzSnRPaUJ1YjI1bE95QjNhV1J2ZDNNNklESTdJSGR2Y21RdGMzQmhZMmx1WnpvZ01IQjRPeUF0ZDJWaWEybDBMWFJsZUhRdGMzUnliMnRsTFhkcFpIUm9PaUF3Y0hnN0lIZG9hWFJsTFhOd1lXTmxPaUJ1YjNKdFlXdzdJR0poWTJ0bmNtOTFibVF0WTI5c2IzSTZJQ05tWkdaa1ptUTdJSFJsZUhRdFpHVmpiM0poZEdsdmJpMTBhR2xqYTI1bGMzTTZJR2x1YVhScFlXdzdJSFJsZUhRdFpHVmpiM0poZEdsdmJpMXpkSGxzWlRvZ2FXNXBkR2xoYkRzZ2RHVjRkQzFrWldOdmNtRjBhVzl1TFdOdmJHOXlPaUJwYm1sMGFXRnNPeUJrYVhOd2JHRjVPaUJwYm14cGJtVWdJV2x0Y0c5eWRHRnVkRHNnWm14dllYUTZJRzV2Ym1VN0lqN1F2OUdBMEw3UXN0QyswTHZRdnRDNjBMQW1JM2hrT3dvZzBMTFJqOUMzMExEUXU5R00wTDNRc05HUElERXNNdEM4MEx3Z0xTQXlNemZRdXRDekpteDBPeTl6Y0dGdVBpWnNkRHNoTFMxRmJtUkdjbUZuYldWdWRDMHRQaVlqZUdRN0NpWnNkRHRrYVhZZ2MzUjViR1U5SW1Oc1pXRnlPaUJpYjNSb095SWdaR0YwWVMxdFkyVXRjM1I1YkdVOUltTnNaV0Z5T2lCaWIzUm9PeUkrSm14ME8ySnlJR1JoZEdFdGJXTmxMV0p2WjNWelBTSXhJajRtSTNoa093b21iSFE3TDJScGRqNG1JM2hrT3dvbWJIUTdMMlJwZGo0bUkzaGtPd29tYkhRN1pHbDJJR1JoZEdFdGJXRnlhMlZ5UFNKZlgxTkpSMTlRVDFOVVgxOGlQaTB0SUNac2REdGljajRtSTNoa093b21iSFE3TDJScGRqNG1JM2hrT3dvbWJIUTdaR2wyUHRDaElOR0QwTExRc05DMjBMWFF2ZEM0MExYUXZDd2cwTHZRdnRDejBMalJnZEdDSm14ME8ySnlQaVlqZUdRN0N0QzYwTDdRdk5DLzBMRFF2ZEM0MExnZ0ptRnRjRHR4ZFc5ME85Q2EwWURRdnRDeTBMWFF1OUdNMEwzUmk5QzVJTkNtMExYUXZkR0MwWUFtWVcxd08zRjFiM1E3Sm14ME8ySnlQaVlqZUdRN0N0Q2EwTERRdWRDMDBMRFF1OUM0MEwzUXNDRFFudEM2MFlIUXNOQzkwTEFnMEozUXVOQzYwTDdRdTlDdzBMWFFzdEM5MExBbWJIUTdZbkkrSmlONFpEc0swTE11SU5DYTBZRFFzTkdCMEwzUXZ0R1AwWURSZ2RDNkpteDBPMkp5UGlZamVHUTdDdEdDMExYUXV5NGdPRGs0TXpJMk5qUXpNekFtYkhRN1luSStKaU40WkRzSzBMclJnTkMrMExMUXRkQzcwWXpRdmRHTDBMblJodEMxMEwzUmd0R0FMdEdBMFlRdkpteDBPeTlrYVhZK0ppTjRaRHNLSm14ME95OWthWFkrSmlONFpEc0tKbXgwT3k5a2FYWStKaU40WkRzS0pteDBPeTlpYjJSNVBpWWplR1E3Q2lac2REc3ZhSFJ0YkQ0bUkzaGtPd284TDJacGJHVkRiMjUwWlc1MFBqd3Zhbk52Yms5aWFtVmpkRDQ4TDNOdllYQmxiblk2UW05a2VUNDhMM052WVhCbGJuWTZSVzUyWld4dmNHVSs="]
    # for h in hashs:
    #     text = text_from_hash(h)
    #     print(ygpt.get_pos(text, save=True, bag=False))
    #     break
    # print(y_gpt().get_pos(text))
# Synchronous completion example
# completion = yandex_gpt.get_sync_completion(messages=msgs, temperature=0)
# print(completion)
# msgs += [{"role": "assistant", "text": completion}]
# content3 = text_from_hash('UEQ5NGJXd2dkbVZ5YzJsdmJqMG5NUzR3SnlCbGJtTnZaR2x1WnowbmRYUm1MVGduUHo0OGMyOWhjR1Z1ZGpwRmJuWmxiRzl3WlNCNGJXeHVjenB6YjJGd1pXNTJQU0pvZEhSd09pOHZjMk5vWlcxaGN5NTRiV3h6YjJGd0xtOXlaeTl6YjJGd0wyVnVkbVZzYjNCbEx5SStQSE52WVhCbGJuWTZRbTlrZVQ0OGFuTnZiazlpYW1WamRENDhiMkpxWldOMFRtRnRaVDV0YzJkZlpXVmxZMkkwTTJKaU1qZ3hNakl5TURneE0yUXpPV001TXpZek5HTmpNVGc4TDI5aWFtVmpkRTVoYldVK1BHSjFZMnRsZEU1aGJXVStZM0p0TFdWdFlXbHNQQzlpZFdOclpYUk9ZVzFsUGp4bWFXeGxRMjl1ZEdWdWRENG1iSFE3YUhSdGJENG1JM2hrT3dvbWJIUTdhR1ZoWkQ0bUkzaGtPd29tYkhRN2JXVjBZU0JvZEhSd0xXVnhkV2wyUFNKRGIyNTBaVzUwTFZSNWNHVWlJR052Ym5SbGJuUTlJblJsZUhRdmFIUnRiRHNnWTJoaGNuTmxkRDExZEdZdE9DSStKaU40WkRzS0pteDBPeTlvWldGa1BpWWplR1E3Q2lac2REdGliMlI1UGlZamVHUTdDaVpzZER0d0lITjBlV3hsUFNKbWIyNTBMWE5wZW1VNk1UQndkRHNnWTI5c2IzSTZJekF3TURCbVppSStKbXgwTzJrKzBKTFFuZENWMEtqUW5kQ3YwSzhnMEovUW50Q24wS0xRa0RvZzBKWFJnZEM3MExnZzBMN1JndEMvMFlEUXNOQ3kwTGpSZ3RDMTBMdlJqQ0RRdmRDMTBMalF0OUN5MExYUmdkR0MwTFhRdlN3ZzBMM1F0U0RRdjlDMTBZRFF0ZEdGMEw3UXROQzQwWUxRdFNEUXY5QytJTkdCMFlIUmk5QzcwTHJRc05DOExDRFF2ZEMxSU5DKzBZTFF2OUdBMExEUXN0QzcwWS9RdWRHQzBMVWcwTC9Rc05HQTBMN1F1OUM0TENEUmdTRFF2dEdCMFlMUXZ0R0EwTDdRdHRDOTBMN1JnZEdDMFl6UmppRFF2dEdDMExyUmdOR0wwTExRc05DNTBZTFF0U0RRc3RDNzBMN1F0dEMxMEwzUXVOR1BMaVpzZERzdmFUNG1iSFE3TDNBK0ppTjRaRHNLSm14ME8ySnlQaVlqZUdRN0NpWnNkRHRpY2o0bUkzaGtPd29tYkhRN1luSStKaU40WkRzS0pteDBPMkp5UGlZamVHUTdDaVpzZER0a2FYWStKaU40WkRzS0pteDBPMlJwZGlCaGJHbG5iajBpYkdWbWRDSStKaU40WkRzS0pteDBPMlJwZGlCemRIbHNaVDBpYkdsdVpTMW9aV2xuYUhRNklESTBjSGc3SWo3UWw5QzAwWURRc05DeTBZSFJndEN5MFlQUXVkR0MwTFV1SUNac2REdGljajRtSTNoa093clFuOUdBMEw3UmlOR0RJTkN5MFl2UmdkR0MwTERRc3RDNDBZTFJqQ0RSZ2RHSDBMWFJnaURRdmRDd0lOQzMwTERSajlDeTBMclJneUFtYkhRN1lTQnpkSGxzWlQwaVkyOXNiM0k2SUNNek16TTdJSFJsZUhRdFpHVmpiM0poZEdsdmJqb2dibTl1WlRzaVBsdGplVzUwWld0aElHbGtJREV5TURNbWJIUTdMMkUrWFNEaWdKTW1JM2hrT3dvbWJIUTdZU0J6ZEhsc1pUMGlZMjlzYjNJNklDTTBZVGt3WlRJN0lIUmxlSFF0WkdWamIzSmhkR2x2YmpvZ2RXNWtaWEpzYVc1bE95SWdhSEpsWmowaWFIUjBjSE02THk5d2NtOWtZWFpoZVM1elpXd3RZbVV1Y25VdlkyOXlaUzl2Y21SbGNuTXZNamt4TkRJNE1EWXZaRzkzYm14dllXUXZiR2x0YVhSbFpEOXBaRDB5T1RFME1qZ3dOaVpoYlhBN1lXMXdPM0psY1hWbGMzUkpaRDAxTXpVMU16YzVNRE1tWVcxd08yRnRjRHRqYjJSbFBUZzNORFkxWXpFNE9XRmpORGhpTW1aa1pUTXpPV1EwWmpZME9HVmlNakV6SWo0bUkzaGtPd3JSZ2RDNjBMRFJoOUN3MFlMUmpDRFF0OUN3MFkvUXN0QzYwWU1tYkhRN0wyRStMQ0FtYkhRN1lTQnpkSGxzWlQwaVkyOXNiM0k2SUNNek16TTdJSFJsZUhRdFpHVmpiM0poZEdsdmJqb2dibTl1WlRzaVBpWnNkRHRpY2o0bUkzaGtPd3JRdjlDNzBMRFJndEMxMEx2UmpOR0owTGpRdWpvZzBKN1FudENlSU5DaDBKb2dKbUZ0Y0R0eGRXOTBPOUNSTVNaaGJYQTdjWFZ2ZERzZzRvQ1RJQ1pzZERzdllUNG1iSFE3WVNCemRIbHNaVDBpWTI5c2IzSTZJQ00wWVRrd1pUSTdJSFJsZUhRdFpHVmpiM0poZEdsdmJqb2dkVzVrWlhKc2FXNWxPeUlnYUhKbFpqMGlhSFIwY0hNNkx5OXdjbTlrWVhaaGVTNXpaV3d0WW1VdWNuVXZZMjl5WlM5emRYQndiR2xsY2k5amIyMXdZVzU1THpFd01ETXhNakV2Y21WeGRXbHphWFJsY3k5c2FXMXBkR1ZrUDJsa1BUSTVNVFF5T0RBMkptRnRjRHRoYlhBN2NtVnhkV1Z6ZEVsa1BUVXpOVFV6Tnprd015WmhiWEE3WVcxd08yTnZaR1U5T0RjME5qVmpNVGc1WVdNME9HSXlabVJsTXpNNVpEUm1OalE0WldJeU1UTWlQdEdCMExyUXNOR0gwTERSZ3RHTUpteDBPeTloUGk0bUkzaGtPd29tYkhRN1luSStKaU40WkRzSzBKVFF1OUdQSU5DKzBZTFF2OUdBMExEUXN0QzYwTGdnMFlIUmg5QzEwWUxRc0NEUXZkQ3cwTGJRdk5DNDBZTFF0U0FtYkhRN1lTQnpkSGxzWlQwaVkyOXNiM0k2SUNObVpqQXdNVE03SUhSbGVIUXRaR1ZqYjNKaGRHbHZiam9nZFc1a1pYSnNhVzVsT3lJZ2FISmxaajBpYUhSMGNITTZMeTl3Y205a1lYWmhlUzV6Wld3dFltVXVjblV2WTI5eVpTOXpkWEJ3YkdsbGNpOXlaV2RwYzNSeWVTOXNhVzFwZEdWa1AybGtQVEk1TVRReU9EQTJKbUZ0Y0R0aGJYQTdjbVZ4ZFdWemRFbGtQVFV6TlRVek56a3dNeVpoYlhBN1lXMXdPMk52WkdVOU9EYzBOalZqTVRnNVlXTTBPR0l5Wm1SbE16TTVaRFJtTmpRNFpXSXlNVE1tWVcxd08yRnRjRHRoWTNScGIyNDljMlZ1WkNJK0ppTjRaRHNLMEpmUWxOQ1YwS0hRckNac2REc3ZZVDR1SUNac2REc3ZaR2wyUGlZamVHUTdDaVpzZER0aWNqNG1JM2hrT3dvbWJIUTdaR2wyUGpFdUlOQ1EwWURRdk5DdzBZTFJnOUdBMExBZzBKQXlOREFnTmlBdElEQXNOamdnMFlJZ0tOQ2gwTFhRdXRHRzBMalJqeUF4TGpFZzBLSFJndEMxMEwzUml5RFF2OUMrMExUUXN0Q3cwTHZRc0NBeE5TNHdOUzR5TkNEUmc5R0MwWURRdnRDOEtTQW9TVVFnMEwvUXZ0QzMwTGpSaHRDNDBMZ2dOVFEwTkNrbUkzaGtPd29tYkhRN0wyUnBkajRtSTNoa093b21iSFE3WkdsMlBqSXVJTkNRMFlEUXZOQ3cwWUxSZzlHQTBMQWcwSkExTUREUW9TQTRJQzBnTVN3MUlOR0NJQ2pRb2RDMTBMclJodEM0MFk4Z01TNHhJTkNoMFlMUXRkQzkwWXNnMEwvUXZ0QzAwTExRc05DNzBMQWdNVFV1TURVdU1qUWcwWVBSZ3RHQTBMN1F2Q2tnS0VsRUlOQy8wTDdRdDlDNDBZYlF1TkM0SURVME5EVXBKaU40WkRzS0pteDBPeTlrYVhZK0ppTjRaRHNLSm14ME8yUnBkajR6TGlEUWtOR0EwTHpRc05HQzBZUFJnTkN3SU5DUU5UQXcwS0VnTVRJZ0xTQXhOaXcxSU5HQ0lDalFvZEMxMExyUmh0QzQwWThnTVM0eElOQ2gwWUxRdGRDOTBZc2cwTC9RdnRDMDBMTFFzTkM3MExBZ05pdzEwWUlzSU5DaDBMWFF1dEdHMExqUmp5QXhMRElnMEtUUW56RWdNVERSZ2lEUXY5QyswWUhSZ3RDdzBMTFF1dEN3SURFMUxqQTFMakkwSU5HRDBZTFJnTkMrMEx3cElDaEpSQ0RRdjlDKzBMZlF1TkdHMExqUXVDQTFORFEyS1NZamVHUTdDaVpzZERzdlpHbDJQaVlqZUdRN0NpWnNkRHRrYVhZK05DNGcwSkRSZ05DODBMRFJndEdEMFlEUXNDRFFrRFV3TU5DaElERTJJQzBnTVN3eE5TRFJnaUFvMEtIUXRkQzYwWWJRdU5HUElERXNNaURRcE5DZk1TRFF2OUMrMFlIUmd0Q3cwTExRdXRDd0lERTFMakExTGpJMEtTQW9TVVFnMEwvUXZ0QzMwTGpSaHRDNDBMZ2dOVFEwTnlrbUkzaGtPd29tYkhRN0wyUnBkajRtSTNoa093b21iSFE3WW5JK0ppTjRaRHNLSm14ME8yUnBkajdRbE5DKzBML1F2dEM3MEwzUXVOR0MwTFhRdTlHTTBMM1FzTkdQSU5DNDBMM1JoTkMrMFlEUXZOQ3cwWWJRdU5HUE9pQW1iSFE3TDJScGRqNG1JM2hrT3dvbWJIUTdaR2wySUhOMGVXeGxQU0owWlhoMExXRnNhV2R1T2lCc1pXWjBPeUkrTVM0ZzBKL1F2dEdCMFlMUXNOQ3kwTGpSZ3RHTUlOQzZJREUxTGpBMUxqSXdNalFnSm14ME95OWthWFkrSmlONFpEc0tKbXgwTzJScGRpQnpkSGxzWlQwaWRHVjRkQzFoYkdsbmJqb2diR1ZtZERzaVBqSXVJTkNpMFlEUXRkQ3gwWVBRdGRHQzBZSFJqeURRdE5DKzBZSFJndEN3MExMUXV0Q3dJTkMvMEw0ZzBMRFF0TkdBMExYUmdkR0RPaURRa05DMDBZRFF0ZEdCSU5DLzBZRFF2dEMxMExyUmd0Q3dJQzBnMEtEUXZ0R0IwWUhRdU5HUElDd2cwS0hRc3RDMTBZRFF0TkM3MEw3UXN0R0IwTHJRc05HUElOQyswTEhRdTlDdzBZSFJndEdNSUN3ZzBKWFF1dEN3MFlMUXRkR0EwTGpRdmRDeDBZUFJnTkN6SUN3ZzBLTFF0ZEM5MExqUmdkR0MwTERSanlBc0lEalFrU1lqZUdRN0NpWnNkRHN2WkdsMlBpWWplR1E3Q2lac2REdGthWFlnYzNSNWJHVTlJblJsZUhRdFlXeHBaMjQ2SUd4bFpuUTdJajR6TGlBbWJIUTdjM0JoYmlCemRIbHNaVDBpWTI5c2IzSTZjbVZrT3lJKzBLblFzTkMvMEw3UXNpRFFrTkdBMFlMUXRkQzhJQ1pzZERzdmMzQmhiajRtYkhRN0wyUnBkajRtSTNoa093b21iSFE3WkdsMklITjBlV3hsUFNKMFpYaDBMV0ZzYVdkdU9pQnNaV1owT3lJK05DNGcwS0xSZ05DMTBMSFJnOUMxMFlMUmdkR1BJTkMrMFlMUmdkR0EwTDdSaDlDNjBMQWcwTC9RdTlDdzBZTFF0ZEMyMExBc0lETXcwTFRRdmRDMTBMa2dKbXgwT3k5a2FYWStKaU40WkRzS0pteDBPMkp5UGlZamVHUTdDaVpzZER0a2FYWSswSlhSZ2RDNzBMZ2cwTDNRdGRDKzBMSFJoZEMrMExUUXVOQzgwTDRnMExmUXNOQzAwTERSZ3RHTUlOQ3kwTDdRdjlHQTBMN1JnU0RRdjlDK0lOQzMwTERSajlDeTBMclF0U3dnMEwzUXNOQzIwTHpRdU5HQzBMVWdKbXgwTzJFZ2MzUjViR1U5SW1OdmJHOXlPaUFqTkdFNU1HVXlPeUIwWlhoMExXUmxZMjl5WVhScGIyNDZJSFZ1WkdWeWJHbHVaVHNpSUdoeVpXWTlJbWgwZEhCek9pOHZjSEp2WkdGMllYa3VjMlZzTFdKbExuSjFMMk52Y21VdmMzVndjR3hwWlhJdmNtVm5hWE4wY25rdmJHbHRhWFJsWkQ5cFpEMHlPVEUwTWpnd05pWmhiWEE3WVcxd08zSmxjWFZsYzNSSlpEMDFNelUxTXpjNU1ETW1ZVzF3TzJGdGNEdGpiMlJsUFRnM05EWTFZekU0T1dGak5EaGlNbVprWlRNek9XUTBaalkwT0dWaU1qRXpKbUZ0Y0R0aGJYQTdZV04wYVc5dVBXTm9ZWFFpUGlZamVHUTdDdENYMEpUUWxkQ2gwS3dtYkhRN0wyRStMaUFtYkhRN0wyUnBkajRtSTNoa093b21iSFE3WkdsMlBpWnNkRHRpY2o0bUkzaGtPd3JRb1NEUmc5Q3kwTERRdHRDMTBMM1F1TkMxMEx3c0lDWnNkRHRpY2o0bUkzaGtPd3JRbnRDZTBKNGcwS0hRbWlBbVlXMXdPM0YxYjNRNzBKRXhKbUZ0Y0R0eGRXOTBPeUFtYkhRN1luSStKaU40WkRzSzBKSFFzTkdIMExqUXZkQzQwTDBnMEpqUXM5QyswWURSakNEUW5OQzQwWVhRc05DNTBMdlF2dEN5MExqUmh5QW1iSFE3WW5JK0ppTjRaRHNLWW1GamFHbHVhVzVwYlVCemEycGlheTVqYjIwZ0pteDBPMkp5UGlZamVHUTdDaVpoYlhBN0l6UXpPemNnS0RreE1pa2dOamcyTFRRekxUUXpJQ1pzZER0aWNqNG1JM2hrT3dvbWJIUTdMMlJwZGo0bUkzaGtPd29tYkhRN0wyUnBkajRtSTNoa093b21iSFE3TDJScGRqNG1JM2hrT3dvbWJIUTdMMkp2WkhrK0ppTjRaRHNLSm14ME95OW9kRzFzUGlZamVHUTdDand2Wm1sc1pVTnZiblJsYm5RK1BDOXFjMjl1VDJKcVpXTjBQand2YzI5aGNHVnVkanBDYjJSNVBqd3ZjMjloY0dWdWRqcEZiblpsYkc5d1pUND0=')
# print('-'*6)
# msgs += [{"role": "user", "text": content3}]
# start = time.time()
# completion2 = yandex_gpt.get_sync_completion(messages=msgs, temperature=0)
# print('Время запроса к Алисе:', time.time() - start)
# print(completion2)