# order_recognition/core/utils.py

def normalize_param(param_value: str) -> str:
    if not isinstance(param_value, str):
        return ""
    
    # Приводим к нижнему регистру и заменяем римские цифры
    text = param_value.lower()
    text = text.replace('iii', '3').replace('ii', '2').replace('i', '1')
    
    # Словарь замен для транслитерации и удаления разделителей
    replacements = {
        # Кириллица -> Латиница (важно для стали)
        'а': 'a', 'с': 'c', 'е': 'e', 'о': 'o', 
        'р': 'p', 'х': 'x', 'к': 'k', 'т': 't', 
        'у': 'y', 'в': 'b', 'м': 'm',
        
        '-': '', ' ': '', '.': '', '/': ''
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
        
    return text.strip()