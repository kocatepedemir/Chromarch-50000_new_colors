import os
import sqlite3
import uuid

from flask import Flask, request, jsonify, session, Response

ITEMS_PER_PAGE = 24

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

# sid -> path to that session's uploaded db file
SESSION_DBS = {}


class ColorApp:
    """Holds the row-parsing logic. Pure data logic, no GUI/tkinter
    dependency, so it works the same whether called from a desktop
    tkinter app or from this Flask server."""

    @staticmethod
    def parse_row_data(columns, row):
        name = "Color Item"
        hex_val = ""
        rgb_val = ""
        extra = []

        for idx, cell in enumerate(row):
            col_name = str(columns[idx]).lower()
            val = str(cell) if cell is not None else ""

            if "hex" in col_name or val.startswith("#"):
                hex_val = val if val.startswith("#") else f"#{val}"
            elif "rgb" in col_name or "rgb" in val:
                rgb_val = val
            elif "name" in col_name or "title" in col_name or "label" in col_name:
                name = val
            else:
                if not hex_val and (val.startswith("#") or len(val) == 6):
                    hex_val = val if val.startswith("#") else f"#{val}"
                else:
                    extra.append(f"{columns[idx]}: {val}")

        return name, hex_val, rgb_val, "\n".join(extra[:3])


def get_session_id():
    if "sid" not in session:
        session["sid"] = str(uuid.uuid4())
    return session["sid"]


def get_db_path():
    sid = get_session_id()
    return SESSION_DBS.get(sid)


# --------------------------------------------------------------------------
# Embedded frontend (HTML + CSS + JS in one string, no separate files)
# --------------------------------------------------------------------------
PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>GitHub New Colors Explorer (50k Dataset)</title>
<style>
:root {
  --bg: #0d1117; --panel: #161b22; --border: #21262d;
  --text: #c9d1d9; --text-bright: #f0f6fc; --text-dim: #8b949e;
  --accent: #58a6ff; --accent2: #79c0ff; --green: #238636; --input-bg: #010409;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--text);
  font-family: "Segoe UI", system-ui, sans-serif;
  height: 100vh; display: flex; flex-direction: column;
}
#top-frame { background: var(--panel); padding: 12px 15px; display: flex; align-items: center; gap: 10px; }
#title { color: var(--accent); font-size: 15px; font-weight: bold; margin-right: auto; }
#search-entry {
  background: var(--input-bg); color: var(--text); border: 1px solid #30363d;
  padding: 6px 8px; font-size: 10pt; width: 260px; border-radius: 3px;
}
#search-entry:focus { outline: none; border-color: var(--accent); }
#load-btn {
  background: var(--green); color: white; font-weight: bold; font-size: 10pt;
  border: 0; padding: 6px 12px; border-radius: 4px; cursor: pointer;
}
#load-btn:disabled { opacity: 0.6; cursor: default; }
#load-btn:not(:disabled):hover { filter: brightness(1.1); }
#file-input { display: none; }
#main-container { flex: 1; overflow-y: auto; padding: 10px; }
#status-label { text-align: center; color: var(--text-dim); font-size: 12pt; padding: 50px 0; white-space: pre-line; }
#grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; padding: 10px; }
@media (max-width: 800px) { #grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 500px) { #grid { grid-template-columns: 1fr; } }
.card { background: var(--panel); border: 1px solid var(--border); border-radius: 4px; overflow: hidden; display: flex; flex-direction: column; }
.card-preview { height: 55px; }
.card-details { padding: 8px 10px; }
.card-title { color: var(--text-bright); font-weight: bold; font-size: 10pt; margin-bottom: 4px; word-break: break-word; }
.card-btn {
  display: block; width: 100%; background: var(--input-bg); border: 0; text-align: left;
  padding: 4px 6px; margin: 2px 0; font-family: Consolas, monospace; font-size: 9pt;
  cursor: pointer; border-radius: 3px;
}
.card-btn.hex { color: var(--accent); font-weight: bold; }
.card-btn.rgb { color: var(--accent2); font-size: 8pt; }
.card-extra { color: var(--text-dim); font-size: 8pt; margin-top: 4px; white-space: pre-line; }
#nav-frame { background: var(--panel); padding: 8px 15px; display: flex; align-items: center; }
#nav-frame button { background: var(--border); color: var(--text); border: 0; padding: 4px 10px; border-radius: 4px; cursor: pointer; }
#nav-frame button:disabled { opacity: 0.5; cursor: default; }
#page-label { flex: 1; text-align: center; color: var(--text-dim); font-size: 10pt; }
</style>
</head>
<body>

  <div id="top-frame">
    <div id="title">GitHub New Colors Explorer</div>
    <input id="search-entry" type="text" value="Search colors, HEX, RGB...">
    <button id="load-btn">Load Database</button>
    <input id="file-input" type="file" accept=".db,.sqlite,.sqlite3">
  </div>

  <div id="main-container">
    <div id="status-label">Click 'Load Database' to view 50k color dataset.</div>
    <div id="grid" style="display:none;"></div>
  </div>

  <div id="nav-frame">
    <button id="prev-btn" disabled>&#9668; Previous</button>
    <div id="page-label">Page 0 of 0</div>
    <button id="next-btn" disabled>Next &#9658;</button>
  </div>

<script>
const ITEMS_PER_PAGE = 24;
const PLACEHOLDER_TEXT = "Search colors, HEX, RGB...";

let selectedTable = "";
let currentPage = 1;
let totalItems = 0;
let totalPages = 1;
let dbLoaded = false;

const searchEntry = document.getElementById("search-entry");
const loadBtn = document.getElementById("load-btn");
const fileInput = document.getElementById("file-input");
const statusLabel = document.getElementById("status-label");
const grid = document.getElementById("grid");
const prevBtn = document.getElementById("prev-btn");
const nextBtn = document.getElementById("next-btn");
const pageLabel = document.getElementById("page-label");

searchEntry.addEventListener("focus", () => {
  if (searchEntry.value === PLACEHOLDER_TEXT) searchEntry.value = "";
});
searchEntry.addEventListener("blur", () => {
  if (!searchEntry.value.trim()) searchEntry.value = PLACEHOLDER_TEXT;
});
searchEntry.addEventListener("input", () => {
  if (dbLoaded) { currentPage = 1; fetchAndRender(); }
});

loadBtn.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  await loadDatabase(file);
});

