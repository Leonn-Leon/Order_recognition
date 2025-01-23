import base64
import json
import xml.etree.ElementTree as ET
import html
from bs4 import BeautifulSoup
from order_recognition.utils.data_text_processing import Data_text_processing

# Функция для парсинга XML и извлечения HTML-содержимого
def html_from_xml(xml_data):
    # Парсинг XML
    root = ET.fromstring(xml_data)
    # Нахождение элемента fileContent и декодирование HTML-содержимого
    html_content = html.unescape(root.find('.//fileContent').text)
    return html_content

# Функция для преобразования HTML в текст
def convert_html_to_text(html_content):
    soup = BeautifulSoup(html_content, features="html.parser")
    return soup.get_text('\n').replace('\r\n', ' ')

def xml_from_hash(hash):
    content = base64.standard_b64decode(base64.standard_b64decode(hash)).decode('utf-8')
    return content
def text_from_hash(hash):
    content = xml_from_hash(hash)
    try:
        html_content = html_from_xml(content)
    except:
        html_content = json.loads(content)["fileContent"]
    text = convert_html_to_text(html_content)
    text = Data_text_processing().clean_text(text)
    return text

if __name__ == '__main__':
    hash = "ZXlKaWRXTnJaWFJPWVcxbElqb2lZM0p0TFdWdFlXbHNJaXdpYjJKcVpXTjBUbUZ0WlNJNkltMXpaMTloTlRnNU1tRXdNbUkyTWpFNE5HTXhZV0UzTkdaaE1ETmxPV0psWldRMU5TSXNJbVpwYkdWRGIyNTBaVzUwSWpvaVhHNDhTRlJOVEQ0OFFrOUVXVDQ4Y0NCemRIbHNaVDFjSW0xaGNtZHBiaTEwYjNBNklEQndlRHRjSWlCa2FYSTlYQ0pzZEhKY0lqN1FvZEdIMExqUmd0Q3cwTFhRdkNEUmdkQzgwTFhSZ3RHRElOQzkwTEFnMEw3UXNkR0swTFhRdXRHQ0lESXdNalVnMExQUXZ0QzAwTEF1UEZ3dmNENWNianh3SUdScGNqMWNJbXgwY2x3aVB0Q2YwWURRdnRHSTBZTWcwTExSaTlHQjBZTFFzTkN5MExqUmd0R01JTkdCMFlmUXRkR0NMQ0RRdjlDMjBMc2dPanhjTDNBK1hHNDhjQ0JrYVhJOVhDSnNkSEpjSWo0eExpRFFvdEdBMFlQUXNkQ3dJTkMvMFlEUXZ0R0VJREUwTUNveE5EQXFOQ0JjZFRJd01UTWdNVElnMEx3dTBMOHVJTkNkMEw0ZzBMTFJpOUdCMFlMUXNOQ3kwTHZSajlDNUlOQ3lJTkdDMEw3UXZkQzkwTERSaFM0ZzBKelF2ZEMxSU5HQzBMRFF1aURRdjlDKzBMM1JqOUdDMEwzUXRkQzVJTkN4MFlQUXROQzEwWUl1UEZ3dmNENWNianh3SUdScGNqMWNJbXgwY2x3aVBqSXVJTkNvMExMUXRkQzcwTFhSZ0NBeU1DQmNkVEl3TVRNZ056SWcwTHd1MEw4dUlOQy8wTDRnTmlEUXZOQzEwWUxSZ05DKzBMSWcwTC9RdU5DNzBMWFF2ZEdMMExrdVBGd3ZjRDVjYmp4d0lHUnBjajFjSW14MGNsd2lQak11SU5DajBMUFF2dEM3MEw3UXVpQTNOU28xSUZ4MU1qQXhNeUF4TURnZzBMd3UwTDh1SU5DLzBMNGdOaURRdkNEUXY5QzQwTHZRdGRDOTBZdlF1UzQ4WW5JK1BHSnlQanhjTDNBK1hHNDhaR2wySUdsa1BWd2liV0ZwYkMxaGNIQXRZWFYwYnkxa1pXWmhkV3gwTFhOcFoyNWhkSFZ5WlZ3aVBseHVJRHh3SUdScGNqMWNJbXgwY2x3aVBpMHRQR0p5UGx4dUlDQWcwSjdSZ3RDLzBZRFFzTkN5MEx2UXRkQzkwTDRnMExqUXR5QThZU0JvY21WbVBWd2lhSFIwY0hNNkx5OXRZV2xzTG5KMUwxd2lQazFoYVd3OFhDOWhQaURRdE5DNzBZOGdRVzVrY205cFpEeGNMM0ErWEc0OFhDOWthWFkrUEZ3dlFrOUVXVDQ4WEM5SVZFMU1QbHh1SW4wPQ=="
    text = text_from_hash(hash)
    print(text)
