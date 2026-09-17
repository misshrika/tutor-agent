#!/usr/bin/env python3
"""
AI Tutor Agent — Flask Web App
================================
Upload a PDF/DOCX/TXT document, pick a subject persona, and generate
flashcards that get pushed directly into a running Anki desktop instance
via AnkiConnect.

Local run:   python app.py
Open:        http://localhost:5000

Requires Anki desktop open with the AnkiConnect add-on installed
(Tools -> Add-ons -> Get Add-ons, code: 2055492159, then restart Anki).
"""
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request

load_dotenv()

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tutor_core

MAX_UPLOAD_BYTES = 15 * 1024 * 1024   # 15 MB

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES


@app.errorhandler(413)
def too_large(_e):
    return jsonify({"error": f"File is larger than the {MAX_UPLOAD_BYTES // (1024*1024)}MB limit."}), 413


@app.route("/")
def index():
    return HTML_TEMPLATE


@app.route("/api/anki-status")
def api_anki_status():
    reachable = tutor_core.check_anki_reachable()
    return jsonify({"reachable": reachable})


@app.route("/api/generate", methods=["POST"])
def api_generate():
    if "file" not in request.files:
        return jsonify({"error": "No file provided."}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename."}), 400

    ext = Path(f.filename).suffix.lower()
    if ext not in (".pdf", ".docx", ".txt"):
        return jsonify({"error": "Only .pdf, .docx, and .txt files are supported."}), 400

    persona_key = request.form.get("persona", "general")
    if persona_key not in tutor_core.PERSONAS:
        persona_key = "general"

    deck_name = (request.form.get("deck_name") or "").strip() or "AI_Generated_Deck"

    tmp_path = None
    try:
        tmp_fd, tmp_path_str = tempfile.mkstemp(suffix=ext)
        os.close(tmp_fd)
        tmp_path = Path(tmp_path_str)
        f.save(tmp_path)

        flashcards = tutor_core.generate_flashcards(str(tmp_path), persona_key)
        if not flashcards:
            return jsonify({"error": "No flashcards could be generated from this document."}), 422

        push_result = tutor_core.push_to_anki(flashcards, deck_name)

        return jsonify({
            "success": True,
            "deck_name": deck_name,
            "cards": [{"question": c.question, "answer": c.answer} for c in flashcards],
            "push_result": push_result,
        })

    except tutor_core.AnkiNotReachable as e:
        return jsonify({"error": str(e)}), 503
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"Something went wrong: {e}"}), 500
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Tutor Agent</title>
<meta name="description" content="Turn a document into Anki flashcards, automatically.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&family=Spline+Sans+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root {
  --ground: #FAF9F6; --ground-raised: #F2F0E9; --ink: #1E1B16; --ink-soft: #6B6355;
  --line: #DDD6C8; --line-soft: #E9E4D8; --accent: #3D5A45; --accent-soft: #E4EBE3;
  --amber: #B5762A; --amber-soft: #F5EBDC; --red: #A44430; --red-soft: #F5E5E0;
  --chip-bg: #FFFFFF; --shadow: 0 1px 2px rgba(30,27,22,.06), 0 4px 16px rgba(30,27,22,.04);
  --serif: 'Source Serif 4', Georgia, serif; --mono: 'Spline Sans Mono', ui-monospace, 'SF Mono', Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --ground:#17160F; --ground-raised:#1E1C14; --ink:#EDE9DE; --ink-soft:#A39B87;
    --line:#383426; --line-soft:#2A271C; --accent:#7FA089; --accent-soft:#22291F;
    --amber:#D99A4E; --amber-soft:#2C2416; --red:#D97A63; --red-soft:#2C1E19;
    --chip-bg:#1E1C14; --shadow: 0 1px 2px rgba(0,0,0,.3), 0 4px 20px rgba(0,0,0,.25);
  }
}
:root[data-theme="dark"] {
  --ground:#17160F; --ground-raised:#1E1C14; --ink:#EDE9DE; --ink-soft:#A39B87;
  --line:#383426; --line-soft:#2A271C; --accent:#7FA089; --accent-soft:#22291F;
  --amber:#D99A4E; --amber-soft:#2C2416; --red:#D97A63; --red-soft:#2C1E19;
  --chip-bg:#1E1C14; --shadow: 0 1px 2px rgba(0,0,0,.3), 0 4px 20px rgba(0,0,0,.25);
}
* { box-sizing: border-box; }
body { background: var(--ground); color: var(--ink); font-family: var(--serif); margin: 0; padding: 0 20px; padding-block: 40px 80px; }
.mono { font-family: var(--mono); }
.wrap { max-width: 900px; margin: 0 auto; }
.eyebrow { font-family: var(--mono); font-size: 12px; letter-spacing: .12em; text-transform: uppercase; color: var(--accent); font-weight: 600; margin: 0 0 10px; }
h1 { font-size: clamp(26px,4.2vw,36px); font-weight: 700; margin: 0 0 14px; line-height: 1.16; text-wrap: balance; letter-spacing: -.01em; }
.lede { font-size: 16px; line-height: 1.6; color: var(--ink-soft); max-width: 64ch; margin: 0 0 6px; }
.lede strong { color: var(--ink); font-weight: 600; }

