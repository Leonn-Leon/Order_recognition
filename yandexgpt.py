# from yandex_gpt import YandexGPTConfigManagerForAPIKey, YandexGPT, YandexGPTThread
import os
from hash2text import text_from_hash
import json
import time
import pandas as pd
import requests
from datetime import datetime
from config import Authorization_AIM, xfolderid, gpt_version_id, gpt_url


class custom_yandex_gpt():
    def __init__(self):
        self.headers = {"Authorization": "Bearer " + Authorization_AIM,
                   "x-folder-id": xfolderid }
        df = pd.read_csv("data/msgs_ei_marked.csv", index_col=0)
        self.msgs = df.to_numpy()
        self.msgs = [{"role":i[0], "text":i[1].replace('\xa0', ' ').replace('"', "''")} for i in self.msgs]
        self.req = {
            "modelUri": "ds://"+gpt_version_id,
            "completionOptions": {
                "stream": False,
                "temperature": 0.3,
                "maxTokens": "3000"
            },
            "messages": [
                {
                    "role": "system",
                    "text": self.msgs[0]['text']
                }
            ]
        }

    def write_logs(self, text, event=1):
        event = 'EVENT' if event == 1 else 'ERROR'
        date_time = datetime.now().astimezone()
        file_name = './logs/' + str(date_time.date()) + '.txt'
        log = open(file_name, 'a')
        log.write(str(date_time) + ' | ' + event + ' | ' + text + '\n')
        log.close()


    def get_pos(self, text:str, save=False, bag=False):
        while '\n\n' in text:
            text = text.replace('\n\n', '\n')
        self.msgs += [{"role": "user", "text": text.replace('\xa0', ' ').replace('"', "''")}]
        if bag:
            print(self.msgs[-1]['text'])
            print('-' * 15)
        prompt = self.req
        prompt['messages'] += [self.msgs[-1]]
        start = time.time()
        res = requests.post(gpt_url,
                            headers=self.headers, json=prompt)
        self.write_logs('Время на запрос, ' + str(time.time() - start))
        self.write_logs(str(res.text))
        print('Время на запрос, ', time.time() - start)
        try:
            answer = json.loads(res.text)['result']['alternatives'][0]['message']['text']
        except:
            self.write_logs(res.text, event=0)
            print(res.text)
        if save:
            self.msgs += [{"role": "assistant", "text": answer}]
            pd.DataFrame(self.msgs).to_csv("data/msgs.csv")

        return self.split_answer(answer)

    def split_answer(self,answer):
        answer = answer.split('\n')
        answer_ei = []
        for pos in answer:
            s = pos.split('|')
            if len(s) < 3:
                continue
            answer_ei += [(s[-3], s[-2], s[-1])]
        return answer_ei

if __name__ == "__main__":
    ygpt = custom_yandex_gpt()
    hashs = []
    for log in os.listdir('logs'):
        with open('logs/'+log, 'r') as file:
            for line in file:
                if 'Body - ' not in line:
                    continue
                h = json.loads(line[50:].replace("'", '"'))['email']
                if h not in hashs and h != '':
                    hashs += [h]
    for h in hashs[-1:]:
        text = text_from_hash(h)
        print(ygpt.get_pos(text, save=True, bag=True))
        break
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