"""Computer Vision & OCR Module.

OpenCV preprocessing (grayscale, upscaling, denoising, deskewing, binarisation) followed
by Tesseract OCR via pytesseract. Also computes an image-based layout quality score.
"""
import shutil
from functools import lru_cache

import cv2
import numpy as np

import config


class OCRUnavailableError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def tesseract_path() -> str | None:
    for cand in [config.TESSERACT_CMD, shutil.which("tesseract"), *config.TESSERACT_CANDIDATES]:
        if cand and shutil.which(cand):
            return cand
    return None


def ocr_available() -> bool:
    return tesseract_path() is not None


def decode_image(data: bytes) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("The file could not be decoded as an image.")
    return img


def _rotate(img: np.ndarray, angle: float, border=cv2.BORDER_REPLICATE, value=0) -> np.ndarray:
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)  # positive angle = counter-clockwise
    return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=border, borderValue=value)


def estimate_skew(gray: np.ndarray, max_angle: float = 10.0) -> float:
    """Projection-profile skew estimation.

    Text lines produce sharp peaks in the horizontal ink projection only when they are level, so the
    rotation that maximises the profile's variance is the correction angle (coarse 1° search, then 0.1°).
    """
    inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    if np.count_nonzero(inv) < 500:
        return 0.0
    scale = min(1.0, 900 / inv.shape[1])
    small = cv2.resize(inv, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else inv

    def score(a):
        return float(np.var(_rotate(small, a, cv2.BORDER_CONSTANT, 0).sum(axis=1, dtype=np.float64)))

    best = max(np.arange(-max_angle, max_angle + 0.01, 1.0), key=score)
    best = max(np.arange(best - 1.0, best + 1.01, 0.1), key=score)
    return round(float(best), 2)


def deskew(gray: np.ndarray) -> tuple[np.ndarray, float]:
    """Rotate so text lines are horizontal. Returns (image, correction angle in degrees)."""
    angle = estimate_skew(gray)
    if abs(angle) < 0.2:
        return gray, 0.0
    return _rotate(gray, angle), angle


def preprocess(img: np.ndarray) -> tuple[np.ndarray, dict]:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    h, w = gray.shape
    if w < 1500:  # upscale small scans so Tesseract sees ~300 DPI glyphs
        scale = 1500 / w
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.fastNlMeansDenoising(gray, h=10)
    gray, angle = deskew(gray)
    binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    return binary, {"skew_angle": round(angle, 2), "width": w, "height": h}


def layout_score(binary: np.ndarray, skew_angle: float = 0.0) -> float:
    """Heuristic 0-100 score of scan quality and layout: text blocks, margins, density, skew."""
    inv = cv2.bitwise_not(binary)
    h, w = inv.shape
    density = float(np.count_nonzero(inv)) / inv.size  # fraction of ink pixels
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(w // 40, 5), max(h // 150, 3)))
    blocks = cv2.dilate(inv, kernel, iterations=2)
    contours, _ = cv2.findContours(blocks, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = [cv2.boundingRect(c) for c in contours if cv2.contourArea(c) > (w * h) * 0.0005]

    score = 0.0
    # 1. Ink density: typical text pages are 3-20% ink
    score += 30 if 0.02 <= density <= 0.25 else 12
    # 2. Number of distinct text blocks (structured sections)
    score += min(len(boxes), 12) / 12 * 30
    # 3. Margins: content should not touch page edges
    if boxes:
        x0 = min(b[0] for b in boxes); y0 = min(b[1] for b in boxes)
        x1 = max(b[0] + b[2] for b in boxes); y1 = max(b[1] + b[3] for b in boxes)
        margins_ok = sum([x0 > w * 0.02, y0 > h * 0.02, x1 < w * 0.98, y1 < h * 0.98])
        score += margins_ok / 4 * 20
    # 4. Skew penalty
    score += max(0.0, 20 - abs(skew_angle) * 4)
    return round(min(score, 100.0), 1)


def ocr_image(img: np.ndarray) -> dict:
    """Run the CV pipeline + Tesseract. Returns text, mean word confidence (0-100) and layout score."""
    if not ocr_available():
        raise OCRUnavailableError(
            "Tesseract OCR is not installed. Install it (Windows: https://github.com/UB-Mannheim/tesseract/wiki) "
            "or set the TESSERACT_CMD environment variable to tesseract.exe."
        )
    import pytesseract

    pytesseract.pytesseract.tesseract_cmd = tesseract_path()
    binary, meta = preprocess(img)
    data = pytesseract.image_to_data(binary, config="--oem 3 --psm 6", output_type=pytesseract.Output.DICT)

    confs, lines, current_key, current = [], [], None, []
    for i, word in enumerate(data["text"]):
        conf = float(data["conf"][i])
        if not word.strip():
            continue
        if conf >= 0:
            confs.append(conf)
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        if key != current_key and current:
            lines.append(" ".join(current))
            current = []
        current_key = key
        current.append(word)
    if current:
        lines.append(" ".join(current))

    return {
        "text": "\n".join(lines),
        "ocr_confidence": round(float(np.mean(confs)), 1) if confs else 0.0,
        "layout_score": layout_score(binary, meta["skew_angle"]),
        **meta,
    }
