import fitz
import os

doc = fitz.open('Trabajo 4. SR Colaborativo.pdf')
os.makedirs('pdf_pages', exist_ok=True)
for i, page in enumerate(doc):
    mat = fitz.Matrix(2, 2)  # 2x zoom for better quality
    pix = page.get_pixmap(matrix=mat)
    pix.save(f'pdf_pages/page_{i+1:02d}.png')
print(f'Saved {len(doc)} pages as images in pdf_pages/')
