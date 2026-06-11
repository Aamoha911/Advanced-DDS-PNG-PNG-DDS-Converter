from PIL import Image, ImageFilter, ImageEnhance
from PyQt5.QtGui import QPixmap, QImage

__all__ = ["apply_filters", "prepare_image", "pil_to_pixmap"]


def apply_filters(image: Image.Image, opts: dict) -> Image.Image:
    if opts.get("sharpening"):
        image = ImageEnhance.Sharpness(image).enhance(2.0)
    if opts.get("blurring"):
        image = image.filter(ImageFilter.BLUR)
    b = opts.get("brightness", 0)
    if b:
        image = ImageEnhance.Brightness(image).enhance(1 + b / 100.0)
    c = opts.get("contrast", 0)
    if c:
        image = ImageEnhance.Contrast(image).enhance(1 + c / 100.0)
    s = opts.get("saturation", 100)
    if s != 100:
        image = ImageEnhance.Color(image).enhance(s / 100.0)
    return image


def prepare_image(image: Image.Image, opts: dict) -> Image.Image:
    if not opts.get("keep_alpha", True) and image.mode in ("RGBA", "PA"):
        image = image.convert("RGB")
    resize = opts.get("resize")
    if resize:
        image = image.resize(resize, Image.LANCZOS)
    return image


def pil_to_pixmap(image: Image.Image, max_size: int = 360) -> QPixmap:
    if image.mode == "RGBA":
        fmt = QImage.Format_RGBA8888
    else:
        image = image.convert("RGB")
        fmt = QImage.Format_RGB888

    w, h = image.size
    scale = min(max_size / w, max_size / h, 1.0)
    if scale < 1.0:
        nw, nh = int(w * scale), int(h * scale)
        image = image.resize((nw, nh), Image.LANCZOS)
        w, h = nw, nh

    data = image.tobytes()
    if image.mode == "RGBA":
        qimg = QImage(data, w, h, QImage.Format_RGBA8888)
    else:
        qimg = QImage(data, w, h, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg)
