# CatalogIQ — Simple three-panel dashboard for Google Colab
# Layout: LEFT upload | CENTRE five canonical catalogue dimensions | RIGHT AI chat
# Run this after initializing the existing CatalogIQ runtime (con, catalogiq_app, src_path).

from pathlib import Path
import os, sys, json, uuid, inspect, importlib, re, html, threading, time, shutil
import pandas as pd
import gradio as gr

REQUIRED_RUNTIME = ["con", "catalogiq_app", "src_path"]
_missing = [name for name in REQUIRED_RUNTIME if name not in globals()]
if _missing:
    raise RuntimeError(
        "CatalogIQ runtime is not initialized. Missing: " + ", ".join(_missing) +
        ". Run your database and CatalogIQ engine initialization cells first."
    )

CON = con
APP = catalogiq_app
CLIENT = globals().get("client")
SRC_PATH = Path(src_path)
SRC_PATH.mkdir(parents=True, exist_ok=True)
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))
_LOCK = threading.RLock()

# ---------- Styling ----------
CSS = r"""
:root{--bg:#080d17;--side:#0c1320;--card:#101a2b;--card2:#131f33;--line:#22314a;--text:#e9effa;--muted:#91a0b8;--blue:#4386ff;--cyan:#35d4e9;--green:#29c778;--amber:#f5b544;--red:#f16b7c}
body,.gradio-container{background:var(--bg)!important;color:var(--text)!important;color-scheme:dark}
.gradio-container{max-width:100%!important;padding:0!important;font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif!important}
footer{display:none!important}#catalogiq-root{padding:0!important}#cq-shell{gap:0!important;align-items:stretch!important;min-height:100vh;flex-wrap:nowrap!important}
#cq-upload-panel{background:var(--side);border-right:1px solid var(--line);padding:22px 18px!important;gap:13px!important;min-width:265px!important}
#cq-attributes-panel{padding:32px 30px 42px!important;gap:16px!important;min-width:500px!important}
#cq-chat-panel{background:var(--side);border-left:1px solid var(--line);padding:0!important;gap:0!important;min-width:345px!important}
#cq-upload-panel .block,#cq-upload-panel .form,#cq-chat-panel .block{background:transparent!important;border-color:transparent!important;box-shadow:none!important}
.cq-logo{display:flex;align-items:center;gap:10px;padding:2px 3px 16px}.cq-logo-mark{width:38px;height:38px;border-radius:11px;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#377cf4,#7857e8);font-weight:850;color:white;box-shadow:0 6px 18px #3b82f644}.cq-logo-name{font-size:21px;font-weight:800;letter-spacing:-.6px}.cq-logo-name span{color:var(--cyan)}
.cq-label{font-size:10px;letter-spacing:1.25px;font-weight:800;color:var(--muted);text-transform:uppercase;margin:8px 2px 0}
#cq-upload{background:var(--card)!important;border:1px dashed #3a4b69!important;border-radius:14px!important;min-height:105px}#cq-upload *{font-size:12px}
.cq-status{font-size:11.5px;line-height:1.55;padding:9px 11px;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--muted);overflow-wrap:anywhere}.cq-status.ok{color:#73dfa2;border-color:#29c77866}.cq-status.warn{color:#f6c66d;border-color:#f5b54466}.cq-status.err{color:#ff8794;border-color:#f16b7c66}
.cq-mapping-note{font-size:10.5px;line-height:1.5;color:var(--muted)}
#cq-upload-panel button{border-radius:10px!important}
.cq-primary button{background:linear-gradient(135deg,#3277f5,#4d63e8)!important;border:0!important;color:white!important;font-weight:750!important}
.cq-secondary button{background:#18253b!important;border:1px solid var(--line)!important;color:#cbd7e9!important}
.cq-main-head{margin:0 0 5px}.cq-main-head h1{font-size:clamp(24px,2.4vw,32px);font-weight:850;letter-spacing:-.9px;margin:0 0 7px}.cq-main-head p{font-size:12px;color:var(--muted);margin:0}
.cq-catalogue-name{font-size:12px;color:#b9c8df;margin-top:17px;padding:10px 12px;background:#101a2b;border:1px solid var(--line);border-radius:10px;display:flex;justify-content:space-between;gap:10px}.cq-catalogue-name strong{color:#e9effa;font-weight:700}
.cq-attribute-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-top:9px}.cq-attribute{background:linear-gradient(180deg,var(--card2),var(--card));border:1px solid var(--line);border-radius:16px;padding:18px;min-width:0}.cq-attribute:last-child{grid-column:1 / -1}.cq-attribute-head{display:flex;align-items:center;justify-content:space-between;gap:9px}.cq-attribute-title{font-size:13px;font-weight:800;color:#dbe6f7}.cq-attribute-icon{width:34px;height:34px;border-radius:10px;background:#1d2b44;color:var(--cyan);display:flex;align-items:center;justify-content:center;font-size:15px;flex:none}.cq-attribute-value{font-size:24px;font-weight:850;letter-spacing:-.4px;margin:14px 0 5px;overflow-wrap:anywhere}.cq-attribute-sub{font-size:10.5px;color:var(--muted);line-height:1.5}.cq-coverage{height:5px;background:#1d2b44;border-radius:8px;overflow:hidden;margin-top:13px}.cq-coverage span{display:block;height:100%;background:linear-gradient(90deg,#347cf6,#34d4e7);border-radius:8px}.cq-attribute-foot{display:flex;justify-content:space-between;gap:8px;margin-top:8px;color:#a4b2c9;font-size:10px}
.cq-empty{padding:45px 22px;border:1px dashed #34445f;border-radius:16px;background:var(--card);color:var(--muted);text-align:center;font-size:12px;line-height:1.8}
.cq-chat-head{display:flex;align-items:center;gap:11px;padding:18px 17px;border-bottom:1px solid var(--line)}.cq-avatar{width:37px;height:37px;border-radius:11px;background:linear-gradient(135deg,#377cf4,#7857e8);display:flex;align-items:center;justify-content:center;font-size:16px}.cq-chat-head b{display:block;font-size:13px}.cq-chat-head small{font-size:10px;color:var(--muted)}.cq-chat-caption{padding:12px 17px 0;font-size:10px;color:var(--muted);line-height:1.5}
.cq-msgs{display:flex;flex-direction:column;gap:11px;height:calc(100vh - 205px);min-height:390px;overflow-y:auto;padding:16px}.cq-msg{display:flex;max-width:100%}.cq-msg.user{justify-content:flex-end}.cq-bubble{background:#111d31;border:1px solid var(--line);border-radius:13px;padding:10px 12px;font-size:11.5px;line-height:1.65;color:#dbe5f5;white-space:pre-wrap;overflow-wrap:anywhere}.cq-msg.user .cq-bubble{background:linear-gradient(135deg,#2868df,#514fd0);border-color:transparent;color:white}.cq-chat-foot{border-top:1px solid var(--line);padding:13px;gap:9px!important}.cq-chat-foot textarea{background:#0a1220!important;border:1px solid var(--line)!important;border-radius:11px!important;color:var(--text)!important;font-size:12px!important}.cq-send button{background:linear-gradient(135deg,#377cf4,#5a5ce3)!important;color:white!important;border:0!important;border-radius:11px!important;min-height:42px!important;font-weight:750!important}
@media(max-width:1180px){#cq-shell{flex-wrap:wrap!important}#cq-upload-panel,#cq-attributes-panel,#cq-chat-panel{min-width:100%!important;border-left:0!important;border-right:0!important;border-bottom:1px solid var(--line)}.cq-msgs{height:400px}.cq-attribute-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:650px){#cq-attributes-panel{padding:23px 14px!important}.cq-attribute-grid{grid-template-columns:1fr}.cq-attribute:last-child{grid-column:auto}}
"""

