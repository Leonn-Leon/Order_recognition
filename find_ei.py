import re
def find_quantities_and_units(text):
    # Расширенный паттерн для поиска единиц измерения и количества
    # Учитывает единицы измерения до и после числа, а также возможность дефиса
    pattern = r'\b(м|т|тн|кг|мп|шт)?\s*(-)?\s*(\d+\.?\d*)\s*(-)?\s*(м|т|тн|кг|мп|шт)?\b'
    matches = re.findall(pattern, text)
    quantities_and_units = []

    for unit_before, dash1, quantity, dash2, unit_after in matches:
        # Выбор единицы измерения, которая находится либо до, либо после числа
        unit = unit_before if unit_before else unit_after
        if unit:
            quantities_and_units.append((quantity, unit))
    if len(quantities_and_units) == 0:
        return ('1', 'шт')
    return quantities_and_units[-1]


# Пример использования
if __name__ == '__main__':
    text = "Уголок 100x100 7м тн 5.85"
    text = "профиль пн4 7540 3м 045 240шт"
    found_quantities_and_units = find_quantities_and_units(text)
    print("Найденные количества и единицы измерения:", found_quantities_and_units)
