#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""八字排盘网页界面：包装 bazi.py，不修改原程序。

运行: python web.py  然后浏览器打开 http://127.0.0.1:5000
"""
import datetime
import html
import os
import re
import subprocess
import sys

from flask import Flask, render_template_string, request
from lunar_python import LunarMonth

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)

ANSI_RE = re.compile(r"\x1b\[([0-9;]*)m")

PAGE = """<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>八字排盤</title>
<style>
  :root { --bg:#faf7f2; --fg:#2b2b2b; --card:#fff; --line:#d9d2c5; --accent:#8b3a2f; --cyan:#0b7285; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#1c1b19; --fg:#e8e4dc; --card:#262522; --line:#3c3a35; --accent:#e0866f; --cyan:#4fc3d9; }
  }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--fg);
         font-family:-apple-system,"PingFang TC","Microsoft JhengHei",sans-serif; }
  .wrap { max-width:1100px; margin:0 auto; padding:16px; }
  h1 { color:var(--accent); font-size:1.5rem; margin:8px 0 16px; }
  form { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px;
         display:grid; grid-template-columns:repeat(auto-fit,minmax(120px,1fr)); gap:12px; align-items:end; }
  label { display:flex; flex-direction:column; font-size:.85rem; gap:4px; }
  input[type=number], select { padding:8px; border:1px solid var(--line); border-radius:6px;
         background:var(--bg); color:var(--fg); font-size:1rem; width:100%; }
  .chk { flex-direction:row; align-items:center; gap:6px; }
  button { padding:10px 16px; border:0; border-radius:6px; background:var(--accent); color:#fff;
           font-size:1rem; cursor:pointer; }
  .err { color:#c0392b; margin:12px 0; white-space:pre-wrap; }
  .out { background:var(--card); border:1px solid var(--line); border-radius:10px; margin-top:16px;
         padding:12px; overflow-x:auto; }
  pre { margin:0; font-family:"Noto Sans Mono CJK TC","Noto Sans Mono CJK SC","MS Gothic",monospace;
        font-size:13px; line-height:1.5; }
  .c36 { color:var(--cyan); font-weight:bold; }
  .note { font-size:.8rem; opacity:.7; margin-top:12px; }
</style>
</head>
<body>
<div class="wrap">
  <h1>八字排盤</h1>
  <form method="get" action="/">
    <label>年 <input type="number" name="year" value="{{ f.year }}" required min="1850" max="2100"></label>
    <label>月 <input type="number" name="month" value="{{ f.month }}" required min="1" max="12"></label>
    <label>日 <input type="number" name="day" value="{{ f.day }}" required min="1" max="31"></label>
    <label>時 (0-23) <input type="number" name="time" value="{{ f.time }}" required min="0" max="23"></label>
    <label>曆法
      <select name="cal">
        <option value="g" {{ 'selected' if f.cal == 'g' }}>公曆</option>
        <option value="l" {{ 'selected' if f.cal == 'l' }}>農曆</option>
      </select>
    </label>
    <label>性別
      <select name="sex">
        <option value="m" {{ 'selected' if f.sex == 'm' }}>男</option>
        <option value="f" {{ 'selected' if f.sex == 'f' }}>女</option>
      </select>
    </label>
    <label class="chk"><input type="checkbox" name="leap" value="1" {{ 'checked' if f.leap }}> 閏月(農曆)</label>
    <button type="submit">排盤</button>
  </form>
  {% if error %}<div class="err">{{ error }}</div>{% endif %}
  {% if result %}<div class="out"><pre>{{ result|safe }}</pre></div>{% endif %}
  <p class="note">僅供參考與娛樂，命理評判不代表科學結論。</p>
</div>
</body>
</html>
"""


def ansi_to_html(text):
    escaped = html.escape(text)
    open_spans = 0
    out = []
    pos = 0
    for m in ANSI_RE.finditer(escaped):
        out.append(escaped[pos:m.start()])
        pos = m.end()
        codes = m.group(1).split(";")
        if codes in ([""], ["0"]):
            out.append("</span>" * open_spans)
            open_spans = 0
        elif "36" in codes:
            out.append('<span class="c36">')
            open_spans += 1
    out.append(escaped[pos:])
    out.append("</span>" * open_spans)
    return "".join(out)


def parse_form(args):
    f = {
        "year": args.get("year", ""),
        "month": args.get("month", ""),
        "day": args.get("day", ""),
        "time": args.get("time", ""),
        "cal": args.get("cal", "g"),
        "sex": args.get("sex", "m"),
        "leap": args.get("leap") == "1",
    }
    return f


def run_bazi(f):
    try:
        y, mo, d, t = (int(f[k]) for k in ("year", "month", "day", "time"))
    except ValueError:
        return None, "請完整填寫年、月、日、時（皆為整數）。"
    if not (1850 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31 and 0 <= t <= 23):
        return None, "日期或時間超出範圍。"
    if f["cal"] == "g":
        try:
            datetime.date(y, mo, d)
        except ValueError:
            return None, "公曆沒有這個日期。"
    else:
        lm = LunarMonth.fromYm(y, -mo if f["leap"] else mo)
        if lm is None:
            return None, "該年沒有這個閏月。"
        if d > lm.getDayCount():
            return None, "農曆該月只有 %d 天。" % lm.getDayCount()

    cmd = [sys.executable, os.path.join(BASE_DIR, "bazi.py"), str(y), str(mo), str(d), str(t)]
    if f["cal"] == "g":
        cmd.append("-g")
    elif f["leap"]:
        cmd.append("-r")
    if f["sex"] == "f":
        cmd.append("-n")

    try:
        proc = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, text=True,
                              encoding="utf-8", timeout=60)
    except subprocess.TimeoutExpired:
        return None, "排盤逾時。"
    if proc.returncode != 0 or not proc.stdout.strip():
        tail = (proc.stderr or "").strip().splitlines()[-3:]
        return None, "排盤失敗，請檢查日期是否存在（例如該月沒有此日）。\n" + "\n".join(tail)
    return ansi_to_html(proc.stdout), None


@app.route("/")
def index():
    f = parse_form(request.args)
    result = error = None
    if request.args.get("year"):
        result, error = run_bazi(f)
    return render_template_string(PAGE, f=f, result=result, error=error)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)))
