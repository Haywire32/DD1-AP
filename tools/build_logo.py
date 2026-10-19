"""Prepare the approved logo for native texture import; do not generate overlays."""
from collections import deque
from pathlib import Path
from PIL import Image

root = Path(__file__).resolve().parents[1]
source = Image.open(root / 'game/Assets/APLogoSource.png').convert('RGB').resize((256, 256), Image.Resampling.LANCZOS)
image = source.convert('RGBA')
pixels = image.load()
background = bytearray(256 * 256)
queue = deque()

def can_remove(x, y):
    r, g, b, _ = pixels[x, y]
    return max(r, g, b) - min(r, g, b) <= 22 and max(r, g, b) >= 90

def seed(x, y):
    index = y * 256 + x
    if not background[index] and can_remove(x, y):
        background[index] = 1
        queue.append((x, y))

for n in range(256):
    seed(n, 0); seed(n, 255); seed(0, n); seed(255, n)
# The center is a second enclosed area of the preview checkerboard.
for y in range(100, 156):
    for x in range(100, 156):
        seed(x, y)
while queue:
    x, y = queue.popleft()
    for nx, ny in ((x-1,y), (x+1,y), (x,y-1), (x,y+1)):
        if 0 <= nx < 256 and 0 <= ny < 256:
            seed(nx, ny)
for y in range(256):
    for x in range(256):
        if background[y * 256 + x]:
            r, g, b, _ = pixels[x, y]
            pixels[x, y] = (r, g, b, 0)
bounds = image.getbbox()
if bounds is None:
    raise ValueError('Logo background removal produced an empty image.')
image = image.crop(bounds)
side = max(image.size) + 12
square = Image.new('RGBA', (side, side))
square.alpha_composite(image, ((side-image.width)//2, (side-image.height)//2))
image = square.resize((64, 64), Image.Resampling.LANCZOS)
image.save(root / 'game/Assets/APLogo.png')
image.save(root / 'game/Assets/APLogo.tga', format='TGA')
print('Prepared 64x64 PNG/TGA. Reimport APLogoNative.Logo before packaging changed artwork.')
