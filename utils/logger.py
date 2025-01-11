from datetime import datetime

def write_logs(file_name, text, event=1):
    event = 'EVENT' if event == 1 else 'ERROR'
    date_time = datetime.now().astimezone()
    with open(file_name, 'a', encoding="utf-8") as file:
        file.write(f"{date_time} | {event} | {text}\n")
