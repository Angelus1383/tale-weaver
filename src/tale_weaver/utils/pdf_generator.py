# pip install reportlab pillow

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A5, landscape, portrait
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from xml.sax.saxutils import escape
from functools import lru_cache
from PIL import Image, ImageFilter, ImageOps
import os

def generate_storybook_pdf(
    storybook: dict,
    output_path: str,
    parchment_hex: str = "#F5EEDD",
    grain_strength: float = 0.24,   
    blur_radius: float = 1.2,       
    dpi: int = 150                  
) -> str:
    """
    Generate a storybook-style PDF with parchment-like textured backgrounds, 
    cover page, and illustrated text pages.

    Args:
        storybook (dict): Dictionary containing storybook content:
            - "storybook_title" (str): Title of the storybook.
            - "storybook_image_path" (str): Path to the cover image (optional).
            - "pages" (list of dict): Each page should include:
                - "page_number" (int): Page number.
                - "scene_image_path" (str): Path to the illustration image.
                - "scene_text" (str): Story text for the page.
        output_path (str): File path to save the generated PDF.
        parchment_hex (str, optional): Base hex color for parchment background.
        grain_strength (float, optional): Intensity of paper grain texture.
        blur_radius (float, optional): Blur radius applied to the parchment noise.
        dpi (int, optional): Resolution for generated textures.

    Returns:
        str: Path to the saved PDF file.
    """
    def draw_image(cnv, path, x, y, w, h):
        try:
            img = ImageReader(path)
            iw, ih = img.getSize()
            scale = min(w / iw, h / ih)
            nw, nh = iw * scale, ih * scale
            cnv.drawImage(img, x + (w - nw) / 2, y + (h - nh) / 2, nw, nh, mask='auto')
        except Exception:
            cnv.saveState()
            cnv.setFont("Times-Italic", 10)
            cnv.drawCentredString(x + w/2, y + h/2,
                                  f"[Image not available: {os.path.basename(path or '')}]")
            cnv.restoreState()

    def split_drop_cap(text: str):
        t = (text or "").lstrip()
        return (t[0], t[1:]) if t else ("", "")

    def _hex_to_rgb(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    def _shade(rgb, delta):
        r = max(0, min(255, rgb[0] + delta))
        g = max(0, min(255, rgb[1] + delta))
        b = max(0, min(255, rgb[2] + delta))
        return (r, g, b)

    @lru_cache(maxsize=4)
    def parchment_reader(w_pt: float, h_pt: float) -> ImageReader:
        """Create a paper texture as ImageReader (and cache it)."""
        base_rgb = _hex_to_rgb(parchment_hex)
        w_px = max(64, int(w_pt / 72.0 * dpi))
        h_px = max(64, int(h_pt / 72.0 * dpi))

        base = Image.new("RGB", (w_px, h_px), base_rgb)

        noise = Image.frombytes("L", (w_px, h_px), os.urandom(w_px * h_px))
        noise = noise.filter(ImageFilter.GaussianBlur(blur_radius))
        noise = ImageOps.autocontrast(noise, cutoff=1)
        noise = noise.point(lambda x: int(x * grain_strength))

        darker = Image.new("RGB", (w_px, h_px), _shade(base_rgb, -18))
        result = Image.composite(darker, base, noise)

        light_mask = ImageOps.invert(noise).point(lambda x: int(x * (grain_strength * 0.65)))
        lighter = Image.new("RGB", (w_px, h_px), _shade(base_rgb, +14))
        result = Image.composite(lighter, result, light_mask)

        result = result.filter(ImageFilter.GaussianBlur(0.4))

        return ImageReader(result)

    def draw_parchment_bg(cnv, w, h):
        bg = parchment_reader(w, h)
        cnv.drawImage(bg, 0, 0, width=w, height=h, mask='auto')

    
    c = canvas.Canvas(output_path, pagesize=portrait(A5))
    pw, ph = portrait(A5)
    margin = 10 * mm
    gap = 6 * mm

    draw_parchment_bg(c, pw, ph)
    cover_path = (storybook.get("storybook_image_path") or "").strip()
    if cover_path:
        draw_image(c, cover_path, margin, margin, pw - 2 * margin, ph - 2 * margin)
    else:
        c.setFont("Times-Bold", 24)
        c.drawCentredString(pw/2, ph/2, storybook.get("storybook_title", ""))

    c.showPage()

    pages = sorted(storybook.get("pages", []), key=lambda p: p.get("page_number", 0))
    body_size, leading = 13, 18
    body_style = ParagraphStyle("Body", fontName="Times-Roman", fontSize=body_size, leading=leading)

    lpw, lph = landscape(A5)
    for p in pages:
        c.setPageSize(landscape(A5))
        draw_parchment_bg(c, lpw, lph)

        left_x, left_y = margin, margin
        left_w = (lpw - 2 * margin - gap) / 2
        left_h = lph - 2 * margin
        draw_image(c, (p.get("scene_image_path") or "").strip(), left_x, left_y, left_w, left_h)

        right_x = margin + left_w + gap
        right_y = margin
        right_w = left_w
        right_h = left_h

        cap, rest = split_drop_cap(p.get("scene_text", ""))
        drop_html = f'<font size="{body_size*3:.0f}"><b>{escape(cap)}</b></font>{escape(rest)}'
        para = Paragraph(drop_html, body_style)
        _, phgt = para.wrap(right_w, right_h)
        y_text = right_y + max(0, (right_h - phgt) / 2.0)
        para.drawOn(c, right_x, y_text)

        c.setFont("Times-Roman", 10)
        c.drawRightString(right_x + right_w, 6, str(p.get("page_number", "")))
        c.showPage()

    c.save()
    return output_path
