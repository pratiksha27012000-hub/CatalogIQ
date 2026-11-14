# CatalogIQ Dashboard — one-cell setup script for Google Colab
# Run after the CatalogIQ runtime is initialized (con, catalogiq_app, catalogue_id, src_path, and client if enrichment is enabled).

from pathlib import Path
import os, sys, json, uuid, inspect, importlib, re, html, threading, traceback, shutil
import pandas as pd
import gradio as gr

REQUIRED_RUNTIME = ["con", "catalogiq_app", "catalogue_id", "src_path"]
_missing = [name for name in REQUIRED_RUNTIME if name not in globals()]
if _missing:
    raise RuntimeError(
        "CatalogIQ runtime is not initialized. Missing: " + ", ".join(_missing) +
        ". Run your database, catalogue and CatalogIQ engine initialization cells first, then run this dashboard setup."
    )

# Keep the app's database handle and existing engine; do not create a second DB or retrieval stack.
CON = con
APP = catalogiq_app
CLIENT = globals().get("client")
SRC_PATH = Path(src_path)
SRC_PATH.mkdir(parents=True, exist_ok=True)
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))
_LOCK = threading.RLock()

CSS = r"""
:root{--bg:#070b14;--bg2:#0b111d;--card:#0e1524;--card2:#111a2c;--line:#1b2940;--text:#e8edf7;--muted:#8491aa;--blue:#3b82f6;--cyan:#22d3ee;--green:#22c55e;--amber:#f59e0b;--purple:#8b5cf6;--red:#f43f5e}
body,.gradio-container{background:radial-gradient(900px 420px at 55% -8%,rgba(59,130,246,.10),transparent 60%),var(--bg)!important;color:var(--text)!important;color-scheme:dark}
.gradio-container{max-width:100%!important;padding:0!important;font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif!important}
footer{display:none!important}#cq-shell{gap:0!important;align-items:stretch!important;min-height:100vh;flex-wrap:nowrap!important}
#cq-side{background:var(--bg2);border-right:1px solid var(--line);padding:22px 17px!important;gap:13px!important;min-width:250px!important}
#cq-main{padding:34px 30px 45px!important;gap:16px!important;min-width:450px}
#cq-chat{background:var(--bg2);border-left:1px solid var(--line);padding:0!important;gap:0!important;min-width:320px!important}
#cq-side .block,#cq-side .form,#cq-chat .block{background:transparent!important;border-color:transparent!important;box-shadow:none!important}
.cq-logo{display:flex;align-items:center;gap:11px;padding:3px 4px 9px}.cq-logo-mark{width:39px;height:39px;border-radius:12px;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#3b82f6,#8b5cf6);font-weight:850;color:white;box-shadow:0 6px 18px #3b82f655}.cq-logo-text{font-size:22px;font-weight:800;letter-spacing:-.6px}.cq-logo-text span{color:var(--cyan)}
.cq-label{font-size:10px;letter-spacing:1.4px;font-weight:800;color:var(--muted);text-transform:uppercase;margin:9px 2px 0}
#cq-upload{background:var(--card)!important;border:1px dashed #30405e!important;border-radius:15px!important;min-height:110px}
.cq-status{font-size:11.5px;line-height:1.55;padding:9px 11px;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--muted)}.cq-status.ok{color:#4ade80;border-color:#22c55e55}.cq-status.warn{color:#fbbf24;border-color:#f59e0b55}.cq-status.err{color:#fb7185;border-color:#f43f5e55}
.cq-quick button{justify-content:flex-start!important;text-align:left!important;background:var(--card)!important;border:1px solid var(--line)!important;border-radius:11px!important;color:#c1cce0!important;font-size:11.5px!important;padding:9px 10px!important;min-height:0!important}.cq-quick button:hover{border-color:#3b82f6!important;background:#131d33!important}
.cq-title{text-align:center;margin:3px 0 20px}.cq-title h1{font-size:clamp(25px,3vw,35px);font-weight:850;letter-spacing:-1px;margin:0 0 8px}.cq-title p{color:#aab6cb;font-size:13px;margin:0}
.cq-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:13px;margin-bottom:8px}.cq-kpi{background:linear-gradient(180deg,var(--card2),var(--card));border:1px solid var(--line);border-radius:16px;padding:17px;min-width:0}.cq-kpi-head{display:flex;justify-content:space-between;gap:8px}.cq-kpi-label{font-size:10px;font-weight:800;letter-spacing:.8px;text-transform:uppercase;color:#c5d0e3}.cq-kpi-note{font-size:10px;color:var(--muted);margin-top:4px}.cq-kpi-icon{font-size:16px;width:34px;height:34px;border-radius:10px;display:flex;align-items:center;justify-content:center;background:#1b2942;color:var(--cyan)}.cq-kpi-value{font-size:22px;font-weight:850;margin-top:13px;overflow-wrap:anywhere}.cq-kpi-bar{height:3px;background:#1b2942;border-radius:3px;margin-top:11px;overflow:hidden}.cq-kpi-bar span{display:block;height:100%;background:linear-gradient(90deg,#2563eb,#22d3ee)}
.cq-panels{display:grid;grid-template-columns:1fr 1fr;gap:13px;margin:5px 0 18px}.cq-panel{background:var(--card);border:1px solid var(--line);border-radius:15px;padding:16px}.cq-panel h3{font-size:12px;margin:0 0 13px;color:#cbd5e6}.cq-bar-row{display:grid;grid-template-columns:85px 1fr 40px;gap:9px;align-items:center;margin:10px 0;font-size:10px;color:var(--muted)}.cq-track{height:7px;border-radius:8px;background:#1b2942;overflow:hidden}.cq-track span{display:block;height:100%;border-radius:8px;background:linear-gradient(90deg,#2563eb,#22d3ee)}.cq-track.green span{background:linear-gradient(90deg,#16a34a,#4ade80)}
.cq-section{display:flex;align-items:center;gap:9px;margin:4px 0 13px}.cq-dot{width:8px;height:8px;border-radius:50%;background:var(--cyan);box-shadow:0 0 11px var(--cyan)}.cq-section h2{font-size:17px;margin:0;font-weight:800}.cq-section small{color:var(--muted);font-size:10px;margin-left:auto}
.cq-product-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px}.cq-product{background:linear-gradient(180deg,var(--card2),var(--card));border:1px solid var(--line);border-radius:16px;padding:18px;min-width:0}.cq-product:hover{border-color:#31518c}.cq-product-top{display:flex;justify-content:space-between;gap:8px;margin-bottom:10px}.cq-index{font-size:9px;letter-spacing:1px;color:var(--muted);font-weight:800}.cq-stock{font-size:9px;font-weight:800;padding:4px 8px;border-radius:20px;white-space:nowrap}.cq-in{background:#22c55e22;color:#4ade80}.cq-out{background:#f43f5e22;color:#fb7185}.cq-product-name{font-size:13px;line-height:1.5;font-weight:750;min-height:39px;overflow-wrap:anywhere}.cq-price{font-size:23px;font-weight:850;margin:8px 0;background:linear-gradient(90deg,#60a5fa,#22d3ee);-webkit-background-clip:text;background-clip:text;color:transparent}.cq-description{font-size:10.5px;line-height:1.6;color:#929fb6;min-height:33px;margin-bottom:10px}.cq-product-foot{border-top:1px solid var(--line);padding-top:10px;display:flex;justify-content:space-between;font-size:9px;color:var(--muted)}.cq-empty{padding:35px 16px;border:1px dashed #30405e;border-radius:15px;background:var(--card);color:var(--muted);text-align:center;font-size:12px;line-height:1.8}
.cq-chat-head{display:flex;align-items:center;gap:11px;padding:18px;border-bottom:1px solid var(--line)}.cq-avatar{width:37px;height:37px;border-radius:11px;background:linear-gradient(135deg,#3b82f6,#8b5cf6);display:flex;align-items:center;justify-content:center}.cq-chat-head b{display:block;font-size:13px}.cq-chat-head small{font-size:10px;color:var(--muted)}.cq-msgs{display:flex;flex-direction:column;gap:12px;height:calc(100vh - 220px);min-height:400px;overflow-y:auto;padding:17px}.cq-msg{display:flex;gap:8px;max-width:100%}.cq-msg.user{justify-content:flex-end}.cq-bubble{background:#101a2e;border:1px solid var(--line);border-radius:13px;padding:10px 12px;font-size:11.5px;line-height:1.65;color:#d6deee;white-space:pre-wrap;overflow-wrap:anywhere}.cq-msg.user .cq-bubble{background:linear-gradient(135deg,#2563eb,#4f46e5);border-color:transparent;color:white}.cq-chat-foot{border-top:1px solid var(--line);padding:13px;gap:9px!important}.cq-send button{background:linear-gradient(135deg,#3b82f6,#6366f1)!important;color:white!important;border:0!important;border-radius:11px!important;min-height:42px!important;font-weight:750!important}
#cq-side button,#cq-main button,#cq-chat button{border-radius:10px}
@media(max-width:1150px){#cq-shell{flex-wrap:wrap!important}#cq-side,#cq-main,#cq-chat{min-width:100%!important;border-left:0!important;border-right:0!important;border-bottom:1px solid var(--line)}.cq-msgs{height:420px}.cq-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:650px){#cq-main{padding:23px 14px!important}.cq-kpis,.cq-product-grid,.cq-panels{grid-template-columns:1fr}}
"""

