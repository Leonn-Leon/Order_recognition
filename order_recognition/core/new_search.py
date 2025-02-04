import csv
import time
import os
import pickle
import numpy as np
import faiss
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from order_recognition.core.hash2text import text_from_hash
from langchain.docstore.document import Document
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from yandex_cloud_ml_sdk import YCloudML
from yandexgpt import custom_yandex_gpt
from order_recognition.confs import config

class MaterialSelector:
    def __init__(self, csv_path: str, folder_id: str,
                 embedding_cache_file: str = "order_recognition/data/embeddings_cache.pkl",
                 chunk_size: int = 1, chunk_overlap: int = 0,
                 model_name: str = "cointegrated/rubert-tiny2"):
        """
        Инициализация:
          - Загружает материалы из CSV‑файла с объединением нескольких строк в один документ.
          - Создает FAISS‑индекс с использованием эмбеддингов модели cointegrated/rubert-tiny2.
          - Сохраняет/подгружает эмбеддинги для документов.
          - Инициализирует YandexGPT для подбора лучших материалов.
          - Инициализирует объект для извлечения позиций из чистого письма.
        
        Параметры:
          csv_path: путь к CSV‑файлу с материалами.
          folder_id: идентификатор каталога для YandexCloud.
          embedding_cache_file: путь к файлу кэша эмбеддингов.
          chunk_size: число строк, объединяемых в один документ.
          chunk_overlap: количество строк перекрытия между соседними документами.
          model_name: имя модели эмбеддингов (по умолчанию "cointegrated/rubert-tiny2").
        """
        self.csv_path = csv_path
        self.folder_id = folder_id
        self.embedding_cache_file = embedding_cache_file
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # Объект для извлечения позиций из письма
        self.position_extractor = custom_yandex_gpt()
        self.position_extractor.update_token()
        self.iam_token = self.position_extractor.headers["Authorization"][7:]

        # Инструкция для системного промпта
        with open("order_recognition/confs/second_gpt_instruct.txt", encoding="utf-8") as f:
            self.system_instruct = f.read().strip()

        # Загружаем материалы
        self.materials = self.load_materials(self.csv_path)

        # Инициализируем эмбеддинги
        self.embeddings = HuggingFaceEmbeddings(model_name=model_name)

        # Загружаем кэш эмбеддингов (если файл существует)
        if os.path.exists(self.embedding_cache_file):
            print("Загружаем кэш эмбеддингов...")
            with open(self.embedding_cache_file, "rb") as f:
                cache = pickle.load(f)
        else:
            print("Кэш эмбеддингов не найден, вычисляем эмбеддинги...")
            cache = {}

        # Вычисляем эмбеддинги для каждого документа (с использованием кэша)
        computed_embeddings = []
        for doc in self.materials:
            key = doc.page_content
            if key in cache:
                emb = cache[key]
            else:
                emb = self.embeddings.embed_query(key)
                cache[key] = emb
            computed_embeddings.append(emb)

        # Сохраняем обновленный кэш эмбеддингов
        with open(self.embedding_cache_file, "wb") as f:
            pickle.dump(cache, f)

        # Создаём FAISS-индекс
        if computed_embeddings:
            dimension = len(computed_embeddings[0])
            index = faiss.IndexFlatL2(dimension)
            emb_matrix = np.array(computed_embeddings).astype("float32")
            index.add(emb_matrix)
        else:
            raise ValueError("Нет эмбеддингов для создания FAISS‑индекса.")

        # Формируем docstore: ключ – строковый индекс, значение – документ
        docstore = InMemoryDocstore({str(i): doc for i, doc in enumerate(self.materials)})

        # Создаем index_to_docstore_id, сопоставляющий индексы FAISS с идентификаторами документов
        index_to_docstore_id = {i: str(i) for i in range(len(self.materials))}
        self.vectorstore = FAISS(
            embedding_function=self.embeddings,
            index=index,
            docstore=docstore,
            index_to_docstore_id=index_to_docstore_id
        )

        # Модель для уточняющего подбора
        self.sdk = YCloudML(folder_id=self.folder_id, auth=self.iam_token)
        self.model = self.sdk.models.completions("yandexgpt").configure(temperature=0.1)

    def load_materials(self, csv_path: str):
        """
        Загружает материалы из CSV‑файла и группирует строки в документы.
        Каждый документ формируется из chunk_size строк с перекрытием chunk_overlap.
        
        При работе с файлом, содержащим более 100 000 записей, группировка строк позволяет
        сократить количество документов для индексирования, что может ускорить поиск и снизить
        нагрузку на память. Однако если требуется высокая детализация поиска по отдельным материалам,
        имеет смысл оставлять одну строку как отдельный документ.
        
        Возвращает список объектов Document.
        """
        with open(csv_path, encoding="utf-8") as f:
            reader = list(csv.DictReader(f))

        documents = []
        step = self.chunk_size - self.chunk_overlap
        for i in range(0, len(reader), step):
            chunk = reader[i: i + self.chunk_size]
            if not chunk:
                break
            lines = []
            material_ids = []
            for row in chunk:
                # Формируем строку: номер материала и полное наименование
                line = f"{row['Полное наименование материала']}"
                lines.append(line)
                material_ids.append(row['Материал'])
            content = "\n".join(lines)
            documents.append(Document(page_content=content, metadata={"Материалы": material_ids}))
        return documents

    def _process_single_position(self, pos_text: str):
        """
        Вспомогательный метод, который обрабатывает одну позицию:
          1. Ищет похожие документы (k=20).
          2. Формирует промпт для модели.
          3. Запрашивает модель и возвращает (pos_text, результат).
        """
        # Шаг 1. Ищем похожие документы
        similar_docs = self.vectorstore.similarity_search(pos_text, k=20)
        print(f"СТРОКИ ДЛЯ {pos_text}:", similar_docs)
        # Собираем номера материалов
        materials_list = [
            "\n".join([f"{m_id}" for m_id in doc.metadata["Материалы"]])
            for doc in similar_docs
        ]

        # Шаг 2. Формируем промпты
        system_message = {"role": "system", "text": self.system_instruct}
        user_message = {
            "role": "user",
            "text": f"Найди для этого текста: {pos_text}\n 5 максимально похожих строк в этих документах:\n" + "\n".join(materials_list)
        }

        # Шаг 3. Запрашиваем модель
        response = self.model.run([system_message, user_message])
        result_text = response[0].text.strip()
        return pos_text, result_text

    def process_email(self, email_content: str):
        """
        Обрабатывает письмо от клиента:
          1. Извлекает позиции.
          2. Запускает каждую позицию на обработку в отдельном потоке (ThreadPool).
          3. Собирает результаты в общий словарь.
        """
        print("Начали искать позиции в письме...")
        positions = self.position_extractor.big_mail(email_content)  # [(pos_text, ...), ...]

        results = {}
        # Запускаем пул потоков
        with ThreadPoolExecutor(max_workers=5) as executor:
            # Создаём задания для каждого pos_text
            future_to_position = {
                executor.submit(self._process_single_position, pos_tuple[0]): pos_tuple[0]
                for pos_tuple in positions
            }

            # Ожидаем завершения
            for future in as_completed(future_to_position):
                pos_text = future_to_position[future]
                try:
                    # Получаем результат
                    key, value = future.result()
                    results[key] = value
                except Exception as e:
                    # В случае ошибки
                    results[pos_text] = f"Ошибка при обработке: {e}"

        return results