.anki-pill { display: inline-flex; align-items: center; gap: 8px; font-family: var(--mono); font-size: 12.5px; color: var(--ink-soft); background: var(--ground-raised); border: 1px solid var(--line); border-radius: 999px; padding: 6px 14px; margin-top: 18px; }
.anki-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--ink-soft); }
.anki-dot.ok { background: var(--accent); }
.anki-dot.bad { background: var(--red); }

.panel { margin: 32px 0; border: 1px solid var(--line); border-radius: 12px; background: var(--chip-bg); box-shadow: var(--shadow); padding: 24px; }
.panel h2 { font-size: 18px; font-weight: 700; margin: 0 0 14px; }

label.field-label { font-family: var(--mono); font-size: 11px; letter-spacing: .05em; text-transform: uppercase; color: var(--ink-soft); display: block; margin: 16px 0 8px; }
label.field-label:first-child { margin-top: 0; }

.persona-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
@media (max-width: 600px) { .persona-grid { grid-template-columns: 1fr; } }
.persona-option { border: 1px solid var(--line); border-radius: 8px; padding: 12px 14px; cursor: pointer; font-family: var(--mono); font-size: 12.5px; text-align: center; transition: border-color .15s ease, background .15s ease; }
.persona-option.selected { border-color: var(--accent); background: var(--accent-soft); color: var(--accent); font-weight: 600; }

input[type=text] { font-family: var(--mono); font-size: 13px; width: 100%; padding: 10px 12px; border-radius: 8px; border: 1px solid var(--line); background: var(--ground-raised); color: var(--ink); }

.dropzone { border: 2px dashed var(--line); border-radius: 10px; padding: 28px 20px; text-align: center; position: relative; margin-top: 4px; }
.dropzone.drag { border-color: var(--accent); background: var(--accent-soft); }
.dropzone p { font-size: 13.5px; color: var(--ink-soft); margin: 0; }
.dropzone .filename { font-family: var(--mono); font-weight: 600; color: var(--ink); margin-top: 6px; }
#fileInput { position: absolute; inset: 0; opacity: 0; cursor: pointer; }

.actions { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 20px; }
button { font-family: var(--mono); font-size: 13px; letter-spacing: .02em; padding: 11px 18px; border-radius: 8px; border: 1px solid var(--line); background: var(--ground-raised); color: var(--ink); cursor: pointer; transition: border-color .15s ease; }
button:hover:not(:disabled) { border-color: var(--accent); }
button.primary { background: var(--accent); border-color: var(--accent); color: var(--ground); font-weight: 600; }
button.primary:hover:not(:disabled) { opacity: .92; }
button:disabled { opacity: .5; cursor: not-allowed; }