# ---------- File parsing, schema mapping and validation ----------
ALIASES = {
    "product_title": ["product_title", "title", "product name", "name", "item name", "handle"],
    "product_description": ["product_description", "body html", "description", "body", "details", "content", "product details"],
    "selling_price": ["selling_price", "variant price", "price", "selling price", "sale price", "final price", "retail price"],
    "cost_price": ["cost_price", "cost per item", "cost price", "cost", "purchase price", "unit cost"],
    "inventory_quantity": ["inventory_quantity", "variant inventory qty", "inventory quantity", "inventory", "stock", "quantity", "available quantity", "on hand"],
}
CANONICAL = list(ALIASES)

def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s).strip().lower()).strip()

def _auto_map(columns):
    normalized = {_norm(c): c for c in columns}
    out = {}
    for field, aliases in ALIASES.items():
        found = None
        for alias in aliases:
            if _norm(alias) in normalized:
                found = normalized[_norm(alias)]
                break
        out[field] = found or "(Not mapped)"
    return out

def _load_frame(file_obj):
    path = getattr(file_obj, "name", file_obj)
    path = str(path)
    suffix = Path(path).suffix.lower()
    if suffix in (".xlsx", ".xls"):
        frame = pd.read_excel(path)
    elif suffix == ".csv":
        try:
            frame = pd.read_csv(path)
        except UnicodeDecodeError:
            frame = pd.read_csv(path, encoding="latin-1")
    elif suffix == ".json":
        frame = pd.read_json(path)
        if isinstance(frame, pd.Series):
            frame = frame.to_frame()
    else:
        raise ValueError("Supported formats: CSV, XLSX, XLS and JSON.")
    if frame.empty:
        raise ValueError("The uploaded file has no data rows.")
    if len(frame) > 250000:
        raise ValueError("This demo currently limits one upload to 250,000 rows.")
    frame.columns = [str(c).strip() for c in frame.columns]
    if frame.columns.duplicated().any():
        raise ValueError("Duplicate column names found. Rename duplicate columns and upload again.")
    return frame, Path(path).stem

