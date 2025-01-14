from datetime import datetime

def write_logs(text, event=1):
    event = 'EVENT' if event == 1 else 'ERROR'
    date_time = datetime.now().astimezone()
    file_name = str(date_time.date()) + '.txt'
    with open("order_recognition/data/logs/"+file_name, 'a', encoding="utf-8") as file:
        file.write(f"{date_time} | {event} | {text}\n")
