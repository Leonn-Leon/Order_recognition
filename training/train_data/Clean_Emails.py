import base64
from pathlib import Path
from order_recognition.utils.data_text_processing import Data_text_processing
from order_recognition.core.hash2text import text_from_hash

def process_emails(input_file, output_file):
    dp = Data_text_processing()
    
    with open("training/train_data/"+input_file, 'r', encoding='utf-8') as f:
        # encoded_emails = [line.rstrip('\n') for line in f if line.strip()]
        encoded_emails = f.readlines()
        
    encoded_emails = encoded_emails[1:]

    cleaned_texts = []
    for email in encoded_emails:
        decoded_text = text_from_hash(email)
        if decoded_text:
            # cleaned = dp.clean_email_content(decoded_text)
            cleaned_texts.append(decoded_text)

    separator = '\n\n' + '%' * 18 + '\n'
    result = separator.join(cleaned_texts)

    Path("training/train_data/"+output_file).write_text(result, encoding='utf-8')

if __name__ == "__main__":
    process_emails('Selected_Emails.csv', 'Selected_texts2.txt')