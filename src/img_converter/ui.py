import os
from pathlib import Path
from typing import Optional

from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QFileDialog, QVBoxLayout,
    QHBoxLayout, QMessageBox, QCheckBox, QSpinBox, QLineEdit,
    QComboBox, QGroupBox, QProgressBar, QTextEdit,
    QFrame, QSlider, QScrollArea,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QDragEnterEvent, QDropEvent

from PIL import Image

from . import VERSION, APP_NAME
from .formats import (
    SUPPORTED_READ_EXTENSIONS, SUPPORTED_WRITE_FORMATS,
    PNG_COMPRESSION_ITEMS, PNG_COMPRESSION_MAP,
    DDS_COMPRESSION_LABELS,
    TIFF_COMPRESSION_ITEMS,
)
from .filters import apply_filters, prepare_image, pil_to_pixmap
from .worker import ConverterWorker

__all__ = ["ConverterApp", "DropLine"]


class DropLine(QFrame):
    dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFixedHeight(36)
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
        lo = QHBoxLayout(self)
        lo.setContentsMargins(8, 0, 8, 0)
        self._label = QLabel("Drop folder here")
        self._label.setStyleSheet("color:#999; font-size:11px;")
        lo.addWidget(self._label)
        lo.addStretch()
        self.setStyleSheet("""
            DropLine { border: 1.5px dashed #aaa; border-radius:4px; background:#fafafa; }
            DropLine:hover { border-color:#4a9eff; background:#eef4ff; }
        """)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for url in e.mimeData().urls():
            p = url.toLocalFile()
            if os.path.isdir(p):
                self.dropped.emit(p)
                return

    def set_path(self, p):
        self._label.setText(p)
        self._label.setStyleSheet("color:#1a73e8; font-weight:bold; font-size:11px;")