if __name__ == '__main__':
    csv_path = "order_recognition/data/mats.csv"
    folder_id = config.xfolderid  # замените на ваш folder_id
    selector = MaterialSelector(csv_path, folder_id)

    email_content = (
        "Здравствуйте, уголок 35x4 ст3пс - 1.3 тн, арматура арматуру 12 480м по 6м., "
        "швеллер 8п-5 штук по 12 метров. Напишите о возможности доставки, спасибо."
    )

    # print("Начало обработки...")
    # start_time = time.time()
    # results = selector.process_email(email_content)
    # end_time = time.time()
    # elapsed_time = end_time - start_time
    # print(f"Время обработки письма: {elapsed_time:.2f} секунд")

    # print("Итоговые результаты подбора материалов:")
    # for pos, res in results.items():
    #     print(f"Позиция: {pos} -> Материалы: {res}")

    hash = "UEQ5NGJXd2dkbVZ5YzJsdmJqMG5NUzR3SnlCbGJtTnZaR2x1WnowbmRYUm1MVGduUHo0OGMyOWhjR1Z1ZGpwRmJuWmxiRzl3WlNCNGJXeHVjenB6YjJGd1pXNTJQU0pvZEhSd09pOHZjMk5vWlcxaGN5NTRiV3h6YjJGd0xtOXlaeTl6YjJGd0wyVnVkbVZzYjNCbEx5SStQSE52WVhCbGJuWTZRbTlrZVQ0OGFuTnZiazlpYW1WamRENDhiMkpxWldOMFRtRnRaVDV0YzJkZk16SmhaRFZtT1dGaE5UVmpNekkyWVRNeVpXTmtNalpsT0RZNE1XVm1NR004TDI5aWFtVmpkRTVoYldVK1BHSjFZMnRsZEU1aGJXVStZM0p0TFdWdFlXbHNQQzlpZFdOclpYUk9ZVzFsUGp4bWFXeGxRMjl1ZEdWdWRENG1iSFE3YUhSdGJENG1JM2hrT3dvbWJIUTdhR1ZoWkQ0bUkzaGtPd29tYkhRN2JXVjBZU0JvZEhSd0xXVnhkV2wyUFNKRGIyNTBaVzUwTFZSNWNHVWlJR052Ym5SbGJuUTlJblJsZUhRdmFIUnRiRHNnWTJoaGNuTmxkRDExZEdZdE9DSStKaU40WkRzS0pteDBPeTlvWldGa1BpWWplR1E3Q2lac2REdGliMlI1UGlZamVHUTdDaVpzZER0d0lITjBlV3hsUFNKbWIyNTBMWE5wZW1VNk1UQndkRHNnWTI5c2IzSTZJekF3TURCbVppSStKbXgwTzJrKzBKTFFuZENWMEtqUW5kQ3YwSzhnMEovUW50Q24wS0xRa0RvZzBKWFJnZEM3MExnZzBMN1JndEMvMFlEUXNOQ3kwTGpSZ3RDMTBMdlJqQ0RRdmRDMTBMalF0OUN5MExYUmdkR0MwTFhRdlN3ZzBMM1F0U0RRdjlDMTBZRFF0ZEdGMEw3UXROQzQwWUxRdFNEUXY5QytJTkdCMFlIUmk5QzcwTHJRc05DOExDRFF2ZEMxSU5DKzBZTFF2OUdBMExEUXN0QzcwWS9RdWRHQzBMVWcwTC9Rc05HQTBMN1F1OUM0TENEUmdTRFF2dEdCMFlMUXZ0R0EwTDdRdHRDOTBMN1JnZEdDMFl6UmppRFF2dEdDMExyUmdOR0wwTExRc05DNTBZTFF0U0RRc3RDNzBMN1F0dEMxMEwzUXVOR1BMaVpzZERzdmFUNG1iSFE3TDNBK0ppTjRaRHNLSm14ME8ySnlQaVlqZUdRN0NpWnNkRHRpY2o0bUkzaGtPd29tYkhRN1luSStKaU40WkRzS0pteDBPMkp5UGlZamVHUTdDaVpzZER0a2FYWStKaU40WkRzS0pteDBPM0FnYzNSNWJHVTlJbTFoY21kcGJpMTBiM0E2SURCd2VEc2lJR1JwY2owaWJIUnlJajRtYkhRN0wzQStKaU40WkRzS0pteDBPMlJwZGlCcFpEMGliV0ZwYkMxaGNIQXRZWFYwYnkxa1pXWmhkV3gwTFhOcFoyNWhkSFZ5WlNJK0ppTjRaRHNLSm14ME8zQWdaR2x5UFNKc2RISWlQaTB0Sm14ME8ySnlQaVlqZUdRN0N0Q2UwWUxRdjlHQTBMRFFzdEM3MExYUXZkQytJTkM0MExjZ1RXRnBiQzV5ZFNEUXROQzcwWThnUVc1a2NtOXBaQ1pzZERzdmNENG1JM2hrT3dvbWJIUTdMMlJwZGo0bUkzaGtPd290TFMwdExTMHRMU0RRbjlDMTBZRFF0ZEdCMEx2UXNOQzkwTDNRdnRDMUlOQy8wTGpSZ2RHTTBMelF2aUF0TFMwdExTMHRMU1pzZER0aWNqNG1JM2hrT3dyUW50R0NPaURRcU5DdzBZRFF1TkMvMEw3UXNpRFFsTkN3MEx6UXVOR0FJTkNZMFlEUXRkQzYwTDdRc3RDNDBZY2dKbXgwTzJFZ2FISmxaajBpYldGcGJIUnZPbk5vWVhKcGNHOTJaR2xBYzNCckxuSjFJajV6YUdGeWFYQnZkbVJwUUhOd2F5NXlkU1pzZERzdllUNG1iSFE3WW5JK0ppTjRaRHNLMEpyUXZ0QzgwWU02SUVSaGJXbHlJRk5vWVhKcGNHOTJJQ1pzZER0aElHaHlaV1k5SW0xaGFXeDBienBrWVcxcGNpNXphR0Z5YVhCdmRqSXpRRzFoYVd3dWNuVWlQbVJoYldseUxuTm9ZWEpwY0c5Mk1qTkFiV0ZwYkM1eWRTWnNkRHN2WVQ0bWJIUTdZbkkrSmlONFpEc0swSlRRc05HQzBMQTZJTkMvMFkvUmd0QzkwTGpSaHRDd0xDQXhNaURRdU5HTzBMdlJqeUF5TURJMDBMTXVMQ0F3T1RveE9TQW1ZVzF3T3lNME16c3dOVG93TUNac2REdGljajRtSTNoa093clFvdEMxMEx6UXNEb2cwSmZRa05HUDBMTFF1dEN3Sm14ME8ySnlQaVlqZUdRN0NpWnNkRHRpY2o0bUkzaGtPd29tYkhRN1lteHZZMnR4ZFc5MFpTQnBaRDBpYldGcGJDMWhjSEF0WVhWMGJ5MXhkVzkwWlNJZ1kybDBaVDBpTVRjeU1EYzFOemsyT1RBeE16ZzFOekF3TmpNaUlITjBlV3hsUFNKaWIzSmtaWEl0YkdWbWREb3hjSGdnYzI5c2FXUWdJekF3TlVaR09Uc2diV0Z5WjJsdU9qQndlQ0F3Y0hnZ01IQjRJREV3Y0hnN0lIQmhaR1JwYm1jNk1IQjRJREJ3ZUNBd2NIZ2dNVEJ3ZURzaVBpWWplR1E3Q2lac2REdGthWFlnWTJ4aGMzTTlJbXB6TFdobGJIQmxjaUJxY3kxeVpXRmtiWE5uTFcxelp5SStKbXgwTzNOMGVXeGxJSFI1Y0dVOUluUmxlSFF2WTNOeklqNG1iSFE3TDNOMGVXeGxQaVpzZER0aVlYTmxJSFJoY21kbGREMGlYM05sYkdZaUlHaHlaV1k5SW1oMGRIQnpPaTh2WlM1dFlXbHNMbkoxTHlJK0ppTjRaRHNLSm14ME8yUnBkaUJwWkQwaWMzUjViR1ZmTVRjeU1EYzFOemsyT1RBeE16ZzFOekF3TmpNaVBpWWplR1E3Q2lac2REdGthWFlnYVdROUluTjBlV3hsWHpFM01qQTNOVGM1Tmprd01UTTROVGN3TURZelgwSlBSRmtpUGlZamVHUTdDaVpzZER0a2FYWWdZMnhoYzNNOUltTnNYemMzTnpFek9TSStKaU40WkRzS0pteDBPMlJwZGlCamJHRnpjejBpVjI5eVpGTmxZM1JwYjI0eFgyMXlYMk56YzE5aGRIUnlJajRtSTNoa093b21iSFE3Y0NCamJHRnpjejBpVFhOdlRtOXliV0ZzWDIxeVgyTnpjMTloZEhSeUlqNG1iSFE3WWo0bWJIUTdjM0JoYmlCemRIbHNaVDBpWm05dWRDMXphWHBsT2pFd0xqQndkRHRtYjI1MExXWmhiV2xzZVRvblFYSnBZV3duTEhOaGJuTXRjMlZ5YVdZN1kyOXNiM0k2WW14aFkyc2lQdENmMEw3UXU5QyswWUhRc0NBNElEVXdJTkdCMFlJejBML1JnUy9SZ2RDL0lDMGdPU0RSaU5HQ0pteDBPeTl6Y0dGdVBpWnNkRHN2WWo0bWJIUTdMM0ErSmlONFpEc0tKbXgwTzNBZ1kyeGhjM005SWsxemIwNXZjbTFoYkY5dGNsOWpjM05mWVhSMGNpSStKbXgwTzJJK0pteDBPM053WVc0Z2MzUjViR1U5SW1admJuUXRjMmw2WlRveE1DNHdjSFE3Wm05dWRDMW1ZVzFwYkhrNkowRnlhV0ZzSnl4ellXNXpMWE5sY21sbU8yTnZiRzl5T21Kc1lXTnJJajdRbzlDejBMN1F1OUMrMExvZzBMelF0ZEdDMExEUXU5QzcwTGpSaDlDMTBZSFF1dEM0MExrZ05UQjROVEI0TlNBMjBMd2cwWUhSZ2pQUXY5R0JOUy9SZ2RDL05TQXRJRFF5SU5HSTBZSW1iSFE3TDNOd1lXNCtKbXgwT3k5aVBpWnNkRHN2Y0Q0bUkzaGtPd29tYkhRN2NDQmpiR0Z6Y3owaVRYTnZUbTl5YldGc1gyMXlYMk56YzE5aGRIUnlJajRtYkhRN2MzQmhiaUJ6ZEhsc1pUMGlabTl1ZEMxemFYcGxPakV3TGpCd2REdG1iMjUwTFdaaGJXbHNlVG9uUVhKcFlXd25MSE5oYm5NdGMyVnlhV1k3WTI5c2IzSTZZbXhoWTJzaVB0Q2YwWURRdnRDeTBMN1F1OUMrMExyUXNDRFFzdEdQMExmUXNOQzcwWXpRdmRDdzBZOGdNOUM4MEx3ZzRvQ1RJREUxTUNEUXV0Q3pKbXgwT3k5emNHRnVQaVpzZERzdmNENG1JM2hrT3dvbWJIUTdjQ0JqYkdGemN6MGlUWE52VG05eWJXRnNYMjF5WDJOemMxOWhkSFJ5SWo0bWJIUTdjM0JoYmlCemRIbHNaVDBpWm05dWRDMXphWHBsT2pFeUxqQndkRHRqYjJ4dmNqcGliR0ZqYXp0dGMyOHRabUZ5WldGemRDMXNZVzVuZFdGblpUcFNWU0krMEpEUmdOQzgwTERSZ3RHRDBZRFFzQ0RRcENBeE50QzgwTHdnTlRFd0lOR0kwWUlnMEwvUXZpWmhiWEE3Ym1KemNEc2dNVExRdkNac2REc3ZjM0JoYmo0bWJIUTdMM0ErSmlONFpEc0tKbXgwTzNBZ1kyeGhjM005SWsxemIwNXZjbTFoYkY5dGNsOWpjM05mWVhSMGNpSStKbXgwTzNOd1lXNGdjM1I1YkdVOUltWnZiblF0YzJsNlpUb3hNaTR3Y0hRN1kyOXNiM0k2WW14aFkyczdiWE52TFdaaGNtVmhjM1F0YkdGdVozVmhaMlU2VWxVaVB0Q2YwWURRdnRDeTBMN1F1OUMrMExyUXNDRFFzdEdQMExmUXNOQzcwWXpRdmRDdzBZOG1ZVzF3TzI1aWMzQTdJQ1poYlhBN2JtSnpjRHNnSm1GdGNEdHVZbk53T3pFMU1OQzYwTE1tYkhRN0wzTndZVzQrSm14ME95OXdQaVlqZUdRN0NpWnNkRHR3SUdOc1lYTnpQU0pOYzI5T2IzSnRZV3hmYlhKZlkzTnpYMkYwZEhJaVBpWnNkRHR6Y0dGdUlITjBlV3hsUFNKbWIyNTBMWE5wZW1VNk1UTXVOWEIwTzJOdmJHOXlPbUpzWVdOcklqN1FxTkN5MExYUXU5QzcwTFhSZ0NEUXN5L1F1aUF5TU5DZklDMGdORFV3SU5DNjBMTW1iSFE3WW5JK0ppTjRaRHNLMEtqUXN0QzEwTHZRdTlDMTBZQWcwTE12MExvZ01URFFueTBnT0RBZzBMclFzeVpzZER0aWNqNG1JM2hrT3dyUXFOQ3kwTFhRdTlDNzBMWFJnQ0F4TnRDZklDMGdOelV3SU5DNjBMTW1iSFE3WW5JK0ppTjRaRHNLTkM3UW90R0EwWVBRc2RDd0lERXdNTkdGTVRBdzBZVTFJRGd3TUNEUXV0Q3pKbXgwT3k5emNHRnVQaVpzZERzdmNENG1JM2hrT3dvbWJIUTdjQ0JqYkdGemN6MGlUWE52VG05eWJXRnNYMjF5WDJOemMxOWhkSFJ5SWo0bWJIUTdjM0JoYmlCemRIbHNaVDBpWm05dWRDMXphWHBsT2pFekxqVndkRHRqYjJ4dmNqcGliR0ZqYXlJKzBLTFJnTkdEMExIUXNDQTBNTkNsTmpEUXBUUWdMU0EyTWpBZzBMclFzeVpzZER0aWNqNG1JM2hrT3dyUW90R0EwWVBRc2RDd0lEUXcwWVUwTU5HRk5DQXRJREV3TUNEUXV0Q3pKbXgwTzJKeVBpWWplR1E3Q3RDaTBZRFJnOUN4MExBZ01qRFJoVEl3MFlVeUlDMGdOVEFnMExyUXN5WnNkRHRpY2o0bUkzaGtPd3JRb3RHQTBZUFFzZEN3SURVdzBZVTFNTkdGTlNBdElETTFNREFnMExyUXN5WnNkRHRpY2o0bUkzaGtPd3JRbzlDejBMN1F1OUMrMExvZ05ERFJoVFF3MFlVMElDMGdNalV3SU5DNjBMTW1iSFE3WW5JK0ppTjRaRHNLMEtQUXM5QyswTHZRdnRDNklEVXcwWVUxTU5HRk5TQXRJRFV3SU5DNjBMTW1iSFE3WW5JK0ppTjRaRHNLMEtQUXM5QyswTHZRdnRDNklEVXcwWVUxTU5HRk5DQXRJREUxTUNEUXV0Q3pKbXgwT3k5emNHRnVQaVpzZERzdmNENG1JM2hrT3dvbWJIUTdjQ0JqYkdGemN6MGlUWE52VG05eWJXRnNYMjF5WDJOemMxOWhkSFJ5SWo0bWJIUTdjM0JoYmlCemRIbHNaVDBpWm05dWRDMXphWHBsT2pFekxqVndkRHRqYjJ4dmNqcGliR0ZqYXlJKzBMRFJnTkM4MExEUmd0R0QwWURRc0NEUWtEVXdNQ0F4TUNBdElERXpNQ0RRdXRDekpteDBPMkp5UGlZamVHUTdDdEN3MFlEUXZOQ3cwWUxSZzlHQTBMQWcwSkEwTURBZ01UQWdMU0EwTUNEUXV0Q3pKbXgwT3k5emNHRnVQaVpzZER0emNHRnVJSE4wZVd4bFBTSm1iMjUwTFhOcGVtVTZNVEl1TUhCME8yTnZiRzl5T21Kc1lXTnJPMjF6YnkxbVlYSmxZWE4wTFd4aGJtZDFZV2RsT2xKVklqNG1iSFE3TDNOd1lXNCtKbXgwT3k5d1BpWWplR1E3Q2lac2REdHdJR05zWVhOelBTSk5jMjlPYjNKdFlXeGZiWEpmWTNOelgyRjBkSElpUGlac2REdHpjR0Z1SUhOMGVXeGxQU0ptYjI1MExYTnBlbVU2TVRJdU1IQjBPMk52Ykc5eU9tSnNZV05yTzIxemJ5MW1ZWEpsWVhOMExXeGhibWQxWVdkbE9sSlZJajRtWVcxd08yNWljM0E3Sm14ME95OXpjR0Z1UGlac2REc3ZjRDRtSTNoa093b21iSFE3Y0NCamJHRnpjejBpVFhOdlRtOXliV0ZzWDIxeVgyTnpjMTloZEhSeUlqNG1ZVzF3TzI1aWMzQTdKbXgwT3k5d1BpWWplR1E3Q2lac2REc3ZaR2wyUGlZamVHUTdDaVpzZER0d0lITjBlV3hsUFNKamIyeHZjam9qTTJFM05XTTBPMlp2Ym5RNk9YQjBJRUZ5YVdGc0lqN1FvOUN5MExEUXR0Q3cwTFhRdk5HTDBMVWcwTHJRdnRDNzBMdlF0ZEN6MExnZzBMZ2cwTC9Rc05HQTBZTFF2ZEMxMFlEUml5d21iSFE3TDNBK0ppTjRaRHNLSm14ME8zQWdjM1I1YkdVOUltTnZiRzl5T2lNellUYzFZelE3Wm05dWREbzVjSFFnUVhKcFlXd2lQdENkMExEUmlOQ3dJTkNhMEw3UXZOQy8wTERRdmRDNDBZOGcwTC9SZ05DNDBMVFF0ZEdBMExiUXVOQ3kwTERRdGRHQzBZSFJqeURSamRHQzBMalJoOUMxMFlIUXV0QzQwWVVnMEwvUmdOQzQwTDNSaHRDNDBML1F2dEN5SU5DeTBMWFF0TkMxMEwzUXVOR1BJTkN4MExqUXQ5QzkwTFhSZ2RDd0lOQzRJTkMwMExYUXU5Q3cwTFhSZ2lEUXN0R0IwTFVnMExUUXU5R1BJTkdDMEw3UXM5QytMQ0RSaDlHQzBMN1FzZEdMSU5DeTBMZlFzTkM0MEx6UXZ0QyswWUxRdmRDKzBZalF0ZEM5MExqUmp5RFJnU0RRdmRDdzBZalF1TkM4MExnZzBML1FzTkdBMFlMUXZkQzEwWURRc05DODBMZ2cwWUhSZ3RHQTBMN1F1TkM3MExqUmdkR01JTkM5MExBZzBML1JnTkM0MEwzUmh0QzQwTC9Rc05HRklOQyswWUxRdXRHQTBZdlJndEMrMFlIUmd0QzRJTkM0SU5DLzBZRFF2dEMzMFlEUXNOR0gwTDNRdnRHQjBZTFF1QzRnMEovUXZ0R04wWUxRdnRDODBZTWcwTC9SZ05DKzBZSFF1TkM4SU5DUzBMRFJnU0RSZ2RDKzBMN1FzZEdKMExEUmd0R01JTkM5MExEUXZDRFF2dEN4MEw0ZzBMTFJnZEMxMFlVbUkzaGtPd29nMEwzUXRkQ3owTERSZ3RDNDBMTFF2ZEdMMFlVZzBZVFFzTkM2MFlMUXNOR0ZJTkN5MEw0ZzBMTFF0OUN3MExqUXZOQyswTDdSZ3RDOTBMN1JpTkMxMEwzUXVOR1AwWVVnMFlFZzBMM1FzTkdJMExYUXVTRFF1dEMrMEx6UXY5Q3cwTDNRdU5DMTBMa2cwTC9RdmlEUXNOQzAwWURRdGRHQjBZTWdKbXgwTzJFZ2MzUjViR1U5SW1OdmJHOXlPaU16WVRjMVl6UTdJaUJvY21WbVBTSXZMMlV1YldGcGJDNXlkUzlqYjIxd2IzTmxMejl0WVdsc2RHODliV0ZwYkhSdkpUTmhaRzkyWlhKcFpVQnpZMjB1Y25VaUlIUmhjbWRsZEQwaVgySnNZVzVySWlCeVpXdzlJaUJ1YjI5d1pXNWxjaUJ1YjNKbFptVnljbVZ5SWo0bUkzaGtPd3BrYjNabGNtbGxRSE5qYlM1eWRTWnNkRHN2WVQ0dUlOQ1MwWUhSanlEUXVOQzkwWVRRdnRHQTBMelFzTkdHMExqUmp5RFF2OUMrMFlIUmd0R0QwTC9Rc05DMTBZSWcwTElnMEwzUXRkQzMwTERRc3RDNDBZSFF1TkM4MFlQUmppRFJnZEM3MFlQUXR0Q3gwWU1nMExMUXZkR0QwWUxSZ05DMTBMM1F2ZEMxMExQUXZpRFFzTkdEMExUUXVOR0MwTEF1Sm14ME95OXdQaVlqZUdRN0NpWnNkRHR3SUhOMGVXeGxQU0pqYjJ4dmNqb2pNMkUzTldNME8yWnZiblE2T1hCMElFRnlhV0ZzSWo3UW45R0EwTFhSZ3RDMTBMM1F0OUM0MExnZzBML1F2aURRdXRDdzBZZlF0ZEdCMFlMUXN0R0RJTkMrMExIUmdkQzcwWVBRdHRDNDBMTFFzTkM5MExqUmp5RFF1TkM3MExnZzBZTFF2dEN5MExEUmdOQ3dJTkMvMFlEUXVOQzkwTGpRdk5DdzBZN1JndEdCMFk4ZzBMM1FzQ0RSZ3RDMTBMdlF0ZEdFMEw3UXZTRFFzOUMrMFlEUmo5R0gwTFhRdVNEUXU5QzQwTDNRdU5DNEppTjRaRHNLSm14ME8zVStKbXgwTzNOd1lXNGdZMnhoYzNNOUltcHpMWEJvYjI1bExXNTFiV0psY2lJK09DMDRNREF0TnpBd01DMHhNak1tYkhRN0wzTndZVzQrSm14ME95OTFQaTRnMEpmUXN0QyswTDNRdXRDNElOQy8wTDRnMEtEUXZ0R0IwWUhRdU5DNElOQ3gwTFhSZ2RDLzBMdlFzTkdDMEwzUXZpWnNkRHN2Y0Q0bUkzaGtPd29tYkhRN0wyUnBkajRtSTNoa093b21iSFE3TDJScGRqNG1JM2hrT3dvbWJIUTdMMlJwZGo0bUkzaGtPd29tYkhRN0wyUnBkajRtSTNoa093b21iSFE3TDJKc2IyTnJjWFZ2ZEdVK0ppTjRaRHNLSm14ME95OWthWFkrSmlONFpEc0tKbXgwT3k5aWIyUjVQaVlqZUdRN0NpWnNkRHN2YUhSdGJENG1JM2hrT3dvOEwyWnBiR1ZEYjI1MFpXNTBQand2YW5OdmJrOWlhbVZqZEQ0OEwzTnZZWEJsYm5ZNlFtOWtlVDQ4TDNOdllYQmxiblk2Ulc1MlpXeHZjR1Ur"
    email_content = text_from_hash(hash)
    print("Начало обработки...")
    start_time = time.time()
    results = selector.process_email(email_content)
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Время обработки письма: {elapsed_time:.2f} секунд")

    print("Итоговые результаты подбора материалов:")
    for pos, res in results.items():
        print(f"Позиция: {pos} -> Материалы: {res}")