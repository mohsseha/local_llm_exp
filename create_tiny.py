
from PIL import Image, ImageDraw
img = Image.new('RGB', (200, 100), color='white')
d = ImageDraw.Draw(img)
d.text((10, 10), "TEST OCR", fill=(0, 0, 0))
img.save('tiny_test.jpg')
print("Created tiny_test.jpg")