# ---------- Column mapping and validation ----------
ALIASES = {
    "product_title": ["product_title", "title", "product name", "name", "item name"],
    "product_description": ["product_description", "body html", "description", "body", "details", "content", "product details"],
    "selling_price": ["selling_price", "variant price", "price", "selling price", "sale price", "final price", "retail price"],
    "cost_price": ["cost_price", "cost per item", "cost price", "cost", "purchase price", "unit cost"],
    "inventory_quantity": ["inventory_quantity", "variant inventory qty", "inventory quantity", "inventory", "stock", "quantity", "available quantity", "on hand"],
}
CANONICAL = list(ALIASES)
FIELD_LABELS = {
    "product_title": "Product Name", "product_description": "Description",
    "selling_price": "Selling Price", "cost_price": "Cost Price",
    "inventory_quantity": "Inventory Quantity"
}

def _norm(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower()).strip()

def _auto_map(columns):
    by_name = {_norm(c): c for c in columns}
    result = {}
    for field, aliases in ALIASES.items():
        result[field] = next((by_name[_norm(a)] for a in aliases if _norm(a) in by_name), "(Not mapped)")
    return result

def _load_frame(file_obj):
    path = str(getattr(file_obj, "name", file_obj))
    suffix = Path(path).suffix.lower()
    if suffix in (".xlsx", ".xls"):
        frame = pd.read_excel(path)
    elif suffix == ".csv":
        try: frame = pd.read_csv(path)
        except UnicodeDecodeError: frame = pd.read_csv(path, encoding="latin-1")
    elif suffix == ".json":
        frame = pd.read_json(path)
    else:
        raise ValueError("Supported formats: CSV, XLSX, XLS and JSON.")
    if frame.empty: raise ValueError("The uploaded file has no data rows.")
    if len(frame) > 250000: raise ValueError("One upload is limited to 250,000 rows in this demo.")
    frame.columns = [str(c).strip() for c in frame.columns]
    if frame.columns.duplicated().any(): raise ValueError("Duplicate source column names found. Rename them and upload again.")
    return frame, Path(path).stem

