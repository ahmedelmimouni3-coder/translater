import textwrap
from PIL import Image, ImageDraw, ImageFont

try:
    import arabic_reshaper
    RTL_SUPPORT = True
except ImportError:
    RTL_SUPPORT = False

# Base language codes whose scripts the default font (Arial) cannot draw. Codes such as zh-CN are compared by their base part.
UNSUPPORTED_LANG_CODES = [
    'zh', 'ja', 'ko', 'hi', 'bn', 'ta', 'te', 'th',
    'gu', 'kn', 'ml', 'mr', 'ne', 'or', 'pa', 'si', 'as', 'sa', 'bho', 'doi', 'mai', 'gom', 'mni',
    'my', 'km', 'lo', 'am', 'ti', 'dv',
]

FONT_CANDIDATES = ["arial.ttf", "tahoma.ttf", "segoeui.ttf", "DejaVuSans.ttf"]

_MIRROR = {"(": ")", ")": "(", "[": "]", "]": "[", "{": "}", "}": "{", "<": ">", ">": "<", "«": "»", "»": "«"}


def is_unsupported_language(code):
    """Returns True when the language code (e.g. 'zh-CN') uses a script the image font cannot draw."""
    return (code or "").split("-")[0].lower() in UNSUPPORTED_LANG_CODES


def _is_rtl_char(ch):
    """Returns True for Arabic and Hebrew characters, including the presentation forms."""
    code = ord(ch)
    return (0x0590 <= code <= 0x08FF) or (0xFB1D <= code <= 0xFDFF) or (0xFE70 <= code <= 0xFEFF)


def _char_type(ch):
    """Classifies a character as 'R' (right-to-left), 'L' (letter or digit) or 'N' (neutral)."""
    if _is_rtl_char(ch):
        return "R"
    return "L" if ch.isalnum() else "N"


def _visual_order(line):
    """Reorders a shaped line for right-to-left display (simplified bidi with a right-to-left base direction)."""
    types = [_char_type(c) for c in line]
    resolved = list(types)
    for i, t in enumerate(types):
        if t != "N":
            continue
        prev_t = next((types[j] for j in range(i - 1, -1, -1) if types[j] != "N"), None)
        next_t = next((types[j] for j in range(i + 1, len(types)) if types[j] != "N"), None)
        resolved[i] = prev_t if (prev_t is not None and prev_t == next_t) else "R"
    runs = []
    for ch, t in zip(line, resolved):
        if runs and runs[-1][0] == t:
            runs[-1][1] += ch
        else:
            runs.append([t, ch])
    pieces = []
    for direction, text in reversed(runs):
        if direction == "R":
            text = "".join(_MIRROR.get(c, c) for c in reversed(text))
        pieces.append(text)
    return "".join(pieces)


def _prepare_line(line):
    """Shapes Arabic letters and reorders the line for display when RTL support is available."""
    if not RTL_SUPPORT:
        return line
    return _visual_order(arabic_reshaper.reshape(line))


def _load_font(font_size):
    """Returns the first available TrueType font from FONT_CANDIDATES, or Pillow's default font."""
    for name in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, size=font_size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def _wrap_keeping_paragraphs(text, wrap_width):
    """Wraps each paragraph separately so the line breaks of the text are kept (empty lines stay empty)."""
    lines = []
    for paragraph in text.replace("\r", "").split("\n"):
        wrapped = textwrap.wrap(paragraph, width=wrap_width)
        lines.extend(wrapped if wrapped else [""])
    return lines


def text_to_image(text, save_path, img_width=850, img_height=550, font_size=22, wrap_width=52):
    """Draws the text on a white image, saves it to save_path and returns that path.

    The image grows in height when the text does not fit. Right-to-left lines are right-aligned, other lines left-aligned.
    """
    margin = 35
    line_height = font_size + 10
    wrapped_lines = _wrap_keeping_paragraphs(text, wrap_width)
    img_height = max(img_height, margin * 2 + line_height * len(wrapped_lines))

    image = Image.new("RGB", (img_width, img_height), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    font = _load_font(font_size)

    y_offset = margin
    for line in wrapped_lines:
        if line:
            display_line = _prepare_line(line)
            if any(_is_rtl_char(c) for c in line):
                x = img_width - margin - draw.textlength(display_line, font=font)
            else:
                x = margin
            draw.text((x, y_offset), display_line, fill=(0, 0, 0), font=font)
        y_offset += line_height

    image.save(save_path)
    return save_path
