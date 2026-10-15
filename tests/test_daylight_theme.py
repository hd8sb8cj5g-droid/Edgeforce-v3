"""Regression tests for mobile-readable EdgeForce Daylight colors."""
from pathlib import Path
import re
import tomllib

ROOT = Path(__file__).resolve().parents[1]
CONFIG = tomllib.loads((ROOT / '.streamlit/config.toml').read_text())
APP = (ROOT / 'app.py').read_text()


def rgb(c):
    return [int(c[i:i+2], 16) / 255 for i in (1, 3, 5)]


def luminance(c):
    values = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb(c)]
    return sum(x * y for x, y in zip(values, [0.2126, 0.7152, 0.0722]))


def contrast(a, b):
    x, y = sorted((luminance(a), luminance(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


def test_streamlit_theme_light_and_text_contrast():
    theme = CONFIG['theme']
    assert theme['base'] == 'light'
    assert contrast(theme['textColor'], theme['backgroundColor']) >= 7
    assert contrast(theme['textColor'], theme['secondaryBackgroundColor']) >= 7


def test_primary_button_and_secondary_text_wcag_aa():
    assert contrast('#FFFFFF', CONFIG['theme']['primaryColor']) >= 4.5
    assert contrast('#42546B', '#EDF3F8') >= 4.5
    assert contrast('#24384E', CONFIG['theme']['backgroundColor']) >= 4.5


def test_no_legacy_dark_chart_backgrounds():
    assert "paper_bgcolor='#152033'" not in APP
    assert "linear-gradient(165deg,#0d1320" not in APP
    assert "template='plotly_white'" in APP
    assert 'max-width: 700px' in APP


def test_theme_precedes_auth_gate():
    assert APP.index('/* EdgeForce Daylight') < APP.index('if _access_password and not st.session_state')
