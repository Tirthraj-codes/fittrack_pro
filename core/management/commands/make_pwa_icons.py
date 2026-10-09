from django.conf import settings
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw

COLORS = [(255, 107, 53), (247, 37, 133), (123, 47, 247)]          # orange, pink, purple
BOLT = [(0.58, 0.10), (0.28, 0.54), (0.46, 0.54), (0.38, 0.90), (0.72, 0.42), (0.53, 0.42), (0.64, 0.10)]


def gradient(size):
    """A diagonal orange-pink-purple background."""
    image = Image.new('RGB', (size, size))
    draw = ImageDraw.Draw(image)
    steps = size * 2
    for i in range(steps):
        t = i / (steps - 1)
        if t < 0.55:
            a, b, u = COLORS[0], COLORS[1], t / 0.55
        else:
            a, b, u = COLORS[1], COLORS[2], (t - 0.55) / 0.45
        color = tuple(int(a[k] + (b[k] - a[k]) * u) for k in range(3))
        draw.line([(i, 0), (0, i)], fill=color, width=3)
    return image


def make_icon(size, maskable=False):
    image = gradient(size).convert('RGBA')
    # Maskable icons get cropped by the phone, so the bolt must stay in the middle
    scale = 0.72 if maskable else 0.9
    offset = (1 - scale) / 2
    points = [((offset + x * scale) * size, (offset + y * scale) * size) for x, y in BOLT]
    ImageDraw.Draw(image).polygon(points, fill=(255, 224, 102, 255))

    if not maskable:                                  # normal icons have rounded corners
        mask = Image.new('L', (size, size), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.22), fill=255)
        image.putalpha(mask)
    return image


class Command(BaseCommand):
    help = 'Creates the PWA app icons in static/pwa/icons/.'

    def handle(self, *args, **options):
        folder = settings.BASE_DIR / 'static' / 'pwa' / 'icons'
        folder.mkdir(parents=True, exist_ok=True)

        make_icon(192).save(folder / 'icon-192.png')
        make_icon(512).save(folder / 'icon-512.png')
        make_icon(512, maskable=True).save(folder / 'maskable-512.png')
        make_icon(180, maskable=True).convert('RGB').save(folder / 'apple-touch-icon.png')   # iPhones want no transparency

        self.stdout.write(self.style.SUCCESS(f'Icons created in {folder}'))