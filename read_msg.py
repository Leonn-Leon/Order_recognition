import xml.etree.ElementTree as ET
import string

# root = ET.fromstring(country_data_as_string)
tree = ET.parse('data/mesage_example.xml')
# tree = ET.parse('data/mesage_example.xml')
root = tree.getroot()

# _string = ET.tostring(tree.getroot(), encoding='utf-8', method='text')

for child in root:
    print(child.tag)


body = root.find('{http://schemas.xmlsoap.org/soap/envelope/}Body')
_json = body.find('jsonObject')
content = _json.find('fileContent').text
content = content.translate(str.maketrans('', '', string.punctuation))
# print(content)
for i in content.split('\n'):
    if len(i) < 2:
        continue
    print(ord('a'), ord('b'), ord('а'), ord('б'), ord('9'))
    if i[0] != '!':
        # print(i.replace('<!-- ', '').replace('-->', ''))
        print(i)
    break