class ConverterApp(QWidget):
    def __init__(self):
        super().__init__()
        self.source_dir = ""
        self.output_dir = ""
        self.worker: Optional[ConverterWorker] = None
        self._preview_path: Optional[str] = None
        self._preview_original: Optional[Image.Image] = None
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle(f"{APP_NAME} v{VERSION}")
        self.setMinimumSize(540, 700)
        self.resize(580, 780)

        self.setStyleSheet("""
            QWidget { font-family: 'Segoe UI', sans-serif; font-size: 12px; }
            QGroupBox {
                font-weight: 600; border: 1px solid #d0d0d0; border-radius: 5px;
                margin-top: 8px; padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 8px; padding: 0 5px; color: #333;
            }
            QPushButton {
                padding: 5px 14px; border-radius: 3px; border: 1px solid #ccc;
                background: #f5f5f5;
            }
            QPushButton:hover { background: #eaeaea; }
            QPushButton:disabled { color: #aaa; background: #f0f0f0; }
            QLineEdit {
                border: 1px solid #ccc; border-radius: 3px; padding: 4px 6px;
                background: #fafafa;
            }
            QLineEdit:focus { border-color: #4a9eff; background: #fff; }
            QProgressBar {
                border: 1px solid #bbb; border-radius: 3px; text-align: center;
                height: 20px; font-size: 11px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #4a9eff, stop:1 #43b380);
                border-radius: 2px;
            }
            QTextEdit {
                border: 1px solid #ccc; border-radius: 3px; background: #fafafa;
                font-family: 'Consolas','Courier New',monospace; font-size: 11px;
            }
            QComboBox {
                border: 1px solid #ccc; border-radius: 3px; padding: 3px 6px;
                background: #fafafa;
            }
            QComboBox:focus { border-color: #4a9eff; }
            QComboBox QAbstractItemView {
                background: #fff; border: 1px solid #bbb; selection-background-color: #1a73e8;
                selection-color: #fff; outline: none;
            }
            QComboBox QAbstractItemView::item:hover { background: #e8f0fe; color: #000; }
            QComboBox QAbstractItemView::item:selected { background: #1a73e8; color: #fff; }
            QSpinBox {
                border: 1px solid #ccc; border-radius: 3px; padding: 3px 4px;
                background: #fafafa;
            }
            QSpinBox:focus { border-color: #4a9eff; }
            QSlider::groove:horizontal {
                border: 1px solid #bbb; height: 5px; border-radius: 2px;
                background: #e0e0e0;
            }
            QSlider::handle:horizontal {
                background: #1a73e8; border: none; width: 14px; height: 14px;
                margin: -5px 0; border-radius: 7px;
            }
            QCheckBox { spacing: 5px; }
        """)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        self._root = QVBoxLayout(content)
        self._root.setSpacing(6)
        self._root.setContentsMargins(12, 10, 12, 10)

        self._build_header()
        self._build_output_section()
        self._build_source_section()
        self._build_output_dir_section()
        self._build_options_section()
        self._build_filters_section()
        self._build_preview_section()
        self._build_progress_section()
        self._build_actions()

        self._root.addStretch()
        scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        self._refresh_format_options()

    # ── header ──
    def _build_header(self):
        h = QLabel(APP_NAME)
        h.setFont(QFont("Segoe UI", 16, QFont.Bold))
        h.setAlignment(Qt.AlignCenter)
        h.setStyleSheet("color:#1a73e8; margin:2px 0;")
        self._root.addWidget(h)
        exts = ", ".join(sorted(SUPPORTED_READ_EXTENSIONS))
        sub = QLabel(f"Reads {len(SUPPORTED_READ_EXTENSIONS)} formats — {exts}")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("color:#888; font-size:10px; margin-bottom:2px;")
        self._root.addWidget(sub)

    # ── output format ──
    def _build_output_section(self):
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(QLabel("Output format:"))
        self.fmt_combo = QComboBox()
        self.fmt_combo.setMinimumWidth(160)
        for f in SUPPORTED_WRITE_FORMATS:
            self.fmt_combo.addItem(f.label, f.label)
        self.fmt_combo.currentIndexChanged.connect(self._refresh_format_options)

        self.threads_spin = QSpinBox()
        n_cpus = os.cpu_count() or 4
        self.threads_spin.setRange(1, n_cpus)
        self.threads_spin.setValue(n_cpus)
        self.threads_spin.setPrefix("Threads: ")
        self.threads_spin.setToolTip("Number of parallel conversion workers")
        row.addWidget(self.fmt_combo)
        row.addWidget(self.threads_spin)
        row.addStretch()
        f = QFrame()
        f.setLayout(row)
        self._root.addWidget(f)

    # ── source ──
    def _build_source_section(self):
        g = QGroupBox("Source")
        lo = QVBoxLayout(g)
        lo.setContentsMargins(8, 16, 8, 6)
        lo.setSpacing(4)
        row = QHBoxLayout()
        self.src_path = QLineEdit()
        self.src_path.setPlaceholderText("No folder selected")
        self.src_path.setReadOnly(True)
        row.addWidget(self.src_path)
        self.src_browse = QPushButton("Browse")
        self.src_browse.clicked.connect(self._pick_src)
        row.addWidget(self.src_browse)
        self.src_drop = DropLine()
        self.src_drop.dropped.connect(self._set_src)
        self.src_count = QLabel("")
        self.src_count.setStyleSheet("color:#888; font-size:11px;")
        lo.addLayout(row)
        lo.addWidget(self.src_drop)
        lo.addWidget(self.src_count)
        self._root.addWidget(g)

    # ── output ──
    def _build_output_dir_section(self):
        g = QGroupBox("Output")
        lo = QVBoxLayout(g)
        lo.setContentsMargins(8, 16, 8, 6)
        lo.setSpacing(4)
        row = QHBoxLayout()
        self.out_path = QLineEdit()
        self.out_path.setPlaceholderText("No folder selected (defaults to source)")
        self.out_path.setReadOnly(True)
        row.addWidget(self.out_path)
        self.out_browse = QPushButton("Browse")
        self.out_browse.clicked.connect(self._pick_out)
        row.addWidget(self.out_browse)
        self.out_same = QPushButton("Use Source")
        self.out_same.clicked.connect(self._out_same_as_src)
        row.addWidget(self.out_same)
        self.out_drop = DropLine()
        lo.addLayout(row)
        lo.addWidget(self.out_drop)
        self._root.addWidget(g)

    # ── options ──
    def _build_options_section(self):
        self.opt_grp = QGroupBox("Options")
        lo = QVBoxLayout(self.opt_grp)
        lo.setContentsMargins(8, 16, 8, 6)
        lo.setSpacing(4)
        r1 = QHBoxLayout()
        self.keep_alpha_cb = QCheckBox("Keep alpha")
        self.keep_alpha_cb.setChecked(True)
        self.preserve_mtime_cb = QCheckBox("Preserve timestamps")
        r1.addWidget(self.keep_alpha_cb)
        r1.addWidget(self.preserve_mtime_cb)
        r1.addStretch()
        lo.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("If exists:"))
        self.overwrite_combo = QComboBox()
        self.overwrite_combo.addItems(["Overwrite", "Skip", "Rename"])
        r2.addWidget(self.overwrite_combo)
        self._fmt_option_rows = {}

        def _add_fmt_opt(fmt, label, widget, setup_fn=None):
            lbl = QLabel(label)
            lbl.setVisible(False)
            widget.setVisible(False)
            if setup_fn:
                setup_fn(widget)
            r2.addWidget(lbl)
            r2.addWidget(widget)
            self._fmt_option_rows[fmt] = (lbl, widget)

        _add_fmt_opt("PNG", "PNG compression:", QComboBox(),
            lambda c: c.addItems(PNG_COMPRESSION_ITEMS) or c.setCurrentText("Level 6"))
        _add_fmt_opt("JPEG", "JPEG quality:", QSpinBox(),
            lambda c: (c.setRange(1, 100), c.setValue(90), c.setSuffix(" %")))
        _add_fmt_opt("WebP", "WebP quality:", QSpinBox(),
            lambda c: (c.setRange(1, 100), c.setValue(85), c.setSuffix(" %")))
        _add_fmt_opt("TIFF", "TIFF compression:", QComboBox(),
            lambda c: c.addItems(TIFF_COMPRESSION_ITEMS))
        _add_fmt_opt("DDS", "DDS format:", QComboBox(),
            lambda c: c.addItems(DDS_COMPRESSION_LABELS) or c.setCurrentText("DXT5 (RGBA, interpolated alpha)"))
        _add_fmt_opt("AVIF", "AVIF quality:", QSpinBox(),
            lambda c: (c.setRange(1, 100), c.setValue(80), c.setSuffix(" %")))
        _add_fmt_opt("HEIF", "HEIF quality:", QSpinBox(),
            lambda c: (c.setRange(1, 100), c.setValue(80), c.setSuffix(" %")))

        self.webp_lossless_cb = QCheckBox("Lossless")
        self.webp_lossless_cb.setVisible(False)
        r2.addWidget(self.webp_lossless_cb)
        self._fmt_option_rows["WebP_lossless"] = (QLabel(), self.webp_lossless_cb)
        r2.addStretch()
        lo.addLayout(r2)
        self._root.addWidget(self.opt_grp)

    # ── filters ──
    def _build_filters_section(self):
        self.flt_grp = QGroupBox("Filters")
        self.flt_grp.setCheckable(True)
        self.flt_grp.setChecked(False)
        self.flt_grp.toggled.connect(self._on_filters_toggled)
        lo = QVBoxLayout(self.flt_grp)
        lo.setContentsMargins(8, 16, 8, 6)
        lo.setSpacing(4)

        r1 = QHBoxLayout()
        self.resize_cb = QCheckBox("Resize")
        self.resize_cb.toggled.connect(self._schedule_preview)
        r1.addWidget(self.resize_cb)
        self.resize_w = QSpinBox()
        self.resize_w.setRange(1, 16384); self.resize_w.setValue(1024); self.resize_w.setEnabled(False)
        self.resize_h = QSpinBox()
        self.resize_h.setRange(1, 16384); self.resize_h.setValue(1024); self.resize_h.setEnabled(False)
        self.resize_w.valueChanged.connect(self._schedule_preview)
        self.resize_h.valueChanged.connect(self._schedule_preview)
        self.resize_cb.toggled.connect(self.resize_w.setEnabled)
        self.resize_cb.toggled.connect(self.resize_h.setEnabled)
        r1.addWidget(QLabel("W:")); r1.addWidget(self.resize_w)
        r1.addWidget(QLabel("H:")); r1.addWidget(self.resize_h)
        r1.addStretch()
        lo.addLayout(r1)

        sliders = [
            ("Brightness", -100, 100, 0, "%d", "brightness"),
            ("Contrast",   -100, 100, 0, "%d", "contrast"),
            ("Saturation", 0, 300, 100, "%d%%", "saturation"),
        ]
        for label, rmin, rmax, default, fmts, attr in sliders:
            r = QHBoxLayout()
            cb = QCheckBox(label)
            cb.toggled.connect(self._schedule_preview)
            sl = QSlider(Qt.Horizontal)
            sl.setRange(rmin, rmax); sl.setValue(default); sl.setEnabled(False)
            sl.valueChanged.connect(self._schedule_preview)
            val_lbl = QLabel(fmts % default)
            val_lbl.setMinimumWidth(36)
            val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val_lbl.setStyleSheet("color:#555; font-size:11px;")
            cb.toggled.connect(sl.setEnabled)
            sl.valueChanged.connect(lambda v, l=val_lbl, f=fmts: l.setText(f % v))
            r.addWidget(cb); r.addWidget(sl, 1); r.addWidget(val_lbl)
            lo.addLayout(r)
            setattr(self, f"{attr}_cb", cb)
            setattr(self, f"{attr}_sl", sl)

        rfx = QHBoxLayout()
        self.sharpen_cb = QCheckBox("Sharpen")
        self.sharpen_cb.toggled.connect(self._schedule_preview)
        self.blur_cb = QCheckBox("Blur")
        self.blur_cb.toggled.connect(self._schedule_preview)
        rfx.addWidget(self.sharpen_cb); rfx.addWidget(self.blur_cb); rfx.addStretch()
        lo.addLayout(rfx)
        self._root.addWidget(self.flt_grp)

    # ── preview ──
    def _build_preview_section(self):
        self.preview_grp = QGroupBox("Live Preview")
        self.preview_grp.setVisible(False)
        lo = QVBoxLayout(self.preview_grp)
        lo.setContentsMargins(8, 16, 8, 6)
        lo.setSpacing(6)

        top = QHBoxLayout()
        self.preview_pick_btn = QPushButton("Pick Sample Image...")
        self.preview_pick_btn.clicked.connect(self._pick_preview)
        self.preview_auto_btn = QPushButton("Auto from Source")
        self.preview_auto_btn.clicked.connect(self._auto_pick_preview)
        self.preview_info = QLabel("No image selected")
        self.preview_info.setStyleSheet("color:#888; font-size:11px;")
        top.addWidget(self.preview_pick_btn)
        top.addWidget(self.preview_auto_btn)
        top.addWidget(self.preview_info)
        top.addStretch()
        lo.addLayout(top)

        images = QHBoxLayout()
        images.setSpacing(12)

        left = QVBoxLayout()
        left.addWidget(QLabel("Original"), alignment=Qt.AlignCenter)
        self.orig_preview = QLabel()
        self.orig_preview.setFixedSize(260, 260)
        self.orig_preview.setAlignment(Qt.AlignCenter)
        self.orig_preview.setStyleSheet(
            "border: 1px solid #ddd; border-radius: 4px; background: #f5f5f5;"
        )
        left.addWidget(self.orig_preview)
        images.addLayout(left)

        arrow = QLabel("→")
        arrow.setFont(QFont("Segoe UI", 24))
        arrow.setAlignment(Qt.AlignCenter)
        arrow.setStyleSheet("color:#1a73e8;")
        images.addWidget(arrow)

        right = QVBoxLayout()
        right.addWidget(QLabel("Processed"), alignment=Qt.AlignCenter)
        self.proc_preview = QLabel()
        self.proc_preview.setFixedSize(260, 260)
        self.proc_preview.setAlignment(Qt.AlignCenter)
        self.proc_preview.setStyleSheet(
            "border: 1px solid #1a73e8; border-radius: 4px; background: #f5f5f5;"
        )
        right.addWidget(self.proc_preview)
        images.addLayout(right)

        lo.addLayout(images)
        self._root.addWidget(self.preview_grp)

        self._preview_timer = QTimer()
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(150)
        self._preview_timer.timeout.connect(self._do_preview)

    def _on_filters_toggled(self, on):
        self.preview_grp.setVisible(on)
        if on and not self._preview_path and self.source_dir:
            self._auto_pick_preview()

    def _schedule_preview(self):
        if self._preview_original is not None and self.flt_grp.isChecked():
            self._preview_timer.start()

    def _pick_preview(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "Select Sample Image", self.source_dir or "",
            f"Images ({' '.join('*'+e for e in SUPPORTED_READ_EXTENSIONS)})"
        )
        if p:
            self._load_preview(p)

    def _auto_pick_preview(self):
        if not self.source_dir:
            return
        for f in sorted(os.listdir(self.source_dir)):
            if Path(f).suffix.lower() in SUPPORTED_READ_EXTENSIONS:
                self._load_preview(os.path.join(self.source_dir, f))
                return

    def _load_preview(self, path):
        try:
            self._preview_path = path
            self._preview_original = Image.open(path).copy()
            self.preview_info.setText(Path(path).name)
            pm = pil_to_pixmap(self._preview_original, 260)
            self.orig_preview.setPixmap(pm)
            self._do_preview()
        except Exception as e:
            self.preview_info.setText(f"Error: {e}")

    def _do_preview(self):
        if self._preview_original is None:
            return
        try:
            opts = self._gather_preview_opts()
            img = self._preview_original.copy()
            img = prepare_image(img, opts)
            img = apply_filters(img, opts)
            pm = pil_to_pixmap(img, 260)
            self.proc_preview.setPixmap(pm)
        except Exception as e:
            self.proc_preview.setText(f"Error:\n{e}")

    def _gather_preview_opts(self):
        return {
            "keep_alpha": self.keep_alpha_cb.isChecked(),
            "resize": (self.resize_w.value(), self.resize_h.value()) if self.resize_cb.isChecked() else None,
            "brightness": self.brightness_sl.value() if self.brightness_cb.isChecked() else 0,
            "contrast": self.contrast_sl.value() if self.contrast_cb.isChecked() else 0,
            "saturation": self.saturation_sl.value() if self.saturation_cb.isChecked() else 100,
            "sharpening": self.sharpen_cb.isChecked(),
            "blurring": self.blur_cb.isChecked(),
        }

    # ── progress + log ──
    def _build_progress_section(self):
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self._root.addWidget(self.progress_bar)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(120)
        self.log.setPlaceholderText("Log will appear here...")
        self._root.addWidget(self.log)

    def _build_actions(self):
        r = QHBoxLayout()
        r.setSpacing(8)
        self.start_btn = QPushButton("Start Conversion")
        self.start_btn.setStyleSheet(
            "QPushButton{background:#1a73e8;color:#fff;border:none;"
            "font-weight:bold;font-size:13px;padding:7px 20px;border-radius:4px;}"
            "QPushButton:hover{background:#1557b0;}"
            "QPushButton:disabled{background:#aac6f2;}"
        )
        self.start_btn.clicked.connect(self._start)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setStyleSheet(
            "QPushButton{background:#e74c3c;color:#fff;border:none;"
            "padding:7px 16px;border-radius:4px;}"
            "QPushButton:hover{background:#c0392b;}"
            "QPushButton:disabled{background:#f0a8a0;}"
        )
        self.cancel_btn.clicked.connect(self._cancel)
        self.clr_btn = QPushButton("Clear")
        self.clr_btn.clicked.connect(self.log.clear)
        r.addWidget(self.start_btn)
        r.addWidget(self.cancel_btn)
        r.addWidget(self.clr_btn)
        r.addStretch()
        self._root.addLayout(r)

    # ──────────────────────────────────────────────
    # Format options vis
    # ──────────────────────────────────────────────

    def _refresh_format_options(self):
        label = self.fmt_combo.currentData()
        for key, (lbl, w) in self._fmt_option_rows.items():
            visible = (key == label)
            lbl.setVisible(visible)
            w.setVisible(visible)
        is_webp = (label == "WebP")
        self._fmt_option_rows.get("WebP_lossless", (None, None))[1].setVisible(is_webp)

    # ──────────────────────────────────────────────
    # Directory helpers
    # ──────────────────────────────────────────────

    def _set_src(self, p):
        self.source_dir = p
        self.src_path.setText(p)
        self.src_drop.set_path(p)
        self._update_file_count()

    def _pick_src(self):
        p = QFileDialog.getExistingDirectory(self, "Source Directory")
        if p:
            self._set_src(p)

    def _set_out(self, p):
        self.output_dir = p
        self.out_path.setText(p)
        self.out_drop.set_path(p)

    def _pick_out(self):
        p = QFileDialog.getExistingDirectory(self, "Output Directory")
        if p:
            self._set_out(p)

    def _out_same_as_src(self):
        if self.source_dir:
            self._set_out(self.source_dir)

    def _update_file_count(self):
        if not self.source_dir:
            self.src_count.setText("")
            return
        try:
            files = [f for f in os.listdir(self.source_dir)
                     if Path(f).suffix.lower() in SUPPORTED_READ_EXTENSIONS]
            n = len(files)
            self.src_count.setText(
                f"{n} image{'s' if n != 1 else ''} found" if n else "No supported images"
            )
        except Exception:
            self.src_count.setText("")

    def _fmt_val(self, key, attr="currentText", fallback=""):
        pair = self._fmt_option_rows.get(key)
        if pair:
            w = pair[1]
            return getattr(w, attr)() if callable(getattr(w, attr, None)) else getattr(w, attr, fallback)
        return fallback

    def _fmt_int(self, key, fallback=0):
        pair = self._fmt_option_rows.get(key)
        if pair:
            return pair[1].value()
        return fallback

    def _gather_opts(self) -> dict:
        label = self.fmt_combo.currentData()
        return {
            "keep_alpha": self.keep_alpha_cb.isChecked(),
            "preserve_mtime": self.preserve_mtime_cb.isChecked(),
            "overwrite_mode": self.overwrite_combo.currentText(),
            "output_fmt": label,
            "png_compression": PNG_COMPRESSION_MAP.get(self._fmt_val("PNG", fallback="Level 6"), 6),
            "jpeg_quality": self._fmt_int("JPEG", 90),
            "webp_quality": self._fmt_int("WebP", 85),
            "webp_lossless": self.webp_lossless_cb.isChecked(),
            "tiff_compression": self._fmt_val("TIFF", fallback="None"),
            "dds_format": self._fmt_val("DDS", fallback="DXT5 (RGBA, interpolated alpha)"),
            "avif_quality": self._fmt_int("AVIF", 80),
            "heif_quality": self._fmt_int("HEIF", 80),
            "resize": (self.resize_w.value(), self.resize_h.value()) if self.resize_cb.isChecked() else None,
            "brightness": self.brightness_sl.value() if self.brightness_cb.isChecked() else 0,
            "contrast": self.contrast_sl.value() if self.contrast_cb.isChecked() else 0,
            "saturation": self.saturation_sl.value() if self.saturation_cb.isChecked() else 100,
            "sharpening": self.sharpen_cb.isChecked(),
            "blurring": self.blur_cb.isChecked(),
        }

    # ──────────────────────────────────────────────
    # Conversion
    # ──────────────────────────────────────────────

    def _start(self):
        if not self.source_dir or not os.path.isdir(self.source_dir):
            QMessageBox.warning(self, "Missing Source", "Select a valid source directory.")
            return
        if not self.output_dir:
            self._set_out(self.source_dir)

        files = sorted([
            os.path.join(self.source_dir, f) for f in os.listdir(self.source_dir)
            if Path(f).suffix.lower() in SUPPORTED_READ_EXTENSIONS
        ])
        if not files:
            QMessageBox.information(self, "No Files", "No supported images in source directory.")
            return

        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

        opts = self._gather_opts()
        label = self.fmt_combo.currentData()
        n = self.threads_spin.value()
        self.worker = ConverterWorker(files, self.output_dir, label, opts, n_workers=n)
        self.worker.progress.connect(self._on_progress)
        self.worker.file_done.connect(self._on_file_done)
        self.worker.finished.connect(self._on_finished)

        self._set_busy(True)
        self.log.clear()
        self.log.append(f"Converting {len(files)} -> {label}  |  {n} worker{'s' if n!=1 else ''}\n")
        self.worker.start()

    def _cancel(self):
        if self.worker:
            self.worker.cancel()
            self.log.append("\nCancelled.")

    def _on_progress(self, cur, total, name):
        self.progress_bar.setValue(int(cur / total * 100))
        self.progress_bar.setFormat(f"{cur}/{total}  {name}")

    def _on_file_done(self, name, success, msg):
        icon = "OK" if success else "FAIL"
        self.log.append(f"  [{icon}] {name}" + (f"  ({msg})" if msg else ""))

    def _on_finished(self, ok, fail):
        self._set_busy(False)
        if fail == 0:
            self.log.append(f"\nDone — {ok} converted.")
        else:
            self.log.append(f"\nDone — {ok} OK, {fail} failed.")
        self.progress_bar.setFormat("")

    def _set_busy(self, busy):
        self.start_btn.setEnabled(not busy)
        self.cancel_btn.setEnabled(busy)
        for w in [self.src_browse, self.out_browse, self.out_same, self.fmt_combo, self.threads_spin]:
            w.setEnabled(not busy)
        self.progress_bar.setVisible(busy)
        self.opt_grp.setEnabled(not busy)
        self.flt_grp.setEnabled(not busy)
        if not busy:
            self.progress_bar.setValue(0)
