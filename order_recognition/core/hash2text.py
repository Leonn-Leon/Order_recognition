import base64
import json
import xml.etree.ElementTree as ET
import html
from bs4 import BeautifulSoup
from order_recognition.utils.data_text_processing import Data_text_processing

def html_from_xml(xml_data):
    root = ET.fromstring(xml_data)
    html_content = html.unescape(root.find('.//fileContent').text)
    return html_content

def convert_html_to_text(html_content):
    soup = BeautifulSoup(html_content, features="html.parser")
    return soup.get_text('\n').replace('\r', ' ')

def xml_from_hash(hash):
    content = base64.standard_b64decode(base64.standard_b64decode(hash)).decode('utf-8')
    return content
def text_from_hash(hash):
    content = xml_from_hash(hash)
    try:
        html_content = html_from_xml(content)
    except:
        html_content = json.loads(content)["fileContent"]
    # print(html_content)
    text = convert_html_to_text(html_content)
    text = Data_text_processing().clean_email_content(text)
    return text

if __name__ == '__main__':
    hash = "..."
    text = text_from_hash(hash)