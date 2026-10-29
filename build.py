#!/usr/bin/env python3
"""Converts the .docx files in ./docs into HTML fragments in ./public/content.
Run:  pip install lxml  &&  python build.py   (only needed when you edit the Word files)"""
import zipfile, re, json, html, shutil
from pathlib import Path
from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ns = {"w": W}
q = lambda t: "{%s}%s" % (W, t)
ROOT = Path(__file__).parent
OUT = ROOT / "public" / "content"

DOCS = [  # slug, file, short title, blurb
 ("guide", "C_and_Embedded_C_Complete_Study_Guide", "Complete Study Guide", "Full theory with code, from basics to embedded C"),
 ("cheatsheet", "C_and_Embedded_C_Interview_Cheat_Sheet", "Interview Cheat Sheet", "One-line answers for the night before"),
 ("datatypes", "Data_Types_in_C_with_int_Explained", "Data Types in C", "Sizes, ranges, int in depth"),
 ("plan", "C_and_Embedded_C_Study_Plan", "Study Plan", "Day-by-day calendar, 30 Oct to 30 Nov"),
]

def esc(s): return html.escape(s, quote=False)
def slugify(s): return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60] or "section"

class Doc:
    def __init__(self, path):
        z = zipfile.ZipFile(path)
        self.body = etree.fromstring(z.read("word/document.xml")).find("w:body", ns)
        self.numfmt = {}
        if "word/numbering.xml" in z.namelist():
            n = etree.fromstring(z.read("word/numbering.xml"))
            absfmt = {a.get(q("abstractNumId")): {l.get(q("ilvl")): l.find("w:numFmt", ns).get(q("val")) for l in a.findall("w:lvl", ns)}
                      for a in n.findall("w:abstractNum", ns)}
            for m in n.findall("w:num", ns):
                self.numfmt[m.get(q("numId"))] = absfmt.get(m.find("w:abstractNumId", ns).get(q("val")), {})
        self.ids, self.sections = {}, []

    def uid(self, text):
        s = slugify(text); n = self.ids.get(s, 0); self.ids[s] = n + 1
        return s if n == 0 else f"{s}-{n+1}"

    def runs(self, p):
        out = []
        for r in p.iter(q("r")):
            t = ""
            for c in r:
                if c.tag == q("t"): t += c.text or ""
                elif c.tag == q("tab"): t += "    "
                elif c.tag == q("br") and c.get(q("type")) != "page": t += "\n"
            if not t: continue
            h = esc(t).replace("\n", "<br>")
            rp = r.find("w:rPr", ns)
            if rp is not None:
                f = rp.find("w:rFonts", ns)
                if f is not None and f.get(q("ascii")) == "Consolas": h = f"<code>{h}</code>"
                if rp.find("w:b", ns) is not None: h = f"<strong>{h}</strong>"
                if rp.find("w:i", ns) is not None: h = f"<em>{h}</em>"
            out.append(h)
        s = "".join(out)
        return s.replace("</code><code>", "").replace("</strong><strong>", "").replace("</em><em>", "")

    def raw(self, p):
        return "".join((t.text or "") for t in p.iter(q("t"))) if p.find(".//w:tab", ns) is None else \
               "".join((c.text or "") if c.tag == q("t") else "    " for c in p.iter() if c.tag in (q("t"), q("tab")))

    def blocks(self, elems):
        h, stack = [], []  # stack of (tag, ilvl)
        def close(to=-1):
            while stack and stack[-1][1] > to: h.append(f"</{stack.pop()[0]}>")
        elems = list(elems); k = 0
        while k < len(elems):
            e = elems[k]; k += 1
            if e.tag == q("tbl"): close(); h.append(self.table(e)); continue
            if e.tag != q("p"): continue
            if is_code_p(e):
                close(); lines = [self.raw(e)]
                while k < len(elems) and elems[k].tag == q("p") and is_code_p(elems[k]): lines.append(self.raw(elems[k])); k += 1
                code = "\n".join(lines).strip("\n").rstrip()
                if self.sections: self.sections[-1]["text"] += " " + code
                h.append(f'<pre class="code"><code>{esc(code)}</code></pre>'); continue
            st = e.find("w:pPr/w:pStyle", ns); st = st.get(q("val")) if st is not None else ""
            num = e.find("w:pPr/w:numPr", ns)
            if num is not None:
                lv = int(num.find("w:ilvl", ns).get(q("val"))); nid = num.find("w:numId", ns).get(q("val"))
                tag = "ol" if self.numfmt.get(nid, {}).get(str(lv)) == "decimal" else "ul"
                close(lv)
                if not stack or stack[-1][1] < lv: h.append(f"<{tag}>"); stack.append((tag, lv))
                h.append(f"<li>{self.runs(e)}</li>"); continue
            close()
            txt = self.runs(e)
            if not self.raw(e).strip():
                continue
            if st in ("Heading1", "Heading2"):
                lvl = int(st[-1]); plain = self.raw(e).strip(); i = self.uid(plain)
                self.sections.append({"id": i, "title": plain, "lvl": lvl, "text": ""})
                h.append(f'<h{lvl} id="{i}">{re.sub("</?strong>", "", txt)}</h{lvl}>')
            else:
                h.append(f"<p>{txt}</p>")
                if self.sections: self.sections[-1]["text"] += " " + self.raw(e)
        close()
        return "\n".join(h)

    def table(self, t):
        rows = t.findall("w:tr", ns); cells = rows[0].findall("w:tc", ns)
        def fill(tc):
            s = tc.find("w:tcPr/w:shd", ns); return s.get(q("fill")) if s is not None else None
        if len(rows) == 1 and len(cells) == 1:
            tc = cells[0]; f = fill(tc); ps = tc.findall("w:p", ns)
            if f == "F3F3F3":
                code = "\n".join(self.raw(p) for p in ps).rstrip()
                if self.sections: self.sections[-1]["text"] += " " + code
                return f'<pre class="code"><code>{esc(code)}</code></pre>'
            b = tc.find("w:tcPr/w:tcBorders/w:left", ns)
            col = "#" + b.get(q("color")) if b is not None and b.get(q("color")) not in (None, "auto") else "#2A7F8E"
            kind = "warn" if f == "FDECEA" else "info"
            inner = self.blocks(list(tc))
            if self.sections: self.sections[-1]["text"] += " " + re.sub("<[^>]+>", " ", inner)
            return f'<aside class="callout {kind}" style="--c:{col}">{inner}</aside>'
        hdr = fill(cells[0]) == "1F3A5F"
        out = ['<div class="tablewrap"><table>']
        for ri, tr in enumerate(rows):
            tag = "th" if hdr and ri == 0 else "td"
            out.append("<tr>" + "".join(f"<{tag}>{self.cell(tc)}</{tag}>" for tc in tr.findall("w:tc", ns)) + "</tr>")
        out.append("</table></div>")
        s = "\n".join(out)
        if self.sections: self.sections[-1]["text"] += " " + re.sub("<[^>]+>", " ", s)
        return s

    def cell(self, tc):
        ps = tc.findall("w:p", ns)
        if fill_is_code(tc) and len(ps) >= 1 and all(p.find(".//w:rFonts[@w:ascii='Consolas']", ns) is not None for p in ps if self.raw(p).strip()):
            return f'<pre class="code mini"><code>{esc(chr(10).join(self.raw(p) for p in ps).rstrip())}</code></pre>'
        inner = self.blocks(list(tc))
        return re.sub(r"^<p>(.*)</p>$", r"\1", inner, flags=re.S) if inner.count("<p>") == 1 and "<ul>" not in inner else inner