def _clean_scalar(v):
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(v, "item"):
        try: v = v.item()
        except Exception: pass
    if isinstance(v, (pd.Timestamp,)):
        return v.isoformat()
    return v

def _canonicalize(frame, name, mapping):
    if mapping.get("product_title") in (None, "(Not mapped)"):
        raise ValueError("Product title is required. Map a source column to Product title.")
    out = pd.DataFrame()
    for field in CANONICAL:
        source = mapping.get(field)
        if source in (None, "(Not mapped)"):
            out[field] = None
        else:
            out[field] = frame[source]
    out["product_title"] = out["product_title"].astype("string").str.strip()
    before = len(out)
    out = out[out["product_title"].notna() & (out["product_title"] != "")].copy()
    dropped = before - len(out)
    if out.empty:
        raise ValueError("No valid product titles remain after validation.")
    for col in ["selling_price", "cost_price", "inventory_quantity"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    if (out["selling_price"].dropna() < 0).any() or (out["cost_price"].dropna() < 0).any():
        raise ValueError("Price columns contain negative values. Correct them before registration.")
    if (out["inventory_quantity"].dropna() < 0).any():
        raise ValueError("Inventory contains negative values. Correct it before registration.")
    # Missing inventory is treated as unknown/zero for the stock-safe default policy.
    out["inventory_quantity"] = out["inventory_quantity"].fillna(0)
    out["source_record_id"] = [f"record_{i:06d}" for i in range(1, len(out) + 1)]
    raw_cols = list(frame.columns)
    raw_rows = []
    for idx in out.index:
        raw = {str(k): _clean_scalar(v) for k, v in frame.loc[idx, raw_cols].to_dict().items()}
        raw_rows.append(json.dumps(raw, ensure_ascii=False, default=str))
    out["source_record_json"] = raw_rows
    return out[["source_record_id", "product_title", "product_description", "selling_price", "cost_price", "inventory_quantity", "source_record_json"]], dropped

# ---------- Database operations ----------
def _catalogue_choices():
    rows = CON.execute("""
        SELECT catalogue_name, catalogue_id
        FROM catalogue_registry
        WHERE status = 'active'
        ORDER BY created_at DESC
    """).fetchall()
    return [(str(n), str(i)) for n, i in rows]

def _catalogue_stats(catalogue_id):
    row = CON.execute("""
        SELECT COUNT(*) AS products,
               SUM(CASE WHEN COALESCE(inventory_quantity,0) > 0 THEN 1 ELSE 0 END) AS in_stock,
               AVG(selling_price) AS avg_price,
               SUM(CASE WHEN COALESCE(inventory_quantity,0) <= 0 THEN 1 ELSE 0 END) AS out_stock
        FROM catalogue_records WHERE catalogue_id = ?
    """, [catalogue_id]).fetchone()
    attrs = CON.execute("SELECT COUNT(DISTINCT source_record_id), COUNT(*) FROM catalogue_attributes WHERE catalogue_id = ?", [catalogue_id]).fetchone()
    total = int(row[0] or 0); in_stock = int(row[1] or 0); out_stock = int(row[3] or 0)
    enriched = int(attrs[0] or 0); attr_count = int(attrs[1] or 0)
    return {"products":total,"in_stock":in_stock,"avg_price":row[2],"out_stock":out_stock,"enriched":enriched,"attributes":attr_count,"coverage":round(100*enriched/total,1) if total else 0}

def _index_rebuild(catalogue_id):
    """Find and call the existing semantic index builder without assuming a new retrieval architecture."""
    roots = [("catalogiq_app", APP)]
    for key, value in list(globals().items()):
        class_name = type(value).__name__.lower()
        if key not in {"APP", "CON", "CLIENT", "gr", "pd", "os", "sys"} and (
            "semantic" in key.lower() or "retriev" in key.lower() or "index" in key.lower()
            or "manager" in key.lower() or "semantic" in class_name
        ):
            roots.append((key, value))
    queue = list(roots); seen = set(); candidates = []
    while queue:
        label, obj = queue.pop(0)
        if id(obj) in seen: continue
        seen.add(id(obj))
        lname = label.lower(); cname = type(obj).__name__.lower()
        for method_name in ("build_index", "rebuild_index", "build_catalogue_index", "refresh_index", "create_index"):
            fn = getattr(obj, method_name, None)
            if callable(fn) and ("semantic" in lname or "semantic" in cname or "retriev" in lname or obj is APP):
                candidates.append((f"{label}.{method_name}", fn))
        if len(seen) > 250: continue
        try:
            attrs = vars(obj)
        except Exception:
            attrs = {}
        for k, v in attrs.items():
            if k.startswith("_"): continue
            if isinstance(v, (str, int, float, bool, type(None), pd.DataFrame, pd.Series)):
                continue
            if inspect.ismodule(v):
                if "semantic" in k.lower() or "semantic" in getattr(v, "__name__", "").lower():
                    queue.append((f"{label}.{k}", v))
            elif not inspect.isclass(v) and not inspect.isfunction(v):
                queue.append((f"{label}.{k}", v))
    # Also inspect a semantic_search module already imported in the notebook.
    for mod_name, mod in list(sys.modules.items()):
        if mod and (mod_name.endswith("semantic_search") or mod_name == "semantic_search"):
            for method_name in ("build_index", "rebuild_index", "build_catalogue_index", "refresh_index"):
                fn = getattr(mod, method_name, None)
                if callable(fn): candidates.append((f"{mod_name}.{method_name}", fn))
    unique=[]; keys=set()
    for label, fn in candidates:
        if id(fn) not in keys: unique.append((label,fn)); keys.add(id(fn))
    if not unique:
        raise RuntimeError("Could not locate the existing semantic index builder in the running CatalogIQ app. The catalogue was saved but marked index_failed; no fake searchable status was reported.")
    last_error = None
    for label, fn in unique:
        try:
            sig = inspect.signature(fn)
            params = [p for p in sig.parameters.values() if p.kind in (p.POSITIONAL_ONLY,p.POSITIONAL_OR_KEYWORD,p.KEYWORD_ONLY)]
            values = {
                "con": CON, "conn": CON, "connection": CON, "db": CON, "database": CON,
                "catalogue_id": catalogue_id, "catalog_id": catalogue_id, "catalogue": catalogue_id,
                "records": CON.execute("SELECT * FROM catalogue_records WHERE catalogue_id = ?", [catalogue_id]).df(),
                "df": CON.execute("SELECT * FROM catalogue_records WHERE catalogue_id = ?", [catalogue_id]).df(),
                "dataframe": CON.execute("SELECT * FROM catalogue_records WHERE catalogue_id = ?", [catalogue_id]).df(),
            }
            kwargs = {}; positional=[]; unresolved=[]
            for p in params:
                if p.name in values:
                    if p.kind == p.POSITIONAL_ONLY: positional.append(values[p.name])
                    else: kwargs[p.name] = values[p.name]
                elif p.default is inspect.Parameter.empty:
                    unresolved.append(p.name)
            if unresolved:
                last_error = RuntimeError(f"{label} requires unsupported parameters: {unresolved}")
                continue
            fn(*positional, **kwargs)
            return label
        except Exception as e:
            last_error = e
    raise RuntimeError(f"Existing semantic index refresh failed: {last_error}")

def _register_catalogue(path, display_name, mapping):
    frame, detected_name = _load_frame(path)
    canonical, dropped = _canonicalize(frame, display_name or detected_name, mapping)
    new_id = "cat_" + uuid.uuid4().hex[:8]
    name = (display_name or detected_name or "Uploaded catalogue").strip()
    if not name: name = "Uploaded catalogue"
    now = pd.Timestamp.utcnow().to_pydatetime()
    # Save first in a transaction. New catalogue ID guarantees isolation from all existing catalogues.
    CON.execute("BEGIN TRANSACTION")
    try:
        CON.execute("""
            INSERT INTO catalogue_registry (catalogue_id, catalogue_name, source_file, record_count, created_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [new_id, name, Path(path).name, len(canonical), now, "indexing"])
        rows = [tuple(_clean_scalar(v) for v in row) for row in canonical.itertuples(index=False, name=None)]
        CON.executemany("""
            INSERT INTO catalogue_records (
                catalogue_id, source_record_id, product_title, product_description,
                selling_price, cost_price, inventory_quantity, source_record_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [(new_id,) + r for r in rows])
        CON.execute("COMMIT")
    except Exception:
        CON.execute("ROLLBACK")
        raise
    try:
        indexer = _index_rebuild(new_id)
        CON.execute("UPDATE catalogue_registry SET status = 'active' WHERE catalogue_id = ?", [new_id])
        return new_id, f"Registered {len(canonical):,} products. Search index refreshed using {indexer}." + (f" {dropped} rows without titles were skipped." if dropped else ""), "ok"
    except Exception as e:
        CON.execute("UPDATE catalogue_registry SET status = 'index_failed' WHERE catalogue_id = ?", [new_id])
        return new_id, f"Catalogue data saved ({len(canonical):,} products), but index refresh failed: {e}. It is marked index_failed and will not be selected as active for search until repaired.", "warn"

# ---------- Enrichment adapter ----------
def _run_enrichment(catalogue_id):
    if CLIENT is None:
        raise RuntimeError("Gemini client is not available in this notebook session. Re-run your Gemini client initialization cell first.")
    try:
        mod = importlib.import_module("enrichment_pipeline")
    except Exception as e:
        raise RuntimeError(f"Could not import enrichment_pipeline from {SRC_PATH}: {e}")
    fn = getattr(mod, "enrich_catalogue", None)
    if not callable(fn):
        raise RuntimeError("enrichment_pipeline.py does not expose enrich_catalogue().")
    sig = inspect.signature(fn)
    values = {"con":CON,"conn":CON,"connection":CON,"client":CLIENT,"gemini_client":CLIENT,"catalogue_id":catalogue_id,"catalog_id":catalogue_id}
    kwargs={}; positional=[]; unresolved=[]
    for p in sig.parameters.values():
        if p.kind not in (p.POSITIONAL_ONLY,p.POSITIONAL_OR_KEYWORD,p.KEYWORD_ONLY): continue
        if p.name in values:
            if p.kind == p.POSITIONAL_ONLY: positional.append(values[p.name])
            else: kwargs[p.name]=values[p.name]
        elif p.default is inspect.Parameter.empty: unresolved.append(p.name)
    if unresolved:
        raise RuntimeError(f"Unsupported required enrichment parameters: {unresolved}; function signature is {sig}")
    result=fn(*positional,**kwargs)
    return result

# ---------- HTML render helpers ----------
def _price(v):
    try:
        if pd.isna(v): return "—"
        return "₹{:,.0f}".format(float(v))
    except Exception: return "—"

def _kpi(label, note, value, icon, pct=50):
    pct=max(3,min(100,int(pct)))
    return f'<div class="cq-kpi"><div class="cq-kpi-head"><div><div class="cq-kpi-label">{html.escape(label)}</div><div class="cq-kpi-note">{html.escape(note)}</div></div><div class="cq-kpi-icon">{icon}</div></div><div class="cq-kpi-value">{html.escape(str(value))}</div><div class="cq-kpi-bar"><span style="width:{pct}%"></span></div></div>'

def _dashboard_html(catalogue_id):
    if not catalogue_id: return '<div class="cq-empty">Upload or select a catalogue to view its intelligence dashboard.</div>'
    s=_catalogue_stats(catalogue_id)
    pct=round(100*s["in_stock"]/s["products"]) if s["products"] else 0
    cards=[
        _kpi("Total products","Records in active catalogue",f'{s["products"]:,}',"▦",100 if s["products"] else 3),
        _kpi("In stock","Products with available inventory",f'{s["in_stock"]:,}',"✓",pct),
        _kpi("Average selling price","Across catalogue products",_price(s["avg_price"]),"₹",55),
        _kpi("Enriched products","Products with extracted attributes",f'{s["enriched"]:,} / {s["products"]:,}',"✦",s["coverage"]),
        _kpi("Attributes extracted","Dynamic product attributes",f'{s["attributes"]:,}',"⌘",80 if s["attributes"] else 3),
        _kpi("Out of stock","Products with zero inventory",f'{s["out_stock"]:,}',"◌",round(100*s["out_stock"]/s["products"]) if s["products"] else 3),
    ]
    invpct=round(100*s["in_stock"]/s["products"]) if s["products"] else 0
    outpct=100-invpct if s["products"] else 0
    price_rows=CON.execute("""
        SELECT CASE WHEN selling_price IS NULL THEN 'Unknown'
                    WHEN selling_price < 1000 THEN 'Below ₹1k'
                    WHEN selling_price < 5000 THEN '₹1k–5k'
                    WHEN selling_price < 10000 THEN '₹5k–10k'
                    WHEN selling_price < 25000 THEN '₹10k–25k'
                    ELSE 'Above ₹25k' END AS band, COUNT(*)
        FROM catalogue_records WHERE catalogue_id=? GROUP BY 1
        ORDER BY CASE band WHEN 'Below ₹1k' THEN 1 WHEN '₹1k–5k' THEN 2 WHEN '₹5k–10k' THEN 3 WHEN '₹10k–25k' THEN 4 WHEN 'Above ₹25k' THEN 5 ELSE 6 END
    """,[catalogue_id]).fetchall()
    maxc=max([int(x[1]) for x in price_rows] or [1])
    price_html=''.join(f'<div class="cq-bar-row"><span>{html.escape(str(b))}</span><div class="cq-track"><span style="width:{int(100*c/maxc)}%"></span></div><b>{int(c)}</b></div>' for b,c in price_rows) or '<small>No price data</small>'
    stock_html=f'<div class="cq-bar-row"><span>In stock</span><div class="cq-track green"><span style="width:{invpct}%"></span></div><b>{s["in_stock"]}</b></div><div class="cq-bar-row"><span>Out of stock</span><div class="cq-track"><span style="width:{outpct}%"></span></div><b>{s["out_stock"]}</b></div>'
    return '<div class="cq-kpis">'+''.join(cards)+'</div><div class="cq-panels"><div class="cq-panel"><h3>Price distribution</h3>'+price_html+'</div><div class="cq-panel"><h3>Inventory health</h3>'+stock_html+'</div></div>'

def _product_cards(records):
    if records is None or len(records)==0: return '<div class="cq-empty">No matching products yet.<br>Ask the AI Analyst a question or choose a quick prompt.</div>'
    df=records.copy() if isinstance(records,pd.DataFrame) else pd.DataFrame(records)
    cards=[]
    for i,row in enumerate(df.to_dict(orient="records"),1):
        title=html.escape(str(row.get("product_title") or "Untitled product"))
        desc=str(row.get("product_description") or "")
        try:
            from bs4 import BeautifulSoup
            desc=BeautifulSoup(desc,"html.parser").get_text(" ",strip=True)
        except Exception: pass
        desc=html.escape(' '.join(desc.split())[:170])
        try: stock=float(row.get("inventory_quantity") or 0)
        except Exception: stock=0
        badge='In stock' if stock>0 else 'Out of stock'; cls='cq-in' if stock>0 else 'cq-out'
        try: score=f'Match {float(row.get("similarity_score")):.3f}'
        except Exception: score='Catalogue result'
        cards.append(f'<article class="cq-product"><div class="cq-product-top"><span class="cq-index">PRODUCT {i:02d}</span><span class="cq-stock {cls}">{badge}</span></div><div class="cq-product-name">{title}</div><div class="cq-price">{_price(row.get("selling_price"))}</div><div class="cq-description">{desc or "Product information available in catalogue."}</div><div class="cq-product-foot"><span>Inventory: {int(stock) if stock.is_integer() else stock}</span><span>{html.escape(score)}</span></div></article>')
    return '<div class="cq-product-grid">'+''.join(cards)+'</div>'

def _chat_html(history):
    parts=[]
    for role,msg in list(history or []):
        cls=' user' if role=='user' else ''
        parts.append(f'<div class="cq-msg{cls}"><div class="cq-bubble">{html.escape(str(msg))}</div></div>')
    if not parts:
        parts=[f'<div class="cq-msg"><div class="cq-bubble">Hello! I’m your CatalogIQ AI Analyst. Ask me about prices, inventory, product attributes, or catalogue comparisons.</div></div>']
    return '<div class="cq-msgs">'+''.join(parts)+'</div>'

# ---------- Gradio event callbacks ----------
def _file_loaded(file_obj):
    if file_obj is None: return None, gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), '<div class="cq-status">Choose a catalogue file.</div>', ""
    try:
        frame,name=_load_frame(file_obj)
        mapping=_auto_map(frame.columns)
        choices=["(Not mapped)"]+list(frame.columns)
        preview=frame.head(8).copy()
        status=f"Detected {len(frame):,} rows and {len(frame.columns)} columns. Confirm the five canonical mappings, then register."
        return frame, gr.update(choices=choices,value=mapping["product_title"]),gr.update(choices=choices,value=mapping["product_description"]),gr.update(choices=choices,value=mapping["selling_price"]),gr.update(choices=choices,value=mapping["cost_price"]),gr.update(choices=choices,value=mapping["inventory_quantity"]),gr.update(value=name), gr.update(value=f'<div class="cq-status ok">{html.escape(status)}</div>'), preview
    except Exception as e:
        return None, *(gr.update() for _ in range(6)), gr.update(value=f'<div class="cq-status err">{html.escape(str(e))}</div>'), None

def _register_click(file_obj,frame,name,title_col,desc_col,price_col,cost_col,stock_col):
    if file_obj is None or frame is None: raise gr.Error("Upload a catalogue file first.")
    mapping={"product_title":title_col,"product_description":desc_col,"selling_price":price_col,"cost_price":cost_col,"inventory_quantity":stock_col}
    path=getattr(file_obj,"name",file_obj)
    try:
        new_id,message,kind=_register_catalogue(str(path),name,mapping)
        choices=_catalogue_choices()
        status=f'<div class="cq-status {"ok" if kind=="ok" else "warn"}">{html.escape(message)}<br>Catalogue ID: {html.escape(new_id)}</div>'
        if kind == "ok":
            return gr.update(choices=choices,value=new_id), status, _dashboard_html(new_id)
        return gr.update(choices=choices,value=default_id), status, _dashboard_html(default_id)
    except Exception as e:
        raise gr.Error(f"Registration failed: {e}")

def _search(question,catalogue_id,top_k,history):
    history=list(history or [])
    if not question or not str(question).strip(): return _dashboard_html(catalogue_id),_product_cards(None),_chat_html(history),history,""
    q=str(question).strip(); history.append(("user",q))
    try:
        with _LOCK:
            response=APP.ask(catalogue_id=catalogue_id,question=q,top_k=int(top_k))
        if response.get("status")!="success":
            history.append(("assistant","Search could not be completed: "+str(response.get("errors","Unknown error"))))
            return _dashboard_html(catalogue_id),_product_cards(None),_chat_html(history),history,""
        records=response.get("records",[])
        df=records.copy() if isinstance(records,pd.DataFrame) else pd.DataFrame(records)
        answer=response.get("answer","No answer generated.")
        history.append(("assistant",answer))
        return _dashboard_html(catalogue_id),_product_cards(df),_chat_html(history),history,""
    except Exception as e:
        history.append(("assistant",f"Application error: {e}"))
        return _dashboard_html(catalogue_id),_product_cards(None),_chat_html(history),history,""

def _refresh_catalogue(catalogue_id):
    return _dashboard_html(catalogue_id),_product_cards(None)

def _enrich_click(catalogue_id):
    if not catalogue_id: raise gr.Error("Select a catalogue first.")
    try:
        result=_run_enrichment(catalogue_id)
        return _dashboard_html(catalogue_id), f'<div class="cq-status ok">Attribute enrichment completed. {html.escape(str(result)[:900])}</div>'
    except Exception as e:
        return _dashboard_html(catalogue_id), f'<div class="cq-status err">Enrichment failed: {html.escape(str(e))}</div>'

def _clear_chat(): return _chat_html([]), []

# ---------- Assemble the three-panel dashboard ----------
choices=_catalogue_choices()
default_id=str(catalogue_id)
if not any(v==default_id for _,v in choices):
    try:
        row=CON.execute("SELECT catalogue_name FROM catalogue_registry WHERE catalogue_id=?",[default_id]).fetchone()
        if row: choices.insert(0,(str(row[0]),default_id))
    except Exception: pass

GRADIO_MAJOR = int(str(getattr(gr, "__version__", "5")).split(".")[0])
_BLOCKS_KWARGS = {"title": "CatalogIQ | Product Intelligence"}
if GRADIO_MAJOR < 6:
    _BLOCKS_KWARGS.update({"theme": gr.themes.Base(primary_hue="blue",secondary_hue="indigo",neutral_hue="slate"), "css": CSS})
with gr.Blocks(**_BLOCKS_KWARGS) as demo:
    history_state=gr.State([])
    upload_frame=gr.State(None)
    with gr.Row(elem_id="cq-shell",equal_height=False):
        with gr.Column(scale=2,min_width=250,elem_id="cq-side"):
            gr.HTML('<div class="cq-logo"><div class="cq-logo-mark">IQ</div><div class="cq-logo-text">Catalog<span>IQ</span></div></div>')
            gr.HTML('<div class="cq-label">01 · Ingest catalogue</div>')
            file_upload=gr.File(label="Drop CSV / Excel / JSON or browse",file_types=[".csv",".xlsx",".xls",".json"],file_count="single",type="filepath",elem_id="cq-upload")
            catalogue_name=gr.Textbox(label="Catalogue name",placeholder="e.g. Spring 2027 Catalogue")
            gr.HTML('<div class="cq-label">02 · Map source columns</div>')
            title_map=gr.Dropdown(label="Product title · required",choices=["(Not mapped)"],value="(Not mapped)")
            desc_map=gr.Dropdown(label="Description",choices=["(Not mapped)"],value="(Not mapped)")
            price_map=gr.Dropdown(label="Selling price",choices=["(Not mapped)"],value="(Not mapped)")
            cost_map=gr.Dropdown(label="Cost price",choices=["(Not mapped)"],value="(Not mapped)")
            stock_map=gr.Dropdown(label="Inventory quantity",choices=["(Not mapped)"],value="(Not mapped)")
            register_btn=gr.Button("Register catalogue & build index",variant="primary")
            upload_status=gr.HTML('<div class="cq-status">Upload a file to detect columns and preview your data.</div>')
            gr.HTML('<div class="cq-label">Quick prompts</div>')
            quick_prompts=["Find products below ₹5,000 that are in stock","Find cotton products suitable for everyday use","Show the lowest-priced products","Find products with high inventory","Find out-of-stock products"]
            quick_buttons=[gr.Button(x,size="sm",elem_classes=["cq-quick"]) for x in quick_prompts]
            gr.HTML('<div class="cq-label">Search settings</div>')
            catalogue=gr.Dropdown(label="Active catalogue",choices=choices,value=default_id,interactive=True)
            top_k=gr.Slider(1,10,value=5,step=1,label="Results to display")
            enrich_btn=gr.Button("✦  Enrich product attributes",variant="secondary")
            enrich_status=gr.HTML('<div class="cq-status">Enrichment uses your configured Gemini API client and is only run when you click this button.</div>')
            clear_btn=gr.Button("Clear conversation",size="sm")
            gr.HTML('<div class="cq-status">CatalogIQ combines semantic retrieval, structured filters and extracted catalogue attributes. Uploaded catalogues are isolated under new catalogue IDs.</div>')
        with gr.Column(scale=7,min_width=450,elem_id="cq-main"):
            gr.HTML('<div class="cq-title"><h1>AI-Powered Product Intelligence</h1><p>Catalogue health · semantic discovery · structured product insights</p></div>')
            dashboard=gr.HTML(_dashboard_html(default_id))
            gr.HTML('<div class="cq-section"><span class="cq-dot"></span><h2>Matching products</h2><small>Ranked results from your active catalogue</small></div>')
            products=gr.HTML(_product_cards(None))
            gr.HTML('<div class="cq-label">Upload preview · first 8 source rows</div>')
            preview=gr.Dataframe(value=None,interactive=False,wrap=True,show_row_numbers=False)
        with gr.Column(scale=3,min_width=320,elem_id="cq-chat"):
            gr.HTML('<div class="cq-chat-head"><div class="cq-avatar">✦</div><div><b>AI Analyst</b><small>Ask questions about the active catalogue</small></div></div>')
            chat=gr.HTML(_chat_html([]))
            with gr.Column(elem_classes=["cq-chat-foot"]):
                question=gr.Textbox(show_label=False,placeholder="Ask about price, stock, fabric, margins...",lines=2,max_lines=4)
                send=gr.Button("Send  ➤",variant="primary",elem_classes=["cq-send"])

    file_upload.upload(fn=_file_loaded,inputs=file_upload,outputs=[upload_frame,title_map,desc_map,price_map,cost_map,stock_map,catalogue_name,upload_status,preview])
    register_btn.click(fn=_register_click,inputs=[file_upload,upload_frame,catalogue_name,title_map,desc_map,price_map,cost_map,stock_map],outputs=[catalogue,upload_status,dashboard])
    catalogue.change(fn=_refresh_catalogue,inputs=catalogue,outputs=[dashboard,products])
    send.click(fn=_search,inputs=[question,catalogue,top_k,history_state],outputs=[dashboard,products,chat,history_state,question])
    question.submit(fn=_search,inputs=[question,catalogue,top_k,history_state],outputs=[dashboard,products,chat,history_state,question])
    for btn,prompt in zip(quick_buttons,quick_prompts):
        btn.click(fn=lambda c,k,h,p=prompt:_search(p,c,k,h),inputs=[catalogue,top_k,history_state],outputs=[dashboard,products,chat,history_state,question])
    enrich_btn.click(fn=_enrich_click,inputs=catalogue,outputs=[dashboard,enrich_status])
    clear_btn.click(fn=_clear_chat,inputs=None,outputs=[chat,history_state])

# Close any old dashboard instance before launching the new one.
try:
    old_demo=globals().get("demo")
    if old_demo is not None: old_demo.close()
except Exception: pass

demo = demo
try:
    if "__file__" in globals() and Path(__file__).exists():
        _saved_setup = SRC_PATH / "catalogiq_dashboard_setup.py"
        if Path(__file__).resolve() != _saved_setup.resolve():
            shutil.copy2(__file__, _saved_setup)
        print("Setup script saved to:", _saved_setup)
except Exception as _save_error:
    print("Note: setup script could not be copied into the project folder:", _save_error)

print("CatalogIQ dashboard is built.")
print("Catalogue count:", len(choices))
print("Current catalogue:", default_id)
print("Upload flow: file → auto column mapping → preview → register → semantic index refresh.")
print("Enrichment is manual via the sidebar button; it uses the existing enrichment_pipeline.py and Gemini client.")
_LAUNCH_KWARGS = {"share": True}
if GRADIO_MAJOR >= 6:
    _LAUNCH_KWARGS.update({"theme": gr.themes.Base(primary_hue="blue",secondary_hue="indigo",neutral_hue="slate"), "css": CSS})
demo.launch(**_LAUNCH_KWARGS)
