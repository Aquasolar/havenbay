#!/usr/bin/env python3
"""Baut die statische Website von Haven Bay nach dist/.

Aufruf:
  python build.py --availability build/availability.json          # Produktion
  python build.py --draft --availability content/availability.sample.json   # Entwurf zur Ansicht

Alle Texte stehen in content/, das Aussehen in site/assets/. Der Generator nutzt nur die
Python-Standardbibliothek.
"""
import argparse
import datetime as dt
import hashlib
import html
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PAGES = ["index", "studio", "apartment", "things-to-do", "legal"]
UNITS = ["studio", "apartment"]
CURRENCY_SYMBOLS = {"EUR": "€"}
DRAFT_BANNER = "Entwurf zur Ansicht: Preise, Verfügbarkeit und Kontaktdaten sind Platzhalter. Es wird nichts gesendet."
DEMO_MESSAGE = "Demo: Die Anfrage wurde nicht gesendet."

esc = html.escape


def load_json(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def attr_json(obj):
    """JSON für <script type=application/json>, ohne </script>-Ausbruch."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


# --------------------------------------------------------------------------- Daten
class Site:
    def __init__(self, draft):
        self.draft = draft
        self.cfg = load_json("config.json")
        self.ui = load_json("content/ui.json")
        self.units = load_json("content/units.json")
        self.prices = load_json("content/prices.json")
        self.guest = load_json("content/guest.json")
        self.daily = {}
        self.things = load_json("content/things-to-do.json")
        self.legal = load_json("content/legal.json")
        self.langs = self.cfg["languages"]
        self.today = dt.date.today()
        self.currency = CURRENCY_SYMBOLS.get(self.prices.get("currency", "EUR"), "€")
        v = hashlib.sha1()
        for name in ("style.css", "app.js"):
            v.update((ROOT / "site/assets" / name).read_bytes())
        self.version = v.hexdigest()[:8]

    def text(self, lang, key):
        return self.ui.get(lang, {}).get(key) or self.ui["en"][key]

    def ui_for(self, lang):
        merged = dict(self.ui["en"])
        merged.update(self.ui.get(lang, {}))
        return merged

    def validate(self):
        problems = []
        c = self.cfg
        if not c.get("contact_email"):
            problems.append("config.json: contact_email fehlt")
        if not c.get("form_endpoint") and not c.get("contact_email"):
            problems.append("config.json: weder form_endpoint noch contact_email gesetzt, Anfragen könnten nicht ankommen")
        for key in ("director",):
            if not c["operator"].get(key):
                problems.append(f"config.json: operator.{key} fehlt (Impressum)")
        if not self.prices.get("confirmed"):
            problems.append("content/prices.json: Preise sind nicht bestätigt (confirmed=false)")
        for lang in self.langs:
            missing = [k for k in self.ui["en"] if k not in self.ui.get(lang, {})]
            if missing:
                problems.append(f"content/ui.json: {lang} fehlen Schlüssel: {', '.join(missing)}")
        return problems


# --------------------------------------------------------------------------- Bausteine
def page_href(page):
    return "./" if page == "index" else f"{page}.html"


def lang_href(lang, page):
    return f"../{lang}/" if page == "index" else f"../{lang}/{page}.html"


def head(site, lang, page, title, desc, noindex=False):
    base = site.cfg["base_url"].rstrip("/")
    alts = []
    for l in site.langs:
        path = f"{l}/" if page == "index" else f"{l}/{page}.html"
        alts.append(f'<link rel="alternate" hreflang="{l}" href="{base}/{path}">')
    default = site.cfg["default_language"]
    path = f"{default}/" if page == "index" else f"{default}/{page}.html"
    alts.append(f'<link rel="alternate" hreflang="x-default" href="{base}/{path}">')
    self_path = f"{lang}/" if page == "index" else f"{lang}/{page}.html"
    robots = '<meta name="robots" content="noindex, nofollow">\n' if (site.draft or noindex) else ""
    if noindex:
        alts = []
    icon = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
            "%3Crect width='32' height='32' rx='7' fill='%230f3f4a'/%3E%3Ccircle cx='16' cy='16' r='6' fill='%23f08a24'/%3E%3C/svg%3E")
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
{robots}<link rel="canonical" href="{base}/{self_path}">
{chr(10).join(alts)}
<link rel="icon" href="{icon}">
<link rel="stylesheet" href="../assets/style.css?v={site.version}">
</head>"""


def header(site, lang, page, ui):
    names = site.cfg["language_names"]
    items = []
    for l in site.langs:
        cur = ' aria-current="true"' if l == lang else ""
        items.append(f'<li><a href="{lang_href(l, page)}" hreflang="{l}" lang="{l}"{cur}>{esc(names[l])}</a></li>')
    nav = [
        ("index", ui["nav_home"]),
        ("studio", ui["nav_studio"]),
        ("apartment", ui["nav_apartment"]),
        ("things-to-do", ui["nav_things"]),
    ]
    links = []
    for p, label in nav:
        cur = ' aria-current="page"' if p == page else ""
        links.append(f'<a href="{page_href(p)}"{cur}>{esc(label)}</a>')
    links.append(f'<a href="{page_href("index")}#contact">{esc(ui["nav_contact"])}</a>')
    banner = f'<div class="draft-banner" role="note">{esc(DRAFT_BANNER)}</div>\n' if site.draft else ""
    return f"""<body class="{'is-home' if page == 'index' else 'is-sub'}">
{banner}<a class="skip" href="#main">{esc(ui["skip"])}</a>
<header class="site-header">
<div class="wrap">
<a class="brand" href="./">Haven Bay<small>Apartments</small></a>
<button class="menu-btn" type="button" aria-expanded="false" aria-controls="nav">{esc(ui["menu"])}</button>
<nav class="nav" id="nav" aria-label="{esc(ui["menu"])}">
{chr(10).join(links)}
<a class="btn btn-small" href="{page_href('index')}#booking">{esc(ui["nav_book"])}</a>
</nav>
<details class="lang"><summary aria-label="{esc(ui["lang_label"])}">{lang.upper()}</summary><ul>{''.join(items)}</ul></details>
</div>
</header>"""


def footer(site, lang, ui):
    op = site.cfg["operator"]
    mail = site.cfg.get("contact_email")
    contact = f'<p><a href="mailto:{esc(mail)}">{esc(mail)}</a></p>' if mail else ""
    return f"""<footer class="site-footer">
<div class="wrap footer-grid">
<div>
<p><strong>Haven Bay Apartments</strong></p>
<p>{esc(site.cfg.get("property_address", ""))}</p>
<p>{esc(ui["footer_op"])}, {esc(op["address"])}</p>
{contact}
</div>
<div class="footer-links">
<a href="legal.html">{esc(ui["legal"])}</a>
<a href="legal.html#privacy">{esc(ui["privacy"])}</a>
</div>
</div>
</footer>"""


def img_slot(src, alt="", cls="ph", eager=False):
    loading = "" if eager else ' loading="lazy"'
    return (f'<div class="{cls}"><img src="{esc(src)}" alt="{esc(alt)}"{loading} '
            f'onerror="this.remove()"></div>')


def hero(site, lang, ui, image, h1, p="", sub=False):
    cls = "hero hero-sub" if sub else "hero"
    para = f"<p>{esc(p)}</p>" if p else ""
    return f"""<section class="{cls}">
{img_slot(f"../assets/img/{image}", eager=True)}
<div class="wrap hero-inner">
<h1>{esc(h1)}</h1>
{para}
</div>
</section>"""


def booking_section(site, lang, ui, default_unit, with_price_table=False):
    opts = "".join(
        f'<option value="{u}"{" selected" if u == default_unit else ""}>{esc(ui[u + "_name"])}</option>'
        for u in UNITS
    )
    nights_label = ui["nights"]["other"].replace("{n}", "").strip().capitalize()
    return f"""<section class="section booking" id="booking" aria-labelledby="book-h">
<div class="wrap">
<h2 id="book-h">{esc(ui["book_h"])}</h2>
<p class="muted">{esc(ui["direct_note"])}</p>
<div class="booking-grid">
<div class="cal-card">
<div id="cal"></div>
<ul class="cal-legend">
<li><span></span>{esc(ui["legend_free"])}</li>
<li><span class="lg-booked"></span>{esc(ui["legend_booked"])}</li>
<li><span class="lg-sel"></span>{esc(ui["legend_sel"])}</li>
</ul>
<p id="cal-status" class="cal-status" role="status"></p>
</div>
<div class="summary">
<div class="form">
<div><label for="unit">{esc(ui["f_unit"])}</label><select id="unit" class="field">{opts}</select></div>
<div><label for="guests">{esc(ui["f_guests"])}</label><select id="guests" class="field"></select></div>
</div>
<dl style="margin-top:1rem">
<dt>{esc(ui["f_in"])}</dt><dd id="sum-in">&ndash;</dd>
<dt>{esc(ui["f_out"])}</dt><dd id="sum-out">&ndash;</dd>
<dt>{esc(nights_label)}</dt><dd id="sum-nights">&ndash;</dd>
<dt>{esc(ui["est_label"])}</dt><dd id="sum-total" class="total">&ndash;</dd>
</dl>
<p id="sum-hint" class="hint" role="status"></p>
<button id="btn-clear" class="btn btn-ghost btn-small" type="button" hidden>{esc(ui["clear_dates"])}</button>
<form id="request-form" class="form">
<h3>{esc(ui["form_h"])}</h3>
<div><label for="f-name">{esc(ui["f_name"])}</label><input id="f-name" name="name" class="field" required autocomplete="name"></div>
<div><label for="f-email">{esc(ui["f_email"])}</label><input id="f-email" name="email" type="email" class="field" required autocomplete="email"></div>
<div><label for="f-phone">{esc(ui["f_phone"])}</label><input id="f-phone" name="phone" type="tel" class="field" autocomplete="tel"></div>
<div><label for="f-msg">{esc(ui["f_msg"])}</label><textarea id="f-msg" name="message" class="field"></textarea></div>
<div class="hp" aria-hidden="true"><label>Website<input name="website" tabindex="-1" autocomplete="off"></label></div>
<label class="consent"><input type="checkbox" name="consent" required><span>{esc(ui["f_consent"])} <a href="legal.html#privacy">{esc(ui["privacy"])}</a></span></label>
<button id="btn-send" class="btn" type="submit" disabled>{esc(ui["btn_send"])}</button>
<p id="form-msg" class="form-msg" role="status"></p>
</form>
</div>
</div>
</div>
</section>"""


def page_data(site, lang, ui):
    units = {}
    for u in UNITS:
        cfg = site.units[u]
        pr = site.prices["units"][u]
        units[u] = {
            "min_stay": cfg["min_stay"],
            "max_guests": cfg["max_guests"],
            "nightly": pr["nightly"],
            "monthly": pr["monthly"],
            "weekly": pr.get("weekly"),
            "rules": site.prices.get("rules", {}),
        }
    data = {
        "lang": lang,
        "ui": ui,
        "units": units,
        "currency_symbol": site.currency,
        "availability_url": "../availability.json",
        "daily_url": "../daily-prices.json",
        "endpoint": site.cfg.get("form_endpoint", ""),
        "contact_email": site.cfg.get("contact_email", ""),
        "demo": bool(site.draft),
        "demo_message": DEMO_MESSAGE,
    }
    return f'<script id="hb-data" type="application/json">{attr_json(data)}</script>'


def tail(site, lang, ui, with_data=True):
    data = page_data(site, lang, ui) if with_data else ""
    return f"""{footer(site, lang, ui)}
{data}
<script src="../assets/app.js?v={site.version}" defer></script>
</body>
</html>
"""


# --------------------------------------------------------------------------- Seiten
def current_nightly(site, unit):
    from datetime import date
    today = date.today()
    d = site.daily.get("units", {}).get(unit, {}).get(today.isoformat())
    if isinstance(d, (int, float)):
        return d
    v = site.prices["units"][unit]["nightly"].get(str(today.month))
    return v if isinstance(v, (int, float)) else None


def rates_section(site, ui):
    cards = []
    for u in UNITS:
        now = current_nightly(site, u)
        now_t = f'{site.currency} {now}' if now is not None else esc(ui["on_request"])
        per = f' <span>{esc(ui["per_night"])}</span>' if now is not None else ""
        cards.append(f"""<article class="rate">
<h3>{esc(ui[u + "_name"])}</h3>
<p class="rate-label">{esc(ui["rate_now"])}</p>
<p class="rate-price">{now_t}{per}</p>
<p class="rate-label">{esc(ui["monthly_h"])}</p>
<p class="rate-price">{esc(monthly_text(site, ui, u))}</p>
</article>""")
    return f"""<section class="section-tight rates" aria-labelledby="rates-h">
<div class="wrap">
<h2 id="rates-h">{esc(ui["rates_h"])}</h2>
<p class="muted">{esc(ui["monthly_p"])} {esc(ui["direct_note"])}</p>
<div class="rate-grid">{''.join(cards)}</div>
<p class="muted">{fees_text(site, ui)}</p>
<p class="muted">{esc(ui["pay_p"])}</p>
<p class="muted">{esc(ui["cancel_p"])}</p>
<a class="btn" href="#booking">{esc(ui["btn_check"])}</a>
</div>
</section>"""


def page_index(site, lang):
    ui = site.ui_for(lang)
    opts = "".join(f'<option value="{u}">{esc(ui[u + "_name"])}</option>' for u in UNITS)
    max_g = max(site.units[u]["max_guests"] for u in UNITS)
    gopts = "".join(f"<option>{i}</option>" for i in range(1, max_g + 1))
    rows = []
    for u in UNITS:
        cfg = site.units[u]
        rows.append(f"""<article class="unit-row">
{img_slot(f"../assets/img/{cfg['hero']}", ui[u + '_name'], 'ph unit-photo')}
<div>
<h3>{esc(ui[u + "_name"])}</h3>
<p>{esc(ui[u + "_short"])}</p>
{amenity_list(ui, cfg)}
<a class="btn btn-ghost" href="{u}.html">{esc(ui["unit_more"])}</a>
</div>
</article>""")
    mail = site.cfg.get("contact_email")
    phone = site.cfg.get("contact_phone")
    contact_lines = []
    if mail:
        contact_lines.append(f'<p><a href="mailto:{esc(mail)}">{esc(mail)}</a></p>')
    if phone:
        contact_lines.append(f'<p><a href="tel:{esc(phone.replace(" ", ""))}">{esc(phone)}</a></p>')
    if not contact_lines and site.draft:
        contact_lines.append('<p><span class="todo">[E-Mail und Telefon ergänzen]</span></p>')
    body = f"""{head(site, lang, "index", "Haven Bay Apartments, Rogotin, Neretva Delta", ui["hero_p"])}
{header(site, lang, "index", ui)}
<main id="main">
{hero(site, lang, ui, "hero-bay.jpg", ui["hero_h"], ui["hero_p"])}
{rates_section(site, ui)}
<section class="section" aria-labelledby="units-h">
<div class="wrap">
<h2 id="units-h">{esc(ui["units_h"])}</h2>
{''.join(rows)}
</div>
</section>
{booking_section(site, lang, ui, "studio")}
<section class="section" aria-labelledby="loc-h">
<div class="wrap two-col">
<div>
<h2 id="loc-h">{esc(ui["loc_h"])}</h2>
<p>{esc(ui["loc_p"])}</p>
<a class="btn btn-ghost" href="things-to-do.html">{esc(ui["things_h"])}</a>
</div>
{img_slot("../assets/img/bay-2.jpg", "", "ph unit-photo")}
</div>
</section>
<section class="section-tight" id="contact" aria-labelledby="contact-h">
<div class="wrap">
<h2 id="contact-h">{esc(ui["contact_h"])}</h2>
<p>{esc(ui["contact_p"])}</p>
{''.join(contact_lines)}
<p class="muted">{esc(site.cfg.get("property_address", ""))}</p>
</div>
</section>
</main>
{tail(site, lang, ui)}"""
    return body


def amenity_list(ui, cfg):
    items = "".join(f"<li>{esc(ui['a_' + a])}</li>" for a in cfg["amenities"])
    return f'<ul class="amen">{items}</ul>'


def fees_text(site, ui):
    r = site.prices.get("rules")
    if not r:
        return ""
    c = site.currency
    return esc(ui["fees_p"].format(c=f'{c} {r["cleaning_fee"]}', e=f'{c} {r["extra_guest_fee"]}',
               w=r["weekly_discount_winter"], s=r["weekly_discount_season"], n=r["winter_min_nights"])
               + (" " + ui["fees_monthly"].format(m=f'{c} {r["extra_guest_monthly"]}') if r.get("extra_guest_monthly") is not None else "")
               + (" " + ui["fees_pet"].format(p=f'{c} {r["pet_fee"]}') if r.get("pet_fee") is not None else ""))


def monthly_text(site, ui, unit):
    m = site.prices["units"][unit]["monthly"]
    if isinstance(m.get("price"), (int, float)):
        return f'{site.currency} {m["price"]} {ui["per_month"]}'
    return ui["on_request"]


def page_unit(site, lang, unit):
    ui = site.ui_for(lang)
    cfg = site.units[unit]
    gallery = "".join(img_slot(f"../assets/img/{p}", ui[unit + "_name"]) for p in cfg["photos"])
    title = f'{ui[unit + "_name"]} | Haven Bay Apartments'
    return f"""{head(site, lang, unit, title, ui[unit + "_short"])}
{header(site, lang, unit, ui)}
<main id="main">
{hero(site, lang, ui, cfg["hero"], ui[unit + "_name"], sub=True)}
<section class="section" aria-labelledby="amen-h">
<div class="wrap">
<p style="font-size:var(--step-1);max-width:46ch">{esc(ui[unit + "_short"])}</p>
<h2 id="amen-h">{esc(ui["amen_h"])}</h2>
{amenity_list(ui, cfg)}
<h2>{esc(ui["gal_h"])}</h2>
<div class="gallery">{gallery}</div>
</div>
</section>
<section class="section-tight" aria-labelledby="price-h">
<div class="wrap two-col">
<div>
<h2 id="price-h">{esc(ui["price_h"])}</h2>
<div id="price-table"></div>
</div>
<div class="panel">
<h3>{esc(ui["monthly_h"])}</h3>
<p>{esc(ui["monthly_p"])}</p>
<p><strong>{esc(monthly_text(site, ui, unit))}</strong></p>
<p class="muted">{fees_text(site, ui)}</p>
<p class="muted">{esc(ui["pay_p"])}</p>
<p class="muted">{esc(ui["cancel_p"])}</p>
</div>
</div>
</section>
{booking_section(site, lang, ui, unit)}
</main>
{tail(site, lang, ui)}"""


def photo_credit(p, ui=None):
    ph = p.get("photo")
    if not ph:
        return ""
    if ph.get("ai"):
        return f'<span class="credit">{esc((ui or {}).get("symbol_img", "Illustrative image"))}</span>'
    return (f'<a class="credit" href="{esc(ph["src"])}" target="_blank" rel="noopener license">'
            f'Foto: {esc(ph["credit"])}</a>')


def place_card(site, lang, ui, p, badge=""):
    desc = p["t"].get(lang) or p["t"].get("en", "")
    links = []
    if p.get("map"):
        links.append(f'<a href="{esc(p["map"])}" target="_blank" rel="noopener">{esc(ui["open_map"])}</a>')
    if p.get("url"):
        links.append(f'<a href="{esc(p["url"])}" target="_blank" rel="noopener">{esc(ui["website"])}</a>')
    if p.get("phone"):
        tel = p["phone"].replace(" ", "")
        links.append(f'<a href="tel:{esc(tel)}">{esc(p["phone"])}</a>')
    badge_html = f'<span class="badge">{esc(badge)}</span>' if badge else ""
    return f"""<article class="place" id="{esc(p['id'])}">
{img_slot(f"../assets/img/todo/{p['id']}.jpg", alt=p['name']) if (ROOT / "site/assets/img/todo" / f"{p['id']}.jpg").exists() else '<div class="ph"></div>'}{photo_credit(p, ui) if (ROOT / "site/assets/img/todo" / f"{p['id']}.jpg").exists() else ""}
<div class="place-body">
{badge_html}<h3>{esc(p['name'])}</h3>
<p>{esc(desc)}</p>
<div class="place-links">{''.join(links)}</div>
</div>
</article>"""


def next_annual(today, month, day):
    cand = dt.date(today.year, month, day)
    if cand < today:
        cand = dt.date(today.year + 1, month, day)
    return cand


def whats_on(site, lang, ui):
    """Einträge für das Karussell 'Aktuell'."""
    today = site.today
    cards = []
    for p in site.things["places"]:
        if not p.get("featured"):
            continue
        badge = ""
        if p.get("season") and today.month not in p["season"]:
            continue
        if p.get("ends"):
            end = dt.date.fromisoformat(p["ends"])
            if end < today:
                continue
            badge = ui["until"].replace("{d}", end.strftime("%d.%m.%Y"))
        if p.get("annual"):
            nxt = next_annual(today, p["annual"]["month"], p["annual"]["day"])
            if (nxt - today).days > 60:
                continue
            badge = nxt.strftime("%d.%m.%Y")
        cards.append(place_card(site, lang, ui, p, badge))
    for post in sorted(site.things.get("posts", []), key=lambda x: x.get("date", ""), reverse=True):
        if post.get("date") and dt.date.fromisoformat(post["date"]) > today:
            continue
        if post.get("ends") and dt.date.fromisoformat(post["ends"]) < today:
            continue
        item = {
            "id": post["id"],
            "name": (post.get("title") or {}).get(lang) or (post.get("title") or {}).get("en", ""),
            "t": post.get("text", {}),
            "url": post.get("url"),
            "map": post.get("map"),
        }
        cards.append(place_card(site, lang, ui, item, post.get("date", "")))
    return cards


def page_things(site, lang):
    ui = site.ui_for(lang)
    cats = site.things["categories"]
    chips = [f'<button class="chip" type="button" data-cat="all" aria-pressed="true">{esc(ui["cat_all"])}</button>']
    chips += [f'<button class="chip" type="button" data-cat="{c}" aria-pressed="false">{esc(ui["cat_" + c])}</button>' for c in cats]
    sections = []
    for c in cats:
        cards = "".join(place_card(site, lang, ui, p) for p in site.things["places"] if p["cat"] == c)
        sections.append(f"""<section class="cat-section" data-cat="{c}" aria-labelledby="cat-{c}">
<h2 id="cat-{c}">{esc(ui["cat_" + c])}</h2>
<div class="places">{cards}</div>
</section>""")
    now = whats_on(site, lang, ui)
    carousel = ""
    if now:
        carousel = f"""<section class="section-tight" aria-labelledby="now-h">
<div class="wrap carousel">
<h2 id="now-h">{esc(ui["now_h"])}</h2>
<div class="carousel-track" tabindex="0">{''.join(now)}</div>
<div class="carousel-ctl">
<button class="cal-nav" type="button" data-dir="-1" aria-label="{esc(ui["cal_prev"])}">&lsaquo;</button>
<button class="cal-nav" type="button" data-dir="1" aria-label="{esc(ui["cal_next"])}">&rsaquo;</button>
</div>
</div>
</section>"""
    return f"""{head(site, lang, "things-to-do", ui["things_h"] + " | Haven Bay Apartments", ui["things_p"])}
{header(site, lang, "things-to-do", ui)}
<main id="main">
{hero(site, lang, ui, "hero-bay.jpg", ui["things_h"], ui["things_p"], sub=True)}
{carousel}
<section class="section-tight">
<div class="wrap">
<div class="chips" role="group" aria-label="{esc(ui["things_h"])}">{''.join(chips)}</div>
{''.join(sections)}
</div>
</section>
</main>
{tail(site, lang, ui, with_data=False)}"""


def page_guest(site, lang, root=False):
    g = site.guest
    t = g["t"].get(lang) or g["t"]["en"]
    names = site.cfg["language_names"]
    items = "".join(
        f'<li><a href="{lang_href(l, "guest")}" hreflang="{l}" lang="{l}"{" aria-current=\"true\"" if l == lang else ""}>{esc(names[l])}</a></li>'
        for l in site.langs)
    banner = f'<div class="draft-banner" role="note">{esc(DRAFT_BANNER)}</div>\n' if site.draft else ""

    def ul(lst):
        return "<ul>" + "".join(f"<li>{esc(x)}</li>" for x in lst) + "</ul>"

    steps = "<ol>" + "".join(f"<li>{esc(x)}</li>" for x in t["tv_steps"]) + "</ol>"
    emerg = "<dl class=\"pairs\">" + "".join(
        f'<dt>{esc(lbl)}</dt><dd><a href="tel:{num}">{num}</a></dd>' for lbl, num in zip(t["emerg_labels"], g["emergency"])) + "</dl>"
    contacts = "<dl class=\"pairs\">" + "".join(
        f'<dt>{esc(c["name"])}</dt><dd><a href="tel:{c["phone"].replace(" ", "")}">{esc(c["phone"])}</a></dd>' for c in g["contacts"]) + "</dl>"
    tm = g["times"]
    rules = (f'<dl class="pairs"><dt>{esc(t["checkin"])}</dt><dd>{tm["checkin"]}</dd>'
             f'<dt>{esc(t["checkout"])}</dt><dd>{tm["checkout"]}</dd>'
             f'<dt>{esc(t["quiet"])}</dt><dd>{tm["quiet"]}</dd></dl>' + ul(t["rules_items"]))
    wifi = (f'<dl class="pairs wifi"><dt>{esc(t["network"])}</dt><dd><code>{esc(g["wifi"]["ssid"])}</code></dd>'
            f'<dt>{esc(t["password"])}</dt><dd><code>{esc(g["wifi"]["password"])}</code></dd></dl>')
    base = site.cfg["base_url"].rstrip("/")
    page = head(site, lang, "guest", t["title"] + " | Haven Bay", t["sub"], noindex=True)
    if root:
        page = page.replace(f'href="{base}/{lang}/guest.html"', f'href="{base}/guest/"')
    return f"""{page}
<body class="is-sub is-guest">
{banner}<header class="site-header">
<div class="wrap">
<span class="brand">Haven Bay<small>Apartments</small></span>
<details class="lang"><summary aria-label="{esc(site.ui_for(lang)["lang_label"])}">{lang.upper()}</summary><ul>{items}</ul></details>
</div>
</header>
<main id="main">
<section class="section guest">
<div class="wrap">
<h1>{esc(t["title"])}</h1>
<p class="lead">{esc(t["sub"])}</p>
<h2>{esc(t["wifi_h"])}</h2>
{wifi}
<h2>{esc(t["tv_h"])}</h2>
{steps}
<p class="muted">{esc(t["tv_note"])}</p>
<h2>{esc(t["apts_h"])}</h2>
<div class="two-lists">
<div><h3>{esc(t["studio_h"])}</h3>{ul(t["studio_items"])}</div>
<div><h3>{esc(t["apartment_h"])}</h3>{ul(t["apartment_items"])}</div>
</div>
<h2>{esc(t["house_h"])}</h2>
{ul(t["house_items"])}
<h2>{esc(t["rules_h"])}</h2>
{rules}
<h2>{esc(t["ev_h"])}</h2>
<p>{esc(t["ev_p"])}</p>
<h2>{esc(t["emerg_h"])}</h2>
{emerg}
<h2>{esc(t["contact_h"])}</h2>
{contacts}
<p class="closing">{esc(t["closing_p"])}</p>
<p><a class="btn" href="{base}/{lang}/">{esc(t["site_link"])}</a></p>
</div>
</section>
</main>
<script src="../assets/app.js?v={site.version}" defer></script>
</body>
</html>
"""


def page_legal(site, lang):
    ui = site.ui_for(lang)
    leg = site.legal.get(lang) or site.legal["en"]
    labels = leg["imprint_labels"]
    op = site.cfg["operator"]
    rows = []

    def row(key, value):
        if value:
            val = esc(value)
        elif site.draft:
            val = '<span class="todo">[ergänzen]</span>'
        else:
            return
        rows.append(f"<dt>{esc(labels[key])}</dt><dd>{val}</dd>")

    row("operator", op["name"])
    row("address", op["address"])
    row("oib", op.get("oib"))
    if op.get("register"):
        row("register", op.get("register"))
    row("director", op.get("director"))
    row("email", site.cfg.get("contact_email"))
    row("phone", site.cfg.get("contact_phone"))
    paras = "".join(f"<p>{esc(t)}</p>" for t in leg["privacy_p"])
    fallback = ""
    if lang not in site.legal:
        fallback = '<p class="muted">English version.</p>'
    return f"""{head(site, lang, "legal", leg["title"] + " | Haven Bay Apartments", leg["title"])}
{header(site, lang, "legal", ui)}
<main id="main">
<section class="section legal">
<div class="wrap">
<h1>{esc(leg["title"])}</h1>
{fallback}
<h2>{esc(leg["imprint_h"])}</h2>
<dl>{''.join(rows)}</dl>
<h2 id="privacy">{esc(leg["privacy_h"])}</h2>
{paras}
</div>
</section>
</main>
{tail(site, lang, ui, with_data=False)}"""


REDIRECT = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Haven Bay Apartments</title>
{robots}<link rel="canonical" href="{canonical}">
<script>
(function () {{
  location.replace("{default}/{target}");
}})();
</script>
<style>body{{font-family:system-ui,sans-serif;margin:3rem auto;max-width:30rem;padding:0 1rem;color:#0f3f4a}}a{{margin-right:1rem}}</style>
</head><body>
<h1>Haven Bay Apartments</h1>
<p>{links}</p>
</body></html>
"""


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build(args):
    site = Site(args.draft)
    problems = site.validate()
    if problems:
        label = "Hinweis (Entwurf)" if site.draft else "FEHLER"
        for p in problems:
            print(f"{label}: {p}", file=sys.stderr)
        if not site.draft:
            print("Produktions-Build abgebrochen. Mit --draft entsteht ein Entwurf.", file=sys.stderr)
            return 1

    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copytree(ROOT / "site/assets", out / "assets", ignore=shutil.ignore_patterns(".gitkeep"))

    if args.daily and Path(args.daily).exists():
        site.daily = json.loads(Path(args.daily).read_text(encoding="utf-8"))
        shutil.copyfile(args.daily, out / "daily-prices.json")
    else:
        write(out / "daily-prices.json", json.dumps({"units": {"studio": {}, "apartment": {}}, "events": []}))
    # Master-Preise öffentlich lesbar (für die tägliche Preisprüfung Airbnb/Booking)
    pub = {k: v for k, v in site.prices.items() if not k.startswith("_")}
    pub["source"] = "havenbay.eu – Master-Preise der Website (pro Nacht nach Monat, Monatspreis, Regeln)"
    guest = json.loads((ROOT / "content/guest.json").read_text(encoding="utf-8"))
    ops = json.loads((ROOT / "content/operations.json").read_text(encoding="utf-8"))
    for u in UNITS:
        pub["units"][u]["min_stay"] = site.units[u]["min_stay"]
        pub["units"][u]["max_guests"] = site.units[u]["max_guests"]
    pub.setdefault("policies", {})["checkin"] = guest.get("times", {}).get("checkin")
    pub["policies"]["checkout"] = guest.get("times", {}).get("checkout")
    pub["policies"]["quiet_hours"] = guest.get("times", {}).get("quiet")
    pub["policies"]["cleaning_buffer"] = {"weekdays_mon0": ops["cleaning_buffer"]["weekdays"],
        "rule": "Abreise Mo-Fr: Nacht des Abreisetags gesperrt (Reinigung)"}
    pub["rules_explained"] = {
        "min_stay": "units.<einheit>.min_stay Nächte; bei Anreise in rules.min_nights_months mindestens rules.winter_min_nights",
        "monthly": "ab 28 Nächten units.<einheit>.monthly.price je 30 Nächte (anteilig), gültig bis valid_until",
        "weekly_discount": "ab rules.weekly_from_nights Nächten: units.<einheit>.weekly[Monat der Anreise] = Endpreis für 7 Nächte, weitere Nächte anteilig (Preis/7); ohne weekly-Wert: rules.weekly_discount_winter % (Anreise in winter_months) sonst weekly_discount_season %",
        "extra_guests": "ab rules.extra_guest_from Gästen je Zusatzgast rules.extra_guest_fee pro Nacht; bei Monatsmiete pauschal rules.extra_guest_monthly pro 30 Nächte",
        "cleaning": "Reinigung ist in den Direktpreisen enthalten (rules.cleaning_included, rules.cleaning_fee = 0); alle Direktpreise sind Endpreise (Brutto)",
        "pets": "Haustiere willkommen, rules.pet_fee einmal pro Aufenthalt (nicht im Online-Richtpreis enthalten)",
        "daily_overrides": "Tagespreis ersetzt den Monatswert für diese Nacht"}
    if getattr(site, "daily", None):
        pub["daily_overrides"] = site.daily.get("units", {})
    write(out / "prices.json", json.dumps(pub, ensure_ascii=False, indent=1))
    if args.ical_dir and Path(args.ical_dir).exists():
        shutil.copytree(args.ical_dir, out / "ical")
    avail = Path(args.availability) if args.availability else None
    if avail and avail.exists():
        shutil.copyfile(avail, out / "availability.json")
    else:
        print("FEHLER: availability.json nicht gefunden (--availability).", file=sys.stderr)
        return 1

    for lang in site.langs:
        write(out / lang / "index.html", page_index(site, lang))
        for u in UNITS:
            write(out / lang / f"{u}.html", page_unit(site, lang, u))
        write(out / lang / "things-to-do.html", page_things(site, lang))
        write(out / lang / "legal.html", page_legal(site, lang))
        write(out / lang / "guest.html", page_guest(site, lang))
    write(out / "guest" / "index.html", page_guest(site, site.cfg["default_language"], root=True))

    base = site.cfg["base_url"].rstrip("/")
    robots = '<meta name="robots" content="noindex, nofollow">\n' if site.draft else ""
    names = site.cfg["language_names"]
    for target, name in (("", "index.html"), ("things-to-do.html", "things-to-do.html")):
        links = " ".join(f'<a href="{l}/{target}">{esc(names[l])}</a>' for l in site.langs)
        write(out / name, REDIRECT.format(
            robots=robots, canonical=f"{base}/{site.cfg['default_language']}/{target}",
            langs=json.dumps(site.langs), default=site.cfg["default_language"], target=target, links=links))
    write(out / "404.html", REDIRECT.format(
        robots='<meta name="robots" content="noindex">\n', canonical=base + "/", langs=json.dumps(site.langs),
        default=site.cfg["default_language"], target="", links=" ".join(f'<a href="/{l}/">{esc(names[l])}</a>' for l in site.langs)))
    (out / ".nojekyll").write_text("", encoding="utf-8")

    if site.draft:
        write(out / "robots.txt", "User-agent: *\nDisallow: /\n")
    else:
        urls = []
        for lang in site.langs:
            for page in PAGES:
                path = f"{lang}/" if page == "index" else f"{lang}/{page}.html"
                urls.append(f"<url><loc>{base}/{path}</loc></url>")
        write(out / "sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
              + "\n".join(urls) + "\n</urlset>\n")
        write(out / "robots.txt", f"User-agent: *\nAllow: /\nDisallow: /guest/\n" + "".join(f"Disallow: /{l}/guest.html\n" for l in site.langs) + f"Sitemap: {base}/sitemap.xml\n")

    print(f"OK: {len(site.langs)} Sprachen nach {out} gebaut" + (" (Entwurf)" if site.draft else ""))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist")
    ap.add_argument("--availability", default="")
    ap.add_argument("--daily", default="", help="build/daily-prices.json (optional)")
    ap.add_argument("--ical-dir", default="", help="build/ical (optional, Export für Plattformen)")
    ap.add_argument("--draft", action="store_true", help="Entwurf: Platzhalter erlaubt, noindex, keine echte Versendung")
    sys.exit(build(ap.parse_args()))