def is_code_p(p):
    s = p.find("w:pPr/w:shd", ns); return s is not None and s.get(q("fill")) == "F3F3F3"

def fill_is_code(tc):
    s = tc.find("w:tcPr/w:shd", ns); return s is not None and s.get(q("fill")) == "F3F3F3"

def convert(path):
    d = Doc(path); kids = list(d.body); head, i = [], 0
    while i < len(kids) and kids[i].tag == q("p") and kids[i].find("w:pPr/w:pStyle", ns) is None and kids[i].find("w:pPr/w:numPr", ns) is None:
        if d.raw(kids[i]).strip(): head.append(esc(d.raw(kids[i]).strip()))
        i += 1
    cls = ["title", "subtitle", "meta", "meta"]
    header = '<header class="doc-head">' + "".join(f'<p class="{cls[min(n,3)]}">{t}</p>' for n, t in enumerate(head)) + "</header>"
    return header + d.blocks(kids[i:]), d.sections

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True); (ROOT / "public/downloads").mkdir(exist_ok=True)
    manifest, index, pages = [], [], {}
    for slug, fn, title, blurb in DOCS:
        frag, secs = convert(ROOT / "docs" / f"{fn}.docx")
        (OUT / f"{slug}.html").write_text(frag, encoding="utf8"); pages[slug] = frag
        shutil.copy(ROOT / "docs" / f"{fn}.docx", ROOT / "public/downloads" / f"{fn}.docx")
        manifest.append({"slug": slug, "title": title, "blurb": blurb, "docx": f"downloads/{fn}.docx"})
        index += [{"doc": slug, "id": s["id"], "title": s["title"], "text": re.sub(r"\s+", " ", s["text"]).strip()[:4000]} for s in secs]
        print(f"{slug}: {len(frag)//1024} KB, {len(secs)} sections")
    (OUT / "docs.json").write_text(json.dumps(manifest), encoding="utf8")
    data = json.dumps({"docs": manifest, "index": index, "pages": pages}, ensure_ascii=False).replace("</", "<\\/")
    (ROOT / "public" / "data.js").write_text("window.NOTES=" + data + ";", encoding="utf8")
    (OUT / "search.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf8")
