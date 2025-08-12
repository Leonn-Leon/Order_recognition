# order_recognition/core/distance.py
import pandas as pd
import uuid
from multiprocessing import Pool, cpu_count
# Импортируем все необходимое из worker.py
from .worker import init_worker, process_one_task, calculate_score

# ----------------------------------------------------
SACRIFICE_HIERARCHY = [
    # Самые маловажные, которыми жертвуем в первую очередь
    'цвет_ral',
    'покрытие',
    'гост_ту',
    'состояние',

    # Средней важности
    'марка стали',
    'тип',

    # Важные, но можно пожертвовать, если длина не указана
    'длина',
    
    # Ключевые параметры, которыми жертвуем в последнюю очередь
    'класс',      # для арматуры
    'номер',      # для швеллера/балки
    'толщина',    # для листа/трубы/уголка
    'размер',     # для профиля/уголка
    'диаметр',    # для арматуры/круглой трубы
]
# ----------------------------------------------------

class Find_materials():
    def __init__(self, csv_path='order_recognition/data/mats_with_features.csv'):
        self.csv_path = csv_path
        self.csv_encoding = 'utf-8'
        try:
            self.all_materials = pd.read_csv(self.csv_path, dtype=str, encoding=self.csv_encoding)
            self.all_materials['Материал'] = self.all_materials['Материал'].str.zfill(18)
            print('Класс Find_materials создан и данные для UI загружены.')
        except FileNotFoundError:
            print(f"ОШИБКА: Файл с признаками не найден по пути {self.csv_path}")
            self.all_materials = pd.DataFrame()

    def _search_single_pass(self, task: dict):
        """
        Выполняет ОДИН проход поиска для одной задачи.
        Возвращает словарь с результатами и лучшим скором.
        """
        original_query = task.get('original_query', '')
        base_name = task.get('base_name', '')
        query_params = task.get('params', {})
        
        candidates_df = self.all_materials[self.all_materials['base_name'] == base_name].copy()
        
        if candidates_df.empty:
            return {'request_text': original_query, 'best_score': -9999}

        candidates_df['score'] = candidates_df['params_json'].apply(
            lambda x: calculate_score(query_params, x)
        )
        candidates_df['score'] = pd.to_numeric(candidates_df['score'])
        
        top_results = candidates_df.sort_values(by="score", ascending=False).head(5)
        
        response_position = {'request_text': original_query}
        if not top_results.empty:
            response_position['best_score'] = top_results.iloc[0]['score']
        
        for i, (_, row_data) in enumerate(top_results.iterrows()):
            response_position[f'material{i+1}_id'] = row_data['Материал']
            response_position[f"weight_{i+1}"] = str(row_data['score'])
            
        return response_position

    def single_thread_rows(self, structured_rows: list[dict]):
        """
        Многопроходный поиск для Streamlit.
        Сначала ищет точное совпадение. Если не находит, "жертвует"
        наименее важными параметрами и ищет снова.
        """

        final_positions = []
        for task in structured_rows:
            original_params = task.get('params', {}).copy()
            

            result = self._search_single_pass(task)
            
            best_score = result.get('best_score', -9999)
            
            if best_score <= 0 and len(original_params) > 1:

                params_to_sacrifice = original_params.copy()
                
                for param_to_remove in SACRIFICE_HIERARCHY:
                    if param_to_remove in params_to_sacrifice:
                        del params_to_sacrifice[param_to_remove]
                       
                        new_task = task.copy()
                        new_task['params'] = params_to_sacrifice
                        
                        result = self._search_single_pass(new_task)
                        best_score = result.get('best_score', -9999)
                        
                        if best_score > 0:
                            break
            
            final_positions.append(result)

        return {"req_Number": str(uuid.uuid4()), "positions": final_positions}

    def parallel_rows(self, structured_rows: list[dict]):
        print("--- Запускается многопроцессорный режим. ---")
        if not structured_rows:
            return {"req_Number": str(uuid.uuid4()), "positions": []}
            
        tasks = structured_rows
        init_args = (self.csv_path, self.csv_encoding)
        
        num_processes = min(cpu_count(), len(tasks)) 
        if num_processes == 0: return {"req_Number": str(uuid.uuid4()), "positions": []}

        with Pool(initializer=init_worker, initargs=init_args, processes=num_processes) as pool:
            result_from_processes = pool.map(process_one_task, tasks)
        
        return {"req_Number": str(uuid.uuid4()), "positions": result_from_processes}