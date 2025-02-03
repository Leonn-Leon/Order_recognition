import csv
import ast  # Вместо json используем ast для преобразования строки в Python-объект


# Чтение материалов из mats.csv
def load_materials(file_path):
    materials = {}
    with open(file_path, encoding="utf-8") as file:
        reader = csv.reader(file)
        for row in reader:
            if len(row) >= 2:
                material_id, description = row[0], row[4]
                materials[material_id] = description
    return materials


# Чтение данных из out_example.txt
def extract_materials(file_path, materials_dict):
    with open(file_path, encoding="utf-8") as file:
        # Используем ast.literal_eval для безопасного преобразования текста в Python-объект
        data = ast.literal_eval(file.read())

    result = []
    for position in data['positions']:
        materials = {}
        for key, value in position.items():
            if key.startswith("material") and str(int(value)) in materials_dict:
                materials[key] = materials_dict[str(int(value))]
        result.append({"position_id": position["position_id"],
                       "request_text": position["request_text"],
                       "ei": position["ei"],
                       "value": position["value"],
                       "materials": materials})

    return result


# Основной блок
def main():
    mats_csv_path = "order_recognition/data/mats.csv"
    out_example_path = "order_recognition/utils/out_example.txt"

    materials_dict = load_materials(mats_csv_path)
    extracted_data = extract_materials(out_example_path, materials_dict)

    # Вывод результата
    for entry in extracted_data:
        print(f"Position №{entry['position_id']}: {entry['request_text']} | {entry['ei']} | {entry['value']}")
        for mat_key, mat_desc in entry["materials"].items():
            print(f"  {mat_key}: {mat_desc}")
        print()


if __name__ == "__main__":
    main()