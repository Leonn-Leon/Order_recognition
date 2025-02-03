import pandas as pd
import numpy as np
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from order_recognition.core.my_gigachat import EmailRequestRecognizer

# Список известных ключевых слов для материалов
MATERIAL_KEYWORDS = ["арматура", "балка", "труба", "уголок", "профиль", "круг"]

def normalize_text(text):
    """
    Приводит текст к нижнему регистру и выполняет замену вариантов размера:
      - Заменяет слово "a3" (с учётом границ слова) на "a iii".
    Можно расширить эту функцию для других нормализаций при необходимости.
    """
    text = text.lower()
    # Заменяем вариант "a3" на "a iii"
    text = re.sub(r'\ba3\b', 'a iii', text)
    text = re.sub(r'\ba2\b', 'a i', text)
    text = re.sub(r'\ba1\b', 'a i', text)
    return text

def get_primary_keyword(query):
    """
    Извлекает первое найденное ключевое слово из известного списка.
    Если ни одно ключевое слово не найдено, возвращает None.
    """
    query_lower = normalize_text(query)
    for kw in MATERIAL_KEYWORDS:
        if kw in query_lower:
            return kw
    return None

def extract_numbers(text):
    """
    Извлекает все числа (целые и дробные) из строки и возвращает их в виде списка float.
    """
    nums = re.findall(r'\d+(?:\.\d+)?', text)
    return [float(num) for num in nums]

def numerical_distance(query_text, candidate_text):
    """
    Вычисляет «числовое расстояние» между числами, извлечёнными из query_text и candidate_text.
    Если в candidate_text меньше чисел, чем в query_text, возвращается бесконечность.
    Суммируются абсолютные разности первых N чисел, где N = количество чисел в query_text.
    """
    query_nums = extract_numbers(query_text)
    candidate_nums = extract_numbers(candidate_text)
    if len(candidate_nums) < len(query_nums):
        return float('inf')
    return sum(abs(q - c) for q, c in zip(query_nums, candidate_nums))

class MaterialSearcherTFIDF:
    def __init__(self, materials, embedding_field="Полное наименование материала"):
        """
        :param materials: Список словарей с данными о материалах (например, из mats.csv)
        :param embedding_field: Название поля, по которому будут рассчитываться TF-IDF вектора.
        """
        self.materials = materials
        self.embedding_field = embedding_field
        # Приводим тексты к нормализованному виду (нижний регистр + замена вариантов размера)
        self.texts = [normalize_text(material[self.embedding_field]) for material in self.materials]
        # Инициализируем TfidfVectorizer и строим матрицу TF-IDF
        self.vectorizer = TfidfVectorizer()
        self.tfidf_matrix = self.vectorizer.fit_transform(self.texts)
    
    def search_by_tfidf(self, query, top_k=50):
        """
        Выполняет поиск по TF-IDF и возвращает top_k кандидатов с наибольшей косинусной схожестью.
        :param query: Строка запроса (например, "арматура 10 11 a3")
        :param top_k: Количество кандидатов, отбираемых на первом этапе.
        :return: Список словарей с информацией о материале и дополнительным полем "tfidf_similarity".
        """
        query_norm = normalize_text(query)
        query_vector = self.vectorizer.transform([query_norm])
        similarities = cosine_similarity(query_vector, self.tfidf_matrix)[0]
        top_indices = np.argsort(similarities)[::-1][:top_k]
        results = []
        for idx in top_indices:
            material = self.materials[idx].copy()
            material["tfidf_similarity"] = float(similarities[idx])
            results.append(material)
        return results

    def two_stage_search(self, query, top_k_embedding=50, top_k_final=5):
        """
        Двухэтапный поиск:
         1. Отбор top_k_embedding кандидатов по TF-IDF схожести.
         2. Фильтрация кандидатов по основному ключевому слову (если есть) и дальнейший ранжир по числовому расстоянию.
        :param query: Строка запроса (например, "арматура 10 11 a3")
        :param top_k_embedding: Количество кандидатов на первом этапе.
        :param top_k_final: Количество материалов для возврата после второго этапа.
        :return: Список из top_k_final записей.
        """
        # Этап 1: поиск по TF-IDF
        candidates = self.search_by_tfidf(query, top_k=top_k_embedding)
        
        # Определяем основной ключевой термин из запроса (например, "арматура")
        primary_kw = get_primary_keyword(query)
        if primary_kw:
            candidates = [c for c in candidates if primary_kw in normalize_text(c[self.embedding_field])]
            if not candidates:
                print(f"Не найдено кандидатов с ключевым словом '{primary_kw}'.")
                return []
            
        recognizer = EmailRequestRecognizer()
        
        # Этап 2: вычисляем числовое расстояние между числами из запроса и нормализованного полного наименования кандидата
        query_norm = normalize_text(query)
        for candidate in candidates:
            candidate_text_norm = normalize_text(candidate[self.embedding_field])
            candidate["num_distance"] = numerical_distance(query_norm, candidate_text_norm)
        
        candidates_sorted = sorted(candidates, key=lambda x: x["num_distance"])
        return candidates_sorted[:top_k_final]

if __name__ == "__main__":
    # Загружаем данные из файла mats.csv.
    csv_file = "order_recognition/data/mats.csv"
    df = pd.read_csv(csv_file)
    materials = df.to_dict(orient="records")
    
    # Инициализируем поисковик с использованием TF-IDF эмбеддингов и нормализации
    searcher = MaterialSearcherTFIDF(materials)
    
    # Пример строки запроса (например, извлечённой с помощью GPT)
    query = "труба 325 10 09г2с 8732 4"
    
    # Выполняем двухэтапный поиск: сначала top 50 кандидатов по TF-IDF, затем фильтрация по ключевому слову и числовым параметрам до top 5
    final_results = searcher.two_stage_search(query, top_k_embedding=50, top_k_final=5)
    
    print("Top 5 наиболее подходящих материалов:")
    for res in final_results:
        print(f"Материал: {res.get('Материал', 'N/A')}, Полное наименование: {res['Полное наименование материала']}, "
              f"Числовое расстояние: {res['num_distance']:.4f}, TF-IDF similarity: {res['tfidf_similarity']:.4f}")