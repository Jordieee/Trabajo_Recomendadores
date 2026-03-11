import fitz

doc = fitz.open('Trabajo 4. SR Colaborativo.pdf')
text = ""
for page in doc:
    text += page.get_text()
    
with open('t4_reqs.txt', 'w', encoding='utf-8') as f:
    f.write(text)
print("Text extracted to t4_reqs.txt")
