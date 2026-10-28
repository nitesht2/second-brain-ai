"""Render architecture.d2 to light and dark SVGs in docs/screenshots/.

Needs the d2 CLI (https://d2lang.com) on PATH:
    python3 docs/diagrams/src/build.py
Optional: FONT_DIR pointing at Inter TTFs (Inter_400Regular.ttf and
Inter_600SemiBold.ttf, e.g. from the @expo-google-fonts/inter npm package).
Without it, D2's default font is used.
"""
import os
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1] / "screenshots"
THEMES = {
    "light": dict(BG="#ffffff", PANEL="#f6f7f9", CARD="#ffffff", BORDER="#e3e6eb",
                  TEXT="#1d2129", MUTED="#5f6774", EDGE="#9aa1ac",
                  LOCAL="#2f6fe4", VPS="#9333ea", SHARED="#16a34a"),
    "dark": dict(BG="#0d1117", PANEL="#161b22", CARD="#1c2129", BORDER="#30363d",
                 TEXT="#e6edf3", MUTED="#9aa4b0", EDGE="#6e7781",
                 LOCAL="#4f8ef7", VPS="#c084fc", SHARED="#4ade80"),
}

fonts = os.environ.get("FONT_DIR")
src = (HERE / "architecture.d2").read_text()

for name, colors in THEMES.items():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        d2 = src
        for key, value in colors.items():
            d2 = d2.replace("{{" + key + "}}", value)
        (tmp / "architecture.d2").write_text(d2)
        cmd = ["d2", "architecture.d2", str(OUT / f"architecture-{name}.svg")]
        if fonts:
            cmd += [f"--font-regular={fonts}/Inter_400Regular.ttf",
                    f"--font-bold={fonts}/Inter_600SemiBold.ttf",
                    f"--font-italic={fonts}/Inter_400Regular.ttf"]
        subprocess.run(cmd, cwd=tmp, check=True)
