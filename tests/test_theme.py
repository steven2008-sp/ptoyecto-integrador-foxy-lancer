import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import theme  # noqa: E402

# Parejas (texto, fondo) que se usan juntas en la interfaz.
PAIRS = [
    ("text", "bg"), ("text", "surface"), ("text", "surface2"), ("muted", "surface"), ("muted", "bg"),
    ("muted", "surface2"), ("on_primary", "primary"), ("on_primary", "primary_hover"),
    ("primary_text", "primary_soft"), ("primary_text", "surface"), ("secondary_text", "secondary_bg"),
    ("secondary_text", "secondary_hover"), ("success", "success_bg"), ("warn", "warn_bg"),
    ("danger", "danger_bg"), ("info", "info_bg"), ("neutral", "neutral_bg"),
    ("disabled_text", "disabled_bg"), ("slot_sel_text", "slot_sel_bg"), ("on_hero", "hero1"),
    ("on_hero", "hero2"), ("on_hero_muted", "hero1"), ("on_hero_muted", "hero2"),
    ("primary_text", "surface"), ("muted", "primary_soft"),
]


def _check(palette):
    bad = []
    for fg, bg in PAIRS:
        ratio = theme.contrast(palette[fg], palette[bg])
        if ratio < 4.5:
            bad.append((fg, bg, round(ratio, 2)))
    assert palette["danger_btn"] and theme.contrast("#ffffff", palette["danger_btn"]) >= 4.5
    return bad


def test_light_contrast():
    assert _check(theme.LIGHT) == []


def test_dark_contrast():
    assert _check(theme.DARK) == []


def test_stylesheet_template_has_no_missing_keys():
    from string import Template
    values = dict(theme.LIGHT)
    values["check_icon"] = "x.png"
    theme.QSS.substitute(values)
    values = dict(theme.DARK)
    values["check_icon"] = "x.png"
    theme.QSS.substitute(values)


if __name__ == "__main__":
    for fn in (test_light_contrast, test_dark_contrast, test_stylesheet_template_has_no_missing_keys):
        fn()
        print("OK", fn.__name__)
