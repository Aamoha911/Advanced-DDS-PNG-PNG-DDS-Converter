from dataclasses import dataclass, field

__all__ = [
    "FormatInfo", "FORMAT_REGISTRY", "SUPPORTED_READ_EXTENSIONS",
    "SUPPORTED_WRITE_FORMATS", "WRITE_LABEL_TO_FMT",
    "DDS_COMPRESSION", "DDS_COMPRESSION_LABELS", "DDS_COMPRESSION_MAP",
    "PNG_COMPRESSION", "PNG_COMPRESSION_ITEMS", "PNG_COMPRESSION_MAP",
    "TIFF_COMPRESSION_ITEMS",
]


@dataclass
class FormatInfo:
    label: str
    exts: list
    can_read: bool = True
    can_write: bool = True
    needs_plugin: bool = False
    plugin_name: str = ""


FORMAT_REGISTRY: list[FormatInfo] = [
    FormatInfo("DDS",  [".dds"],          True,  True,  False, ""),
    FormatInfo("PNG",  [".png"],          True,  True,  False, ""),
    FormatInfo("JPEG", [".jpg", ".jpeg"], True,  True,  False, ""),
    FormatInfo("WebP", [".webp"],         True,  True,  False, ""),
    FormatInfo("BMP",  [".bmp"],          True,  True,  False, ""),
    FormatInfo("GIF",  [".gif"],          True,  True,  False, ""),
    FormatInfo("TIFF", [".tiff", ".tif"], True,  True,  False, ""),
    FormatInfo("AVIF", [".avif"],         True,  True,  True,  "pillow-avif-plugin"),
    FormatInfo("HEIF", [".heic", ".heif"],True,  True,  True,  "pillow-heif"),
    FormatInfo("EXR",  [".exr"],          True,  False, False, ""),
    FormatInfo("QOI",  [".qoi"],          True,  True,  False, ""),
]

SUPPORTED_READ_EXTENSIONS: set = set()
SUPPORTED_WRITE_FORMATS: list[FormatInfo] = []

for _fmt in FORMAT_REGISTRY:
    if _fmt.needs_plugin:
        try:
            __import__(_fmt.plugin_name.replace("-", "_"))
        except ImportError:
            _fmt.can_read = False
            _fmt.can_write = False
    if _fmt.can_read:
        SUPPORTED_READ_EXTENSIONS.update(_fmt.exts)
    if _fmt.can_write:
        SUPPORTED_WRITE_FORMATS.append(_fmt)

WRITE_LABEL_TO_FMT = {f.label: f for f in SUPPORTED_WRITE_FORMATS}

# Per-format options
DDS_COMPRESSION = [
    ("DXT1 (RGB, no alpha)", "DXT1"),
    ("DXT3 (RGBA, explicit alpha)", "DXT3"),
    ("DXT5 (RGBA, interpolated alpha)", "DXT5"),
    ("BC7 (RGBA, high quality)", "BC7"),
    ("Uncompressed RGBA", "RGBA"),
]
DDS_COMPRESSION_LABELS = [d[0] for d in DDS_COMPRESSION]
DDS_COMPRESSION_MAP = dict(DDS_COMPRESSION)

PNG_COMPRESSION = [
    ("None (Fastest)", 0), ("Level 1", 1), ("Level 2", 2),
    ("Level 3", 3), ("Level 4", 4), ("Level 5", 5),
    ("Level 6", 6), ("Level 7", 7), ("Level 8", 8), ("Level 9 (Best)", 9),
]
PNG_COMPRESSION_ITEMS = [p[0] for p in PNG_COMPRESSION]
PNG_COMPRESSION_MAP = dict(PNG_COMPRESSION)

TIFF_COMPRESSION_ITEMS = ["None", "LZW", "Deflate"]
