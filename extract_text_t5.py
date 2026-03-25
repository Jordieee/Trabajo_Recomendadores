import fitz
doc = fitz.open('Trabajo 5. SR Híbrido.pdf')
text = ""
for page in doc:
    text += page.get_text()
    
with open('t5_reqs.txt', 'w', encoding='utf-8') as f:
    f.write(text)
print("Text extracted to t5_reqs.txt")
