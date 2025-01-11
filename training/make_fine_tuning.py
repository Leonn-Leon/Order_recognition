import re
import json

# Define the pattern to detect lines with multiple '%' symbols (can have other characters as well)
delimiter_pattern = re.compile(r'%{6,}')

questions_path = 'data/Selected_only_text.csv'
answers_path = 'data/Selected_only_text_answers.csv'

# Read the files and split by a line with multiple '%' symbols to get individual entries
with open(questions_path, 'r', encoding='utf-8') as f:
    questions_text = f.read().splitlines()

with open(answers_path, 'r', encoding='utf-8') as f:
    answers_text = f.read().splitlines()

# Extract questions and answers by grouping lines between delimiters
questions = []
answers = []


# Function to group lines between delimiters
def extract_elements_v2(lines, output_list):
    temp = []
    for line in lines:
        if delimiter_pattern.search(line):
            if temp:
                output_list.append("\n".join(temp).strip())
                temp = []
        else:
            temp.append(line)
    if temp:  # append the last collected element if any
        output_list.append("\n".join(temp).strip())

    # Process questions and answers using the refined delimiter detection


extract_elements_v2(questions_text, questions)
extract_elements_v2(answers_text, answers)

# Combine questions and answers into JSON format
examples = []
for question, answer in zip(questions, answers):
    question = question.replace('"\n', '').replace('"', '')
    example = {"request": [{"role": "system","text": "Тебе будет предоставляться текст письма металургической компании c некоторыми материалами. Тебе нужно написать список всех обсуждаемых материалов из этого письма, и в каком количестве каждый материал. Твой ответ должен содержать только список позиций, на каждую позицию 3 параметра разделённые знаком '|' название материала в точности из письма (строка с полной информацией о материале), единица измерения запрашиваемого материала (строка) и количество запрашиваемого материала (число). Единицы измерения должны быть: (тн кг мп шт пд м2 м). В некоторых письмах встречаются сокращения материалов, надо написать такие названия полностью. Дробную и целую часть в числах разделяй только точкой. Если размеры в строке написаны без наименования материала, то они относятся к ранее написанному материалу."},{"role": "user","text": question}],"response": answer}
    examples.append(example)

# Save the examples to a JSON file
output_path = 'data/fine_tuning_examples.json'
with open(output_path, 'w', encoding='utf-8') as f:
    for example in examples:
        f.writelines(str(json.dumps(example, ensure_ascii=False))+'\n')