"""
Image Converter Pro — CLI + GUI entry point.

Usage:
    python -m img_converter                # Launch GUI
    python -m img_converter --help         # CLI options
"""

import sys
import os
import argparse
from pathlib import Path

from . import VERSION, APP_NAME
from .formats import (
    SUPPORTED_READ_EXTENSIONS, SUPPORTED_WRITE_FORMATS,
    WRITE_LABEL_TO_FMT, PNG_COMPRESSION_MAP, DDS_COMPRESSION_MAP,
)
from .filters import apply_filters, prepare_image
from .worker import ConverterWorker

__all__ = ["main", "run_cli", "run_gui"]


def run_gui():
    from PyQt5.QtWidgets import QApplication
    from .ui import ConverterApp

    import ctypes
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("imgconverter")
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = ConverterApp()
    w.show()
    sys.exit(app.exec_())


def run_cli(args):
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from PIL import Image

    fmt_info = WRITE_LABEL_TO_FMT.get(args.format)
    if not fmt_info:
        available = ", ".join(f.label for f in SUPPORTED_WRITE_FORMATS)
        print(f"Unsupported output format '{args.format}'. Available: {available}")
        sys.exit(1)

    out_ext = fmt_info.exts[0]
    src = Path(args.input)
    dst = Path(args.output) if args.output else src

    if src.is_file():
        files = [str(src)]
    else:
        files = sorted([
            str(f) for f in src.rglob("*") if args.recursive
        ]) if args.recursive else sorted([
            str(f) for f in src.iterdir()
            if f.suffix.lower() in SUPPORTED_READ_EXTENSIONS
        ])

    if not files:
        print("No supported images found.")
        sys.exit(0)

    dst.mkdir(parents=True, exist_ok=True)

    opts = {
        "keep_alpha": not args.strip_alpha,
        "preserve_mtime": not args.no_timestamps,
        "overwrite_mode": "Overwrite" if args.force else "Skip",
        "output_fmt": args.format,
        "png_compression": PNG_COMPRESSION_MAP.get(args.png_compress, 6),
        "jpeg_quality": args.jpeg_quality,
        "webp_quality": args.webp_quality,
        "tiff_compression": "LZW" if args.tiff_lzw else "Deflate" if args.tiff_deflate else "None",
        "dds_format": args.dds_format,
        "avif_quality": args.avif_quality,
        "heif_quality": args.heif_quality,
        "resize": (args.resize_width, args.resize_height) if args.resize else None,
        "brightness": args.brightness or 0,
        "contrast": args.contrast or 0,
        "saturation": args.saturation or 100,
        "sharpening": args.sharpen,
        "blurring": args.blur,
    }

    total = len(files)
    ok = fail = 0
    n_workers = args.threads or os.cpu_count() or 4

    print(f"Converting {total} image{'s' if total != 1 else ''} to {args.format} "
          f"({n_workers} worker{'s' if n_workers != 1 else ''})...")

    def process_one(src_path):
        name = Path(src_path).name
        stem = Path(src_path).stem
        out_path = str(dst / f"{stem}{out_ext}")
        try:
            image = Image.open(src_path)
            image = prepare_image(image, opts)
            image = apply_filters(image, opts)
            # format-specific save
            kw = {}
            if args.format == "PNG":
                kw["compress_level"] = opts["png_compression"]
            elif args.format == "JPEG":
                kw["quality"] = opts["jpeg_quality"]
                if image.mode == "RGBA":
                    image = image.convert("RGB")
            elif args.format == "WebP":
                kw["quality"] = opts["webp_quality"]
            elif args.format == "TIFF":
                kw["compression"] = opts["tiff_compression"]
            elif args.format == "DDS":
                kw["dds_format"] = DDS_COMPRESSION_MAP.get(args.dds_format, "DXT5")
            elif args.format == "AVIF":
                kw["quality"] = opts["avif_quality"]
            elif args.format == "HEIF":
                kw["quality"] = opts["heif_quality"]
            image.save(out_path, format=args.format, **kw)
            return (name, True, "")
        except Exception as e:
            return (name, False, str(e))

    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        futures = {pool.submit(process_one, f): f for f in files}
        for i, future in enumerate(as_completed(futures), 1):
            name, success, msg = future.result()
            icon = "+" if success else "x"
            print(f"  [{icon}] {name}" + (f"  ({msg})" if msg else ""))
            if success:
                ok += 1
            else:
                fail += 1
            print(f"  Progress: {i}/{total}", end="\r")

    print(f"\nDone — {ok} converted" + (f", {fail} failed" if fail else "") + ".")


def build_parser():
    p = argparse.ArgumentParser(
        prog=APP_NAME,
        description=f"Bulk image converter — {len(SUPPORTED_READ_EXTENSIONS)} input formats supported."
    )
    p.add_argument("--input", "-i", help="Source file or directory")
    p.add_argument("--output", "-o", help="Output directory (defaults to input)")
    p.add_argument("--format", "-f", choices=[f.label for f in SUPPORTED_WRITE_FORMATS],
                    default="PNG", help="Output format")
    p.add_argument("--recursive", "-r", action="store_true", help="Scan subdirectories")
    p.add_argument("--threads", "-t", type=int, default=0, help="Worker thread count")
    p.add_argument("--force", action="store_true", help="Overwrite existing files")
    p.add_argument("--strip-alpha", action="store_true", help="Remove alpha channel")
    p.add_argument("--no-timestamps", action="store_true", help="Don't preserve mtime")

    # format-specific
    p.add_argument("--png-compress", choices=list(PNG_COMPRESSION_MAP.keys()),
                   default="Level 6", help="PNG compression level")
    p.add_argument("--jpeg-quality", type=int, default=90, help="JPEG quality 1-100")
    p.add_argument("--webp-quality", type=int, default=85, help="WebP quality 1-100")
    p.add_argument("--tiff-lzw", action="store_true", help="TIFF LZW compression")
    p.add_argument("--tiff-deflate", action="store_true", help="TIFF Deflate compression")
    from .formats import DDS_COMPRESSION_LABELS
    p.add_argument("--dds-format", default="DXT5 (RGBA, interpolated alpha)",
                   choices=DDS_COMPRESSION_LABELS,
                   help="DDS compression format")
    p.add_argument("--avif-quality", type=int, default=80, help="AVIF quality 1-100")
    p.add_argument("--heif-quality", type=int, default=80, help="HEIF quality 1-100")

    # filters
    p.add_argument("--resize", action="store_true", help="Enable resize")
    p.add_argument("--resize-width", type=int, default=1024, help="Resize width")
    p.add_argument("--resize-height", type=int, default=1024, help="Resize height")
    p.add_argument("--brightness", type=int, default=0, help="Brightness adjustment (-100..100)")
    p.add_argument("--contrast", type=int, default=0, help="Contrast adjustment (-100..100)")
    p.add_argument("--saturation", type=int, default=100, help="Saturation (0..300)")
    p.add_argument("--sharpen", action="store_true", help="Apply sharpening")
    p.add_argument("--blur", action="store_true", help="Apply blur")
    p.add_argument("--version", action="version", version=f"{APP_NAME} v{VERSION}")

    return p


def main():
    args = build_parser().parse_args()

    if args.input:
        run_cli(args)
    else:
        run_gui()


if __name__ == "__main__":
    main()
