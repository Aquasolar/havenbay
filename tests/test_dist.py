"""Prüfungen der fertig gebauten Seite (Ordner dist). Aufruf: python tests/test_dist.py <dist>"""
import json, os, re, sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

DIST = Path(sys.argv[1] if len(sys.argv) > 1 else "build/e2e-dist").resolve()
ROOT = Path(__file__).resolve().parents[1]
errors = []

def err(code, msg):
    errors.append(f"{code}: {msg}")

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.refs = []; self.eager = []; self.text = []; self._skip = 0
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for k in ("href", "src"):
            if a.get(k): self.refs.append(a[k])
        if tag == "img" and a.get("src") and a.get("loading") != "lazy": self.eager.append(a["src"])
        if tag in ("script", "style"): self._skip += 1
    def handle_endtag(self, tag):
        if tag in ("script", "style"): self._skip -= 1
    def handle_data(self, d):
        if not self._skip: self.text.append(d)

# I3: Bilder klein und ohne GPS
try:
    from PIL import Image
except ImportError:
    Image = None
for img in DIST.rglob("*.jpg"):
    size = img.stat().st_size
    if size > 300_000: err("I3", f"{img.relative_to(DIST)} ist {size // 1000} KB (max. 300)")
    if Image:
        exif = Image.open(img).getexif()
        if exif.get(0x8825): err("I3", f"{img.relative_to(DIST)} enthält GPS-Daten")

# I6: keine geheimen Links oder persönlichen Daten
FORBIDDEN = [r"ical\.booking\.com", r"airbnb\.[a-z.]+/calendar/ical", r"calendar\.google\.com/calendar/ical"]  # Firmen-OIB im Impressum ist Pflicht und erlaubt
tok = os.environ.get("ICAL_EXPORT_TOKEN", "").strip()
for f in DIST.rglob("*"):
    if not f.is_file() or f.suffix not in (".html", ".js", ".json", ".css", ".txt", ".xml"): continue
    t = f.read_text("utf-8", "ignore")
    for pat in FORBIDDEN:
        if re.search(pat, t): err("I6", f"{f.relative_to(DIST)} enthält {pat}")
    if tok and tok in t: err("I6", f"{f.relative_to(DIST)} enthält den Export-Token")

# I1/I5/I8: Platzhalter, tote interne Links, Ladegröße
for page in DIST.rglob("*.html"):
    p = Links(); html = page.read_text("utf-8"); p.feed(html)
    text = " ".join(p.text)
    m = re.search(r"\{[a-z_]+\}", text)
    if m: err("I1", f"{page.relative_to(DIST)}: offener Platzhalter {m.group(0)}")
    for ref in p.refs:
        u = urlparse(ref)
        if u.scheme or ref.startswith(("#", "mailto:", "tel:", "//")): continue
        base = DIST if u.path.startswith("/") else page.parent
        target = (base / u.path.lstrip("/")).resolve() if u.path else page
        if target.is_dir(): target = target / "index.html"
        if not target.exists(): err("I5", f"{page.relative_to(DIST)}: Link ins Leere {ref}")
    if page.name == "index.html" and page.parent != DIST:
        total = len(html.encode())
        for src in p.eager + [r for r in p.refs if r.split("?")[0].endswith((".css", ".js"))]:
            f = (page.parent / urlparse(src).path).resolve()
            if f.exists(): total += f.stat().st_size
        if total > 1_500_000: err("I8", f"{page.relative_to(DIST)} lädt {total // 1000} KB (max. 1500)")

# I4: KI-Bilder gekennzeichnet, Fremdbilder mit Nachweis
places = json.loads((ROOT / "content/things-to-do.json").read_text("utf-8"))
items = places.get("places", places) if isinstance(places, dict) else places
ai = sum(1 for x in items if isinstance(x, dict) and (x.get("photo") or {}).get("ai"))
credited = sum(1 for x in items if isinstance(x, dict) and (x.get("photo") or {}).get("credit"))
ui = json.loads((ROOT / "content/ui.json").read_text("utf-8"))
for lang in ui:
    f = DIST / lang / "things-to-do.html"
    if not f.exists():
        cands = list((DIST / lang).glob("*things*.html")) or list(DIST.glob(f"*things*{lang}*.html"))
        f = cands[0] if cands else None
    if not f: continue
    t = f.read_text("utf-8")
    n_ai = t.count(ui[lang]["symbol_img"]) 
    n_cr = len(re.findall(r'class="credit"', t))
    if n_ai < ai: err("I4", f"{lang}: {n_ai} von {ai} KI-Bildern als Symbolbild gekennzeichnet")
    if n_cr < credited: err("I4", f"{lang}: {n_cr} von {credited} Fremdbildern mit Bildnachweis")

if errors:
    print("\n".join(errors)); print(f"{len(errors)} Fehler"); sys.exit(1)
print("dist checks ok")
