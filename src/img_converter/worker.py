import os
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from PyQt5.QtCore import QThread, pyqtSignal

from PIL import Image

from .formats import WRITE_LABEL_TO_FMT, DDS_COMPRESSION_MAP
from .filters import apply_filters, prepare_image

__all__ = ["ConverterWorker"]


class ConverterWorker(QThread):
    progress = pyqtSignal(int, int, str)
    file_done = pyqtSignal(str, bool, str)
    finished = pyqtSignal(int, int)

    def __init__(self, files, output_dir, output_fmt_label, options, n_workers=None):
        super().__init__()
        self.files = files
        self.output_dir = output_dir
        self.output_fmt_label = output_fmt_label
        self.options = options
        self.n_workers = n_workers or os.cpu_count() or 4
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def _save_image(self, image, dst):
        fmt = self.output_fmt_label
        opts = self.options
        kw = {}

        if fmt == "PNG":
            kw["compress_level"] = opts.get("png_compression", 6)
        elif fmt == "JPEG":
            kw["quality"] = opts.get("jpeg_quality", 90)
            if image.mode == "RGBA":
                image = image.convert("RGB")
        elif fmt == "WebP":
            kw["quality"] = opts.get("webp_quality", 85)
            if opts.get("webp_lossless", False):
                kw["lossless"] = True
        elif fmt == "TIFF":
            c = opts.get("tiff_compression", "None")
            if c == "LZW":
                kw["compression"] = "tiff_lzw"
            elif c == "Deflate":
                kw["compression"] = "tiff_adobe_deflate"
        elif fmt == "GIF":
            kw["optimize"] = True
        elif fmt == "DDS":
            label = opts.get("dds_format", "DXT5 (RGBA, interpolated alpha)")
            kw["dds_format"] = DDS_COMPRESSION_MAP.get(label, "DXT5")
        elif fmt == "AVIF":
            kw["quality"] = opts.get("avif_quality", 80)
        elif fmt == "HEIF":
            kw["quality"] = opts.get("heif_quality", 80)

        image.save(dst, format=fmt, **kw)

    def _process_one(self, src):
        if self._cancelled:
            return None
        name = Path(src).name
        stem = Path(src).stem
        ext = WRITE_LABEL_TO_FMT.get(self.output_fmt_label).exts[0]
        dst = str(Path(self.output_dir) / f"{stem}{ext}")

        ow = self.options.get("overwrite_mode", "Overwrite")
        if ow == "Skip" and os.path.exists(dst):
            return (name, True, "skipped")
        if ow == "Rename (add number)":
            p = Path(dst)
            n = 1
            while p.exists():
                p = p.with_name(f"{p.stem}_{n}{p.suffix}")
                n += 1
            dst = str(p)

        try:
            image = Image.open(src)
            image = prepare_image(image, self.options)
            image = apply_filters(image, self.options)
            self._save_image(image, dst)
            if self.options.get("preserve_mtime", False):
                shutil.copystat(src, dst)
            return (name, True, "")
        except Exception as e:
            return (name, False, str(e))

    def run(self):
        total = len(self.files)
        ok = fail = 0
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

        done = 0
        with ThreadPoolExecutor(max_workers=self.n_workers) as pool:
            futures = {pool.submit(self._process_one, src): src for src in self.files}
            for future in as_completed(futures):
                if self._cancelled:
                    break
                result = future.result()
                done += 1
                if result is None:
                    continue
                name, success, msg = result
                self.progress.emit(done, total, name)
                self.file_done.emit(name, success, msg)
                if success:
                    ok += 1
                else:
                    fail += 1

        self.finished.emit(ok, fail)
