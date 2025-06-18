

from collections import namedtuple


ColorTheme = namedtuple('ColorTheme', 'code name')

## actual color codes are set in CSS

color_themes = [
    ColorTheme(0, 'Default'),
    ColorTheme(1, 'Rei'),
    ColorTheme(2, 'Ai'),
    ColorTheme(3, 'Aqua'),
    ColorTheme(4, 'Neru'),
    ColorTheme(5, 'Gumi'),
    ColorTheme(6, 'Emu'),
    ColorTheme(7, 'Spacegray'),
    ColorTheme(8, 'Haku'),
    ColorTheme(9, 'Miku'),
    ColorTheme(10, 'Defoko'),
    ColorTheme(11, 'Kaito'),
    ColorTheme(12, 'Meiko'),
    ColorTheme(13, 'Leek'),
    ColorTheme(14, 'Teto'),
    ColorTheme(15, 'Ruby')
]

def theme_classes(color_code: int):
    cl = []
    sch, th = divmod(color_code, 256)
    if sch == 1:
        cl.append('color-scheme-light')
    if sch == 2:
        cl.append('color-scheme-dark')
    if 1 <= th <= 15:
        cl.append(f'color-theme-{th}')

    return ' '.join(cl)