prevBtn.addEventListener("click", () => { if (currentPage > 1) { currentPage--; fetchAndRender(); } });
nextBtn.addEventListener("click", () => { if (currentPage < totalPages) { currentPage++; fetchAndRender(); } });

async function loadDatabase(file) {
  loadBtn.disabled = true;
  loadBtn.textContent = "Loading...";
  try {
    const formData = new FormData();
    formData.append("db_file", file);
    const res = await fetch("/api/upload", { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) { alert(data.error || "Failed to read database."); return; }
    selectedTable = data.tables[0];
    dbLoaded = true;
    currentPage = 1;
    fetchAndRender();
  } catch (err) {
    alert("Failed to read database:\\n" + err.message);
  } finally {
    loadBtn.disabled = false;
    loadBtn.textContent = "Load Database";
  }
}

async function fetchAndRender() {
  if (!selectedTable) return;
  let queryText = searchEntry.value.trim();
  if (queryText === PLACEHOLDER_TEXT) queryText = "";
  try {
    const params = new URLSearchParams({ table: selectedTable, q: queryText, page: currentPage });
    const res = await fetch(`/api/query?${params.toString()}`);
    const data = await res.json();
    if (!res.ok) { alert(data.error || "Failed to query database."); return; }
    totalItems = data.total_items;
    totalPages = data.total_pages;
    renderCards(data.cards);
    updatePaginationControls();
  } catch (err) {
    alert("Failed to query database:\\n" + err.message);
  }
}

function renderCards(cards) {
  grid.innerHTML = "";
  if (!cards.length) {
    statusLabel.textContent = "No matching colors found.";
    statusLabel.style.display = "block";
    grid.style.display = "none";
    return;
  }
  statusLabel.style.display = "none";
  grid.style.display = "grid";
  cards.forEach(c => grid.appendChild(createCard(c.name, c.hex, c.rgb, c.extra)));
  document.getElementById("main-container").scrollTop = 0;
}

function createCard(name, hexCode, rgbCode, extraInfo) {
  const card = document.createElement("div");
  card.className = "card";

  const preview = document.createElement("div");
  preview.className = "card-preview";
  preview.style.background = (hexCode && (hexCode.length === 4 || hexCode.length === 7)) ? hexCode : "#21262d";
  card.appendChild(preview);

  const details = document.createElement("div");
  details.className = "card-details";

  const title = document.createElement("div");
  title.className = "card-title";
  title.textContent = name;
  details.appendChild(title);

  if (hexCode) {
    const btnHex = document.createElement("button");
    btnHex.className = "card-btn hex";
    btnHex.textContent = `HEX: ${hexCode}`;
    btnHex.addEventListener("click", () => copyToClipboard(hexCode));
    details.appendChild(btnHex);
  }

  if (rgbCode) {
    const btnRgb = document.createElement("button");
    btnRgb.className = "card-btn rgb";
    btnRgb.textContent = `RGB: ${rgbCode}`;
    btnRgb.addEventListener("click", () => copyToClipboard(rgbCode));
    details.appendChild(btnRgb);
  }

  if (extraInfo) {
    const extra = document.createElement("div");
    extra.className = "card-extra";
    extra.textContent = extraInfo;
    details.appendChild(extra);
  }

  card.appendChild(details);
  return card;
}

function updatePaginationControls() {
  if (totalItems === 0) {
    pageLabel.textContent = "No results found";
    prevBtn.disabled = true;
    nextBtn.disabled = true;
    return;
  }
  pageLabel.textContent = `Page ${currentPage} of ${totalPages.toLocaleString()} (${totalItems.toLocaleString()} colors)`;
  prevBtn.disabled = currentPage <= 1;
  nextBtn.disabled = currentPage >= totalPages;
}

function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    alert(`Copied to clipboard: ${text}`);
  }).catch(() => {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    alert(`Copied to clipboard: ${text}`);
  });
}
</script>
</body>
</html>
"""


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.route("/")
def index():
    return Response(PAGE_HTML, mimetype="text/html")


@app.route("/api/upload", methods=["POST"])
def upload():
    if "db_file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["db_file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    sid = get_session_id()
    dest_path = os.path.join(UPLOAD_DIR, f"{sid}.db")
    file.save(dest_path)
    SESSION_DBS[sid] = dest_path

    try:
        conn = sqlite3.connect(dest_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cur.fetchall()]
        conn.close()
    except Exception as e:
        return jsonify({"error": f"Failed to read database: {e}"}), 400

    if not tables:
        return jsonify({"error": "Database is empty or has no tables."}), 400

    return jsonify({"tables": tables})


@app.route("/api/query")
def query():
    db_path = get_db_path()
    if not db_path or not os.path.exists(db_path):
        return jsonify({"error": "No database loaded yet."}), 400

    table = request.args.get("table", "")
    query_text = request.args.get("q", "").strip()
    page = max(1, int(request.args.get("page", 1)))

    if not table:
        return jsonify({"error": "No table specified."}), 400

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        cur.execute(f"PRAGMA table_info(`{table}`)")
        columns = [c[1] for c in cur.fetchall()]

        where_clause = ""
        params = []
        if query_text:
            conditions = [f"`{c}` LIKE ?" for c in columns]
            where_clause = " WHERE " + " OR ".join(conditions)
            params = [f"%{query_text}%"] * len(columns)

        cur.execute(f"SELECT COUNT(*) FROM `{table}`{where_clause}", params)
        total_items = cur.fetchone()[0]

        offset = (page - 1) * ITEMS_PER_PAGE
        cur.execute(
            f"SELECT * FROM `{table}`{where_clause} LIMIT {ITEMS_PER_PAGE} OFFSET {offset}",
            params,
        )
        rows = cur.fetchall()
        conn.close()

        cards = []
        for row in rows:
            name, hex_val, rgb_val, extra = ColorApp.parse_row_data(columns, row)
            cards.append({"name": name, "hex": hex_val, "rgb": rgb_val, "extra": extra})

        total_pages = max(1, (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

        return jsonify({
            "total_items": total_items,
            "total_pages": total_pages,
            "page": page,
            "cards": cards,
        })

    except Exception as e:
        return jsonify({"error": f"Failed to query database: {e}"}), 400


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
