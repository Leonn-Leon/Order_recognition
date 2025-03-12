import re
import json

# Define the pattern to detect lines with multiple '%' symbols (can have other characters as well)
delimiter_pattern = re.compile(r'%{6,}')

questions_path = 'training/train_data/Selected_texts2.txt'
answers_path = 'training/train_data/Selected_text2_answers.txt'


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

def _load_instruction(instruction_path):
        """
        Загрузка системной инструкции из файла, которая будет передаваться
        в System-сообщении для GPT модели.
        """
        with open(instruction_path, 'r', encoding='utf-8') as file:
            return file.read().strip()

# Combine questions and answers into JSON format
examples = []
instruction = _load_instruction('order_recognition/confs/first_gpt_instruction.txt')
for question, answer in zip(questions, answers):
    question = question.replace('"\n', '').replace('"', '')
    
    example = {"request": [{"role": "system","text": instruction},{"role": "user","text": question}],"response": answer}
    examples.append(example)

# Save the examples to a JSON file
output_path = 'training/train_data/FT_lora_AG.json'
with open(output_path, 'w', encoding='utf-8') as f:
    for example in examples:
        f.writelines(str(json.dumps(example, ensure_ascii=False))+'\n')