def _clean_scalar(value):
    if value is None: return None
    try:
        if pd.isna(value): return None
    except (TypeError, ValueError): pass
    if hasattr(value, "item"):
        try: value = value.item()
        except Exception: pass
    if isinstance(value, pd.Timestamp): return value.isoformat()
    return value

def _canonicalize(frame, mapping):
    if mapping.get("product_title") in (None, "(Not mapped)"):
        raise ValueError("Product Name is required. Map a source column to Product Name.")
    out = pd.DataFrame(index=frame.index)
    for field in CANONICAL:
        source = mapping.get(field)
        out[field] = frame[source] if source not in (None, "(Not mapped)") else None
    out["product_title"] = out["product_title"].astype("string").str.strip()
    original_count = len(out)
    out = out[out["product_title"].notna() & (out["product_title"] != "")].copy()
    dropped = original_count - len(out)
    if out.empty: raise ValueError("No valid product names remain after validation.")
    for col in ["selling_price", "cost_price", "inventory_quantity"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    if (out[["selling_price", "cost_price"]].dropna(how="all") < 0).any().any():
        raise ValueError("Price columns contain negative values. Correct them before registration.")
    if (out["inventory_quantity"].dropna() < 0).any():
        raise ValueError("Inventory contains negative values. Correct it before registration.")
    # Preserve unknown inventory as NULL; do not convert it to zero.
    out["source_record_id"] = [f"record_{i:06d}" for i in range(1, len(out) + 1)]
    raw_rows = []
    for idx in out.index:
        raw = {str(k): _clean_scalar(v) for k, v in frame.loc[idx].to_dict().items()}
        raw_rows.append(json.dumps(raw, ensure_ascii=False, default=str))
    out["source_record_json"] = raw_rows
    return out[["source_record_id", "product_title", "product_description", "selling_price", "cost_price", "inventory_quantity", "source_record_json"]], dropped

# ---------- Catalogue and index operations ----------
def _catalogue_choices():
    rows = CON.execute("""
        SELECT catalogue_name, catalogue_id
        FROM catalogue_registry
        WHERE status = 'active'
        ORDER BY created_at DESC
    """).fetchall()
    return [(str(name), str(cat_id)) for name, cat_id in rows]

def _index_rebuild(catalogue_id):
    """Call the project's existing semantic manager using its real signature."""
    records_df = CON.execute(
        "SELECT * FROM catalogue_records WHERE catalogue_id = ?",
        [catalogue_id]
    ).df()
    if records_df.empty:
        raise RuntimeError(f"No catalogue records found for {catalogue_id}.")

    candidates = []
    for key in ("semantic_manager", "semantic_search_manager", "retriever", "hybrid_retriever"):
        obj = globals().get(key)
        if obj is not None: candidates.append((key, obj))
    if getattr(APP, "semantic_manager", None) is not None:
        candidates.append(("catalogiq_app.semantic_manager", APP.semantic_manager))
    if getattr(APP, "semantic_search_manager", None) is not None:
        candidates.append(("catalogiq_app.semantic_search_manager", APP.semantic_search_manager))
    # Search nested app attributes for a semantic manager if it was not exposed directly.
    try:
        for key, obj in vars(APP).items():
            if "semantic" in key.lower() or "index" in key.lower() or "manager" in type(obj).__name__.lower():
                candidates.append((f"catalogiq_app.{key}", obj))
    except Exception:
        pass

    seen = set()
    errors = []
    for label, obj in candidates:
        if id(obj) in seen: continue
        seen.add(id(obj))
        for method_name in ("build_index", "rebuild_index", "refresh_index", "build_catalogue_index"):
            fn = getattr(obj, method_name, None)
            if not callable(fn): continue
            try:
                sig = inspect.signature(fn)
                values = {
                    "catalogue_id": catalogue_id, "catalog_id": catalogue_id,
                    "catalogue": catalogue_id, "records_df": records_df,
                    "df": records_df, "dataframe": records_df, "records": records_df,
                    "con": CON, "conn": CON, "connection": CON, "db": CON,
                }
                positional, kwargs, unresolved = [], {}, []
                for param in sig.parameters.values():
                    if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                        continue
                    if param.name in values:
                        if param.kind == param.POSITIONAL_ONLY:
                            positional.append(values[param.name])
                        else:
                            kwargs[param.name] = values[param.name]
                    elif param.default is inspect.Parameter.empty:
                        unresolved.append(param.name)
                if unresolved:
                    errors.append(f"{label}.{method_name}{sig}: unsupported required parameters {unresolved}")
                    continue
                fn(*positional, **kwargs)
                return f"{label}.{method_name}{sig}"
            except Exception as exc:
                errors.append(f"{label}.{method_name}: {exc}")
    raise RuntimeError("Could not rebuild the semantic index. " + " | ".join(errors[-5:]))

def _register_catalogue(file_path, display_name, mapping):
    frame, detected_name = _load_frame(file_path)
    canonical, dropped = _canonicalize(frame, mapping)
    catalogue_id = "cat_" + uuid.uuid4().hex[:8]
    name = (display_name or detected_name or "Uploaded catalogue").strip() or "Uploaded catalogue"
    created_at = pd.Timestamp.utcnow().to_pydatetime()
    CON.execute("BEGIN TRANSACTION")
    try:
        CON.execute("""
            INSERT INTO catalogue_registry (catalogue_id, catalogue_name, source_file, record_count, created_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [catalogue_id, name, Path(file_path).name, len(canonical), created_at, "indexing"])
        tuples = [tuple(_clean_scalar(v) for v in row) for row in canonical.itertuples(index=False, name=None)]
        CON.executemany("""
            INSERT INTO catalogue_records (
                catalogue_id, source_record_id, product_title, product_description,
                selling_price, cost_price, inventory_quantity, source_record_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [(catalogue_id,) + row for row in tuples])
        CON.execute("COMMIT")
    except Exception:
        CON.execute("ROLLBACK")
        raise
    try:
        indexer = _index_rebuild(catalogue_id)
        CON.execute("UPDATE catalogue_registry SET status='active' WHERE catalogue_id=?", [catalogue_id])
        note = f"Registered {len(canonical):,} products. Semantic index built successfully."
        if dropped: note += f" {dropped} rows without product names were skipped."
        return catalogue_id, note, "ok"
    except Exception as exc:
        CON.execute("UPDATE catalogue_registry SET status='index_failed' WHERE catalogue_id=?", [catalogue_id])
        return catalogue_id, f"Data saved ({len(canonical):,} products), but index refresh failed: {exc}", "warn"

# ---------- Five canonical-field metrics ----------
def _profile(catalogue_id):
    row = CON.execute("""
        SELECT
          COUNT(*) AS total,
          SUM(CASE WHEN product_title IS NOT NULL AND TRIM(product_title)<>'' THEN 1 ELSE 0 END) AS title_filled,
          COUNT(DISTINCT NULLIF(TRIM(product_title),'')) AS unique_titles,
          SUM(CASE WHEN product_description IS NOT NULL AND TRIM(product_description)<>'' THEN 1 ELSE 0 END) AS description_filled,
          AVG(CASE WHEN product_description IS NOT NULL THEN LENGTH(product_description) END) AS avg_description_chars,
          COUNT(selling_price) AS selling_filled, AVG(selling_price) AS avg_selling,
          MIN(selling_price) AS min_selling, MAX(selling_price) AS max_selling,
          COUNT(cost_price) AS cost_filled, AVG(cost_price) AS avg_cost,
          MIN(cost_price) AS min_cost, MAX(cost_price) AS max_cost,
          COUNT(inventory_quantity) AS inventory_filled,
          SUM(CASE WHEN inventory_quantity > 0 THEN 1 ELSE 0 END) AS in_stock,
          SUM(CASE WHEN inventory_quantity = 0 THEN 1 ELSE 0 END) AS out_stock
        FROM catalogue_records WHERE catalogue_id=?
    """, [catalogue_id]).fetchone()
    if not row or not row[0]:
        return None
    names = ["total","title_filled","unique_titles","description_filled","avg_description_chars","selling_filled","avg_selling","min_selling","max_selling","cost_filled","avg_cost","min_cost","max_cost","inventory_filled","in_stock","out_stock"]
    p = dict(zip(names, row))
    p["enriched_products"] = CON.execute(
        "SELECT COUNT(DISTINCT source_record_id) FROM catalogue_attributes WHERE catalogue_id=?",
        [catalogue_id]
    ).fetchone()[0]
    p["attribute_count"] = CON.execute(
        "SELECT COUNT(*) FROM catalogue_attributes WHERE catalogue_id=?", [catalogue_id]
    ).fetchone()[0]
    p["catalogue_name"] = CON.execute(
        "SELECT catalogue_name FROM catalogue_registry WHERE catalogue_id=?", [catalogue_id]
    ).fetchone()[0]
    return p

def _pct(numerator, denominator):
    return round(100 * (float(numerator or 0) / max(int(denominator or 0), 1)))

def _money(value):
    try:
        if value is None or pd.isna(value): return "—"
        return "₹{:,.0f}".format(float(value))
    except Exception:
        return "—"

def _attribute_card(title, icon, value, sub, filled, total, foot_left, foot_right):
    coverage = _pct(filled, total)
    return f'''<article class="cq-attribute">
      <div class="cq-attribute-head"><div class="cq-attribute-title">{html.escape(title)}</div><div class="cq-attribute-icon">{icon}</div></div>
      <div class="cq-attribute-value">{html.escape(str(value))}</div>
      <div class="cq-attribute-sub">{html.escape(str(sub))}</div>
      <div class="cq-coverage"><span style="width:{coverage}%"></span></div>
      <div class="cq-attribute-foot"><span>{html.escape(str(foot_left))}</span><span>{html.escape(str(foot_right))}</span></div>
    </article>'''

def _attributes_html(catalogue_id):
    if not catalogue_id:
        return '<div class="cq-empty">Upload a catalogue or select an existing one to see the five core data dimensions.</div>'
    p = _profile(catalogue_id)
    if not p:
        return '<div class="cq-empty">No catalogue records found for this selection.</div>'
    total = int(p["total"] or 0)
    cards = [
        _attribute_card("Product Name", "▣", f'{int(p["title_filled"] or 0):,} / {total:,}',
            f'{int(p["unique_titles"] or 0):,} unique product names', p["title_filled"], total,
            "Required field", f'{_pct(p["title_filled"],total)}% complete'),
        _attribute_card("Description", "▤", f'{int(p["description_filled"] or 0):,} / {total:,}',
            f'Average source description length: {int(p["avg_description_chars"] or 0):,} characters', p["description_filled"], total,
            "Product information coverage", f'{_pct(p["description_filled"],total)}% complete'),
        _attribute_card("Selling Price", "₹", _money(p["avg_selling"]),
            f'Range: {_money(p["min_selling"])} – {_money(p["max_selling"])}', p["selling_filled"], total,
            f'{int(p["selling_filled"] or 0):,} prices available', f'{_pct(p["selling_filled"],total)}% complete'),
        _attribute_card("Cost Price", "◈", _money(p["avg_cost"]),
            f'Range: {_money(p["min_cost"])} – {_money(p["max_cost"])}', p["cost_filled"], total,
            f'{int(p["cost_filled"] or 0):,} costs available', f'{_pct(p["cost_filled"],total)}% complete'),
        _attribute_card("Inventory Quantity", "▦", f'{int(p["in_stock"] or 0):,} in stock',
            f'{int(p["out_stock"] or 0):,} out of stock · {int(p["inventory_filled"] or 0):,} inventory values recorded', p["inventory_filled"], total,
            "Inventory coverage", f'{_pct(p["inventory_filled"],total)}% complete'),
    ]
    return ''.join([
        f'<div class="cq-catalogue-name"><span>Selected catalogue</span><strong>{html.escape(str(p["catalogue_name"]))} · {total:,} products</strong></div>',
        '<div class="cq-attribute-grid">', ''.join(cards), '</div>'
    ])

# ---------- Chat and enrichment ----------
def _chat_html(history):
    parts=[]
    for role, message in list(history or []):
        cls = " user" if role == "user" else ""
        parts.append(f'<div class="cq-msg{cls}"><div class="cq-bubble">{html.escape(str(message))}</div></div>')
    if not parts:
        parts = ['<div class="cq-msg"><div class="cq-bubble">Hi! I’m your CatalogIQ assistant. Ask me anything about the selected catalogue — products, descriptions, pricing, costs, inventory or extracted attributes.</div></div>']
    return '<div class="cq-msgs">' + ''.join(parts) + '</div>'

def _run_enrichment(catalogue_id):
    if CLIENT is None:
        raise RuntimeError("Gemini client is not available. Initialize your Gemini client first.")
    mod = importlib.import_module("enrichment_pipeline")
    fn = getattr(mod, "enrich_catalogue", None)
    if not callable(fn):
        raise RuntimeError("enrichment_pipeline.py does not expose enrich_catalogue().")
    sig = inspect.signature(fn)
    values = {"con":CON,"conn":CON,"connection":CON,"client":CLIENT,"gemini_client":CLIENT,"catalogue_id":catalogue_id,"catalog_id":catalogue_id}
    kwargs, positional, unresolved = {}, [], []
    for param in sig.parameters.values():
        if param.kind not in (param.POSITIONAL_ONLY,param.POSITIONAL_OR_KEYWORD,param.KEYWORD_ONLY): continue
        if param.name in values:
            if param.kind == param.POSITIONAL_ONLY: positional.append(values[param.name])
            else: kwargs[param.name] = values[param.name]
        elif param.default is inspect.Parameter.empty: unresolved.append(param.name)
    if unresolved: raise RuntimeError(f"Unsupported required enrichment parameters: {unresolved}; function signature: {sig}")
    return fn(*positional, **kwargs)

def _friendly_ai_error(exc):
    msg = str(exc)
    if any(token in msg.lower() for token in ("503", "unavailable", "high demand", "temporarily")):
        return "The AI model is temporarily busy (503). Your catalogue is safe; please try the question again shortly."
    return "I couldn't complete that query: " + msg

def _ask(question, catalogue_id, history):
    history = list(history or [])
    q = str(question or "").strip()
    if not q: return _chat_html(history), history, ""
    if not catalogue_id:
        history.extend([("user",q),("assistant","Please upload or select a catalogue first.")])
        return _chat_html(history), history, ""
    history.append(("user",q))
    try:
        response = None
        last_error = None
        for attempt in range(3):
            try:
                with _LOCK:
                    response = APP.ask(catalogue_id=catalogue_id, question=q, top_k=5)
                if response.get("status") == "success": break
                last_error = response.get("errors", "Unknown error")
                if not any(t in str(last_error).lower() for t in ("503","unavailable","high demand","temporarily")): break
            except Exception as exc:
                last_error = exc
                if not any(t in str(exc).lower() for t in ("503","unavailable","high demand","temporarily")): raise
            if attempt < 2: time.sleep(1.5 * (attempt + 1))
        if response is None or response.get("status") != "success":
            raise RuntimeError(str(last_error or "AI service did not return a successful response."))
        answer = response.get("answer", "No answer was generated.")
        history.append(("assistant", str(answer)))
    except Exception as exc:
        history.append(("assistant", _friendly_ai_error(exc)))
    return _chat_html(history), history, ""

# ---------- Gradio callbacks ----------
def _file_loaded(file_obj):
    if file_obj is None:
        return *(gr.update() for _ in range(6)), '<div class="cq-status">Choose a catalogue file to begin.</div>', None
    try:
        frame, detected_name = _load_frame(file_obj)
        mapping = _auto_map(frame.columns)
        choices = ["(Not mapped)"] + list(frame.columns)
        preview = frame.head(8)
        status = f'<div class="cq-status ok">Detected {len(frame):,} product rows and {len(frame.columns)} columns. Review the mappings and register the catalogue.</div>'
        return (
            gr.update(choices=choices,value=mapping["product_title"]),
            gr.update(choices=choices,value=mapping["product_description"]),
            gr.update(choices=choices,value=mapping["selling_price"]),
            gr.update(choices=choices,value=mapping["cost_price"]),
            gr.update(choices=choices,value=mapping["inventory_quantity"]),
            gr.update(value=detected_name), status, preview
        )
    except Exception as exc:
        return *(gr.update() for _ in range(6)), f'<div class="cq-status err">{html.escape(str(exc))}</div>', None

def _register_click(file_obj, name, title_col, desc_col, price_col, cost_col, stock_col):
    if file_obj is None: raise gr.Error("Upload a catalogue file first.")
    mapping = {"product_title":title_col,"product_description":desc_col,"selling_price":price_col,"cost_price":cost_col,"inventory_quantity":stock_col}
    path = str(getattr(file_obj,"name",file_obj))
    try:
        new_id, message, kind = _register_catalogue(path,name,mapping)
        choices = _catalogue_choices()
        status = f'<div class="cq-status {"ok" if kind=="ok" else "warn"}">{html.escape(message)}<br>Catalogue ID: {html.escape(new_id)}</div>'
        if kind == "ok":
            return gr.update(choices=choices,value=new_id), status, _attributes_html(new_id)
        return gr.update(choices=choices), status, _attributes_html(new_id)
    except Exception as exc:
        raise gr.Error(f"Catalogue registration failed: {exc}")

def _catalogue_changed(catalogue_id):
    return _attributes_html(catalogue_id)

def _enrich_click(catalogue_id):
    if not catalogue_id: raise gr.Error("Select a catalogue first.")
    try:
        result = _run_enrichment(catalogue_id)
        return _attributes_html(catalogue_id), f'<div class="cq-status ok">Attribute enrichment finished. {html.escape(str(result)[:700])}</div>'
    except Exception as exc:
        return _attributes_html(catalogue_id), f'<div class="cq-status err">Enrichment failed: {html.escape(str(exc))}</div>'

def _clear_chat():
    return _chat_html([]), []

# ---------- Repair the latest failed upload, when possible ----------
# This specifically recovers a catalogue whose rows were saved but whose index
# refresh failed in an earlier dashboard version. It never re-imports the file.
try:
    _failed = CON.execute("""
        SELECT catalogue_id FROM catalogue_registry
        WHERE status='index_failed'
        ORDER BY created_at DESC LIMIT 1
    """).fetchone()
    if _failed:
        _failed_id = str(_failed[0])
        _repair_method = _index_rebuild(_failed_id)
        CON.execute("UPDATE catalogue_registry SET status='active' WHERE catalogue_id=?", [_failed_id])
        print(f"Repaired saved catalogue {_failed_id}; index rebuilt using {_repair_method}.")
except Exception as _repair_error:
    print("A previously failed catalogue index could not be repaired automatically:", _repair_error)

# ---------- Build the simplified three-panel UI ----------
choices = _catalogue_choices()
override_default = globals().get("CATALOGIQ_DASHBOARD_DEFAULT_ID")
default_id = str(override_default) if override_default else (choices[0][1] if choices else "")
if default_id and not any(value == default_id for _, value in choices):
    row = CON.execute("SELECT catalogue_name FROM catalogue_registry WHERE catalogue_id=?",[default_id]).fetchone()
    if row: choices.insert(0,(str(row[0]),default_id))

GRADIO_MAJOR = int(str(getattr(gr,"__version__","5")).split(".")[0])
BLOCKS_KWARGS = {"title":"CatalogIQ | Product Intelligence", "elem_id":"catalogiq-root"}
if GRADIO_MAJOR < 6:
    BLOCKS_KWARGS.update({"theme":gr.themes.Base(primary_hue="blue",secondary_hue="indigo",neutral_hue="slate"),"css":CSS})

with gr.Blocks(**BLOCKS_KWARGS) as demo:
    history_state = gr.State([])
    with gr.Row(elem_id="cq-shell", equal_height=False):
        # LEFT: upload and catalogue controls
        with gr.Column(scale=3,min_width=265,elem_id="cq-upload-panel"):
            gr.HTML('<div class="cq-logo"><div class="cq-logo-mark">IQ</div><div class="cq-logo-name">Catalog<span>IQ</span></div></div>')
            gr.HTML('<div class="cq-label">01 · Upload catalogue</div>')
            file_upload = gr.File(label="Drop CSV / Excel / JSON or browse",file_types=[".csv",".xlsx",".xls",".json"],file_count="single",type="filepath",elem_id="cq-upload")
            catalogue_name = gr.Textbox(label="Catalogue name",placeholder="e.g. Spring Collection")
            gr.HTML('<div class="cq-label">02 · Map columns</div>')
            gr.HTML('<div class="cq-mapping-note">We’ll detect common column names automatically. Confirm the mapping before registration.</div>')
            with gr.Accordion("Review the five field mappings",open=False):
                title_map = gr.Dropdown(label="Product Name · required",choices=["(Not mapped)"],value="(Not mapped)")
                desc_map = gr.Dropdown(label="Description",choices=["(Not mapped)"],value="(Not mapped)")
                price_map = gr.Dropdown(label="Selling Price",choices=["(Not mapped)"],value="(Not mapped)")
                cost_map = gr.Dropdown(label="Cost Price",choices=["(Not mapped)"],value="(Not mapped)")
                stock_map = gr.Dropdown(label="Inventory Quantity",choices=["(Not mapped)"],value="(Not mapped)")
            register_btn = gr.Button("Register catalogue",variant="primary",elem_classes=["cq-primary"])
            upload_status = gr.HTML('<div class="cq-status">Upload a file to detect columns and preview its first rows.</div>')
            gr.HTML('<div class="cq-label">03 · Active catalogue</div>')
            catalogue = gr.Dropdown(label="Selected catalogue",choices=choices,value=default_id or None,interactive=True)
            enrich_btn = gr.Button("Enrich product attributes",variant="secondary",elem_classes=["cq-secondary"])
            enrich_status = gr.HTML('<div class="cq-status">Optional: run Gemini enrichment to extract product-specific attributes.</div>')
            preview = gr.Dataframe(value=None,interactive=False,wrap=True,show_row_numbers=False,label="Upload preview · first 8 rows")

        # CENTRE: exactly five canonical catalogue dimensions
        with gr.Column(scale=6,min_width=500,elem_id="cq-attributes-panel"):
            gr.HTML('<div class="cq-main-head"><h1>Catalogue attributes</h1><p>Your five core data dimensions, completeness and key metrics.</p></div>')
            attributes = gr.HTML(_attributes_html(default_id))

        # RIGHT: free-form AI assistant
        with gr.Column(scale=4,min_width=345,elem_id="cq-chat-panel"):
            gr.HTML('<div class="cq-chat-head"><div class="cq-avatar">✦</div><div><b>CatalogIQ Assistant</b><small>Ask anything about your selected catalogue</small></div></div>')
            gr.HTML('<div class="cq-chat-caption">Questions can cover products, descriptions, pricing, costs, inventory and extracted attributes.</div>')
            chat = gr.HTML(_chat_html([]))
            with gr.Column(elem_classes=["cq-chat-foot"]):
                question = gr.Textbox(show_label=False,placeholder="Ask CatalogIQ anything…",lines=2,max_lines=5)
                send = gr.Button("Send  ➤",variant="primary",elem_classes=["cq-send"])

    file_upload.upload(fn=_file_loaded,inputs=file_upload,outputs=[title_map,desc_map,price_map,cost_map,stock_map,catalogue_name,upload_status,preview])
    register_btn.click(fn=_register_click,inputs=[file_upload,catalogue_name,title_map,desc_map,price_map,cost_map,stock_map],outputs=[catalogue,upload_status,attributes])
    catalogue.change(fn=_catalogue_changed,inputs=catalogue,outputs=attributes)
    enrich_btn.click(fn=_enrich_click,inputs=catalogue,outputs=[attributes,enrich_status])
    send.click(fn=_ask,inputs=[question,catalogue,history_state],outputs=[chat,history_state,question])
    question.submit(fn=_ask,inputs=[question,catalogue,history_state],outputs=[chat,history_state,question])
    clear_btn = None

# Close the prior dashboard, if one exists.
try:
    previous_demo = globals().get("demo")
    if previous_demo is not None and previous_demo is not demo:
        previous_demo.close()
except Exception:
    pass

demo = demo
# Save a reusable copy inside the project folder.
try:
    shutil.copy2(Path(__file__), SRC_PATH / "catalogiq_simple_dashboard.py")
except Exception:
    pass

print("CatalogIQ simple dashboard is ready.")
print("Layout: left upload | centre five canonical fields | right AI assistant")
print("Active catalogue:", default_id or "No active catalogue")
print("Index builder adapter passes catalogue_id and records_df based on the live method signature.")

LAUNCH_KWARGS = {"server_name": "0.0.0.0", "server_port": int(os.environ.get("PORT", "7860"))}
if GRADIO_MAJOR >= 6:
    LAUNCH_KWARGS.update({"theme":gr.themes.Base(primary_hue="blue",secondary_hue="indigo",neutral_hue="slate"),"css":CSS})
demo.launch(**LAUNCH_KWARGS)
