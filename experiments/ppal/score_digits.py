"""Exact supported Robotron display strings; never infer zero glyph count."""


def valid_display_digits(text):
    return (isinstance(text,str) and text.isascii() and text.isdigit()
            and 1<=len(text)<=7 and
            (text in ('0','00') or text[0]!='0'))