.status { font-family: var(--mono); font-size: 13px; color: var(--ink-soft); margin: 16px 0; display: none; align-items: center; gap: 10px; }
.status.show { display: flex; }
.spinner { width: 16px; height: 16px; border: 2px solid var(--line); border-top-color: var(--accent); border-radius: 50%; animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.error-box { font-family: var(--mono); font-size: 13px; color: var(--red); background: var(--red-soft); border: 1px solid var(--red); border-radius: 8px; padding: 12px 14px; margin: 14px 0; display: none; white-space: pre-wrap; }
.error-box.show { display: block; }

.result-summary { font-family: var(--mono); font-size: 13px; background: var(--accent-soft); color: var(--accent); border-radius: 8px; padding: 12px 14px; margin: 16px 0; display: none; }
.result-summary.show { display: block; }

.card-list { margin-top: 16px; display: none; }
.card-list.show { display: block; }
.flashcard { border: 1px solid var(--line); border-radius: 8px; padding: 12px 14px; margin-bottom: 8px; background: var(--ground-raised); }
.flashcard .q { font-weight: 600; font-size: 13.5px; margin-bottom: 4px; }
.flashcard .a { font-size: 13px; color: var(--ink-soft); }

.footnote { margin-top: 36px; font-size: 13px; color: var(--ink-soft); line-height: 1.6; max-width: 64ch; padding-top: 20px; border-top: 1px solid var(--line-soft); }
.footnote code { font-family: var(--mono); font-size: 12px; background: var(--ground-raised); padding: 1px 5px; border-radius: 4px; }
</style>
</head>
<body>
<div class="wrap">

  <p class="eyebrow">Study tool — document to flashcards</p>
  <h1>Upload notes. Get an Anki deck.</h1>
  <p class="lede">
    Drop in a PDF, Word doc, or text file. Pick a subject, and this reads
    the material, generates flashcards with a persona-specific focus
    (technical concepts for CS, vocabulary/grammar for languages), and
    pushes them straight into a new Anki deck on your machine.
  </p>

  <div class="anki-pill" id="ankiPill">
    <span class="anki-dot" id="ankiDot"></span>
    <span id="ankiStatusText">Checking Anki connection...</span>
  </div>

  <div class="panel">
    <h2>Generate a deck</h2>

    <label class="field-label">Document</label>
    <div class="dropzone" id="dropzone">
      <p>Drop a file here, or click to choose one</p>
      <p class="filename" id="filenameLabel"></p>
      <input type="file" id="fileInput" accept=".pdf,.docx,.txt">
    </div>

    <label class="field-label">Subject</label>
    <div class="persona-grid" id="personaGrid">
      <div class="persona-option" data-persona="cs">Computer Science</div>
      <div class="persona-option" data-persona="language">Language Learning</div>
      <div class="persona-option selected" data-persona="general">General Study Notes</div>
    </div>

    <label class="field-label" for="deckName">Anki deck name</label>
    <input type="text" id="deckName" placeholder="e.g. Biology_Chapter_4" value="AI_Generated_Deck">

    <div class="actions">
      <button type="button" class="primary" id="btnGenerate">Generate &amp; push to Anki</button>
    </div>

    <div class="status" id="status"><div class="spinner"></div><span id="statusMsg">Working...</span></div>
    <div class="error-box" id="errorBox"></div>
    <div class="result-summary" id="resultSummary"></div>
    <div class="card-list" id="cardList"></div>
  </div>

  <p class="footnote">
    Requires Anki desktop open on this machine with the
    <code>AnkiConnect</code> add-on installed (Tools &rarr; Add-ons &rarr;
    Get Add-ons, code <code>2055492159</code>, then restart Anki). Cards are
    added with <code>allowDuplicate: false</code>, so re-running this on the
    same material won't create repeats.
  </p>

</div>

<script>
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');
const filenameLabel = document.getElementById('filenameLabel');
const personaGrid = document.getElementById('personaGrid');
const deckNameInput = document.getElementById('deckName');
const btnGenerate = document.getElementById('btnGenerate');
const status = document.getElementById('status');
const statusMsg = document.getElementById('statusMsg');
const errorBox = document.getElementById('errorBox');
const resultSummary = document.getElementById('resultSummary');
const cardList = document.getElementById('cardList');
const ankiDot = document.getElementById('ankiDot');
const ankiStatusText = document.getElementById('ankiStatusText');

let selectedPersona = 'general';
let selectedFile = null;

personaGrid.querySelectorAll('.persona-option').forEach(el => {
  el.addEventListener('click', () => {
    personaGrid.querySelectorAll('.persona-option').forEach(o => o.classList.remove('selected'));
    el.classList.add('selected');
    selectedPersona = el.dataset.persona;
  });
});

fileInput.addEventListener('change', () => {
  if (fileInput.files.length) {
    selectedFile = fileInput.files[0];
    filenameLabel.textContent = selectedFile.name;
  }
});
['dragenter', 'dragover'].forEach(evt => dropzone.addEventListener(evt, e => { e.preventDefault(); dropzone.classList.add('drag'); }));
['dragleave', 'drop'].forEach(evt => dropzone.addEventListener(evt, e => { e.preventDefault(); dropzone.classList.remove('drag'); }));
dropzone.addEventListener('drop', e => {
  const f = e.dataTransfer.files[0];
  if (f) { selectedFile = f; filenameLabel.textContent = f.name; }
});

function showError(msg) { errorBox.textContent = msg; errorBox.classList.add('show'); }
function clearError() { errorBox.classList.remove('show'); errorBox.textContent = ''; }
function setBusy(busy, msg) {
  status.classList.toggle('show', busy);
  if (msg) statusMsg.textContent = msg;
  btnGenerate.disabled = busy;
}

async function checkAnkiStatus() {
  try {
    const res = await fetch('/api/anki-status');
    const data = await res.json();
    if (data.reachable) {
      ankiDot.className = 'anki-dot ok';
      ankiStatusText.textContent = 'Anki connected';
    } else {
      ankiDot.className = 'anki-dot bad';
      ankiStatusText.textContent = 'Anki not reachable — open Anki desktop with AnkiConnect installed';
    }
  } catch (e) {
    ankiDot.className = 'anki-dot bad';
    ankiStatusText.textContent = 'Could not check Anki status';
  }
}
checkAnkiStatus();
setInterval(checkAnkiStatus, 10000);

btnGenerate.addEventListener('click', async () => {
  clearError();
  resultSummary.classList.remove('show');
  cardList.classList.remove('show');
  cardList.innerHTML = '';

  if (!selectedFile) { showError('Please choose a document first.'); return; }

  const fd = new FormData();
  fd.append('file', selectedFile);
  fd.append('persona', selectedPersona);
  fd.append('deck_name', deckNameInput.value.trim() || 'AI_Generated_Deck');

  setBusy(true, 'Reading document, generating flashcards, pushing to Anki — this can take a minute for longer documents...');
  try {
    const res = await fetch('/api/generate', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) { showError(data.error || 'Something went wrong.'); return; }

    resultSummary.textContent = `Added ${data.push_result.added} cards to "${data.deck_name}"` +
      (data.push_result.duplicates_skipped ? ` (${data.push_result.duplicates_skipped} skipped as duplicates)` : '') +
      '. Open Anki to see them.';
    resultSummary.classList.add('show');

    cardList.innerHTML = data.cards.map(c => `
      <div class="flashcard">
        <div class="q">${escapeHtml(c.question)}</div>
        <div class="a">${escapeHtml(c.answer)}</div>
      </div>
    `).join('');
    cardList.classList.add('show');

    checkAnkiStatus();
  } catch (e) {
    showError('Network error — please try again.');
  } finally {
    setBusy(false);
  }
});

function escapeHtml(s) {
  const d = document.createElement('div');
  d.textContent = s == null ? '' : String(s);
  return d.innerHTML;
}
</script>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), threaded=True)
