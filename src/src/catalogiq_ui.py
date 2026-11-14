
import html
import re
import threading
import pandas as pd
import gradio as gr

try:
    from attribute_extractor import clean_html_text
except ImportError:
    clean_html_text = lambda value: str(value)

CSS = '\n:root {\n    --bg: #080d18;\n    --bg2: #0d1422;\n    --panel: #111a2b;\n    --panel2: #151f31;\n    --border: #222e42;\n    --text: #edf2fa;\n    --muted: #8492aa;\n    --blue: #3b82f6;\n    --cyan: #22d3ee;\n    --green: #22c55e;\n    --purple: #8b5cf6;\n    --amber: #f59e0b;\n    --red: #f43f5e;\n}\n\nbody, .gradio-container {\n    color-scheme: dark !important;\n    background: var(--bg) !important;\n    color: var(--text) !important;\n    font-family: Inter, "Segoe UI", sans-serif !important;\n}\n\n.gradio-container {\n    max-width: 100% !important;\n    padding: 0 !important;\n}\n\nfooter { display: none !important; }\n\n#catalogiq-app {\n    padding: 0 !important;\n    width: 100% !important;\n}\n\n/* Main three-panel shell */\n\n#cq-shell {\n    display: flex !important;\n    flex-wrap: nowrap !important;\n    gap: 0 !important;\n    align-items: stretch !important;\n    width: 100% !important;\n    min-height: 100vh;\n}\n\n/* Left sidebar */\n\n#cq-side {\n    flex: 0 0 238px !important;\n    width: 238px !important;\n    min-width: 238px !important;\n    max-width: 238px !important;\n    background: var(--bg2);\n    border-right: 1px solid var(--border);\n    padding: 24px 17px !important;\n    gap: 14px !important;\n}\n\n.cq-logo {\n    display: flex;\n    align-items: center;\n    gap: 11px;\n    padding: 2px 3px 16px;\n}\n\n.cq-logo-mark {\n    height: 38px;\n    width: 38px;\n    border-radius: 11px;\n    display: flex;\n    align-items: center;\n    justify-content: center;\n    background: linear-gradient(135deg,#3b82f6,#8b5cf6);\n    color: white;\n    font-size: 15px;\n    font-weight: 850;\n    box-shadow: 0 6px 18px rgba(59,130,246,.3);\n}\n\n.cq-logo-text {\n    font-size: 21px;\n    font-weight: 800;\n    letter-spacing: -.7px;\n}\n\n.cq-logo-text span { color: var(--cyan); }\n\n.cq-side-label {\n    color: var(--muted);\n    font-size: 9px;\n    font-weight: 800;\n    letter-spacing: 1.5px;\n    text-transform: uppercase;\n    margin: 10px 2px 3px;\n}\n\n.cq-sidebar-card {\n    background: var(--panel);\n    border: 1px solid var(--border);\n    border-radius: 14px;\n    padding: 14px;\n}\n\n.cq-sidebar-card b {\n    display: block;\n    font-size: 12px;\n    margin-bottom: 5px;\n}\n\n.cq-sidebar-card small {\n    color: var(--muted);\n    font-size: 10px;\n    line-height: 1.6;\n}\n\n.cq-progress {\n    height: 5px;\n    background: #202c40;\n    border-radius: 8px;\n    overflow: hidden;\n    margin-top: 11px;\n}\n\n.cq-progress span {\n    height: 100%;\n    display: block;\n    background: linear-gradient(90deg,#3b82f6,#22d3ee);\n    border-radius: 8px;\n}\n\n.cq-quick button {\n    background: var(--panel) !important;\n    border: 1px solid var(--border) !important;\n    color: #bdc9dd !important;\n    border-radius: 10px !important;\n    padding: 9px 11px !important;\n    min-height: 0 !important;\n    text-align: left !important;\n    justify-content: flex-start !important;\n    font-size: 11px !important;\n    font-weight: 500 !important;\n    transition: .18s ease;\n}\n\n.cq-quick button:hover {\n    background: #19263b !important;\n    border-color: #35517b !important;\n    color: white !important;\n}\n\n.cq-clear button {\n    background: transparent !important;\n    border: 1px solid var(--border) !important;\n    color: var(--muted) !important;\n    border-radius: 10px !important;\n    font-size: 11px !important;\n}\n\n/* Centre dashboard */\n\n#cq-main {\n    flex: 1 1 0 !important;\n    min-width: 480px !important;\n    padding: 32px 28px 45px !important;\n    gap: 0 !important;\n    background:\n        radial-gradient(ellipse at 50% 0%,rgba(43,75,125,.10),transparent 55%),\n        var(--bg);\n}\n\n.cq-main-heading {\n    text-align: center;\n    margin: 6px 0 30px;\n}\n\n.cq-main-heading h1 {\n    color: var(--text);\n    font-size: clamp(23px,2.5vw,33px);\n    font-weight: 850;\n    letter-spacing: -1px;\n    margin: 0 0 9px;\n}\n\n.cq-main-heading p {\n    color: #9cacc4;\n    font-size: 12px;\n    margin: 0;\n}\n\n.cq-kpis {\n    display: grid;\n    grid-template-columns: repeat(3,minmax(0,1fr));\n    gap: 15px;\n    margin-bottom: 34px;\n}\n\n.cq-kpi {\n    background: linear-gradient(160deg,var(--panel2),var(--panel));\n    border: 1px solid var(--border);\n    border-radius: 15px;\n    padding: 17px 17px 15px;\n    min-width: 0;\n    transition: .2s ease;\n}\n\n.cq-kpi:hover {\n    transform: translateY(-2px);\n    border-color: #334766;\n}\n\n.cq-kpi-head {\n    display: flex;\n    justify-content: space-between;\n    align-items: flex-start;\n    gap: 7px;\n}\n\n.cq-kpi-label {\n    color: #c8d3e5;\n    font-size: 10px;\n    font-weight: 800;\n    letter-spacing: .7px;\n    text-transform: uppercase;\n}\n\n.cq-kpi-note {\n    color: var(--muted);\n    font-size: 9px;\n    margin-top: 5px;\n}\n\n.cq-kpi-icon {\n    width: 34px;\n    height: 34px;\n    border-radius: 9px;\n    display: flex;\n    justify-content: center;\n    align-items: center;\n    font-size: 15px;\n    flex: none;\n}\n\n.cq-kpi-value {\n    color: white;\n    font-size: 22px;\n    font-weight: 850;\n    margin: 17px 0 12px;\n    overflow-wrap: anywhere;\n}\n\n.cq-kpi-bar {\n    height: 3px;\n    background: #263249;\n    border-radius: 5px;\n    overflow: hidden;\n}\n\n.cq-kpi-bar span {\n    height: 100%;\n    display: block;\n    border-radius: 5px;\n}\n\n.cq-blue .cq-kpi-icon { background:#15365b; color:#60a5fa; }\n.cq-blue .cq-kpi-bar span { background:#3b82f6; }\n\n.cq-green .cq-kpi-icon { background:#10392f; color:#34d399; }\n.cq-green .cq-kpi-bar span { background:#22c55e; }\n\n.cq-cyan .cq-kpi-icon { background:#103744; color:#22d3ee; }\n.cq-cyan .cq-kpi-bar span { background:#22d3ee; }\n\n.cq-purple .cq-kpi-icon { background:#2b2050; color:#a78bfa; }\n.cq-purple .cq-kpi-bar span { background:#8b5cf6; }\n\n.cq-amber .cq-kpi-icon { background:#443016; color:#fbbf24; }\n.cq-amber .cq-kpi-bar span { background:#f59e0b; }\n\n.cq-red .cq-kpi-icon { background:#431d30; color:#fb7185; }\n.cq-red .cq-kpi-bar span { background:#f43f5e; }\n\n.cq-section {\n    display: flex;\n    align-items: center;\n    gap: 9px;\n    margin: 5px 0 17px;\n}\n\n.cq-section-dot {\n    width: 8px;\n    height: 8px;\n    background: var(--cyan);\n    border-radius: 50%;\n    box-shadow: 0 0 10px var(--cyan);\n}\n\n.cq-section h2 {\n    color: var(--text);\n    font-size: 17px;\n    font-weight: 800;\n    margin: 0;\n}\n\n.cq-section small {\n    color: var(--muted);\n    margin-left: auto;\n    font-size: 10px;\n}\n\n/* Results */\n\n.cq-product-grid {\n    display: grid;\n    grid-template-columns: repeat(2,minmax(0,1fr));\n    gap: 14px;\n}\n\n.cq-product-card {\n    background: linear-gradient(160deg,var(--panel2),var(--panel));\n    border: 1px solid var(--border);\n    border-radius: 15px;\n    padding: 18px;\n    min-width: 0;\n    transition: .2s ease;\n}\n\n.cq-product-card:hover {\n    border-color: #35517b;\n    transform: translateY(-2px);\n    box-shadow: 0 10px 24px rgba(0,0,0,.2);\n}\n\n.cq-product-top {\n    display: flex;\n    justify-content: space-between;\n    align-items: center;\n    gap: 8px;\n    margin-bottom: 12px;\n}\n\n.cq-product-index {\n    color: var(--muted);\n    font-size: 9px;\n    font-weight: 800;\n    letter-spacing: 1px;\n}\n\n.cq-stock {\n    font-size: 9px;\n    font-weight: 750;\n    border-radius: 20px;\n    padding: 5px 9px;\n    white-space: nowrap;\n}\n\n.cq-stock-in { background:#123a2b; color:#4ade80; }\n.cq-stock-out { background:#431d2e; color:#fb7185; }\n\n.cq-product-name {\n    color: var(--text);\n    font-size: 14px;\n    line-height: 1.55;\n    font-weight: 750;\n    min-height: 42px;\n    overflow-wrap: anywhere;\n}\n\n.cq-price {\n    color: #60c7f0;\n    font-size: 24px;\n    font-weight: 850;\n    margin: 9px 0;\n}\n\n.cq-product-description {\n    color: #91a0b8;\n    font-size: 10px;\n    line-height: 1.65;\n    min-height: 44px;\n    margin-bottom: 12px;\n}\n\n.cq-product-bottom {\n    border-top: 1px solid var(--border);\n    padding-top: 11px;\n    display: flex;\n    justify-content: space-between;\n    align-items: center;\n    gap: 7px;\n}\n\n.cq-muted { color: var(--muted); font-size: 9px; }\n\n.cq-score {\n    background: #192944;\n    color: #85b8ff;\n    padding: 5px 8px;\n    border-radius: 7px;\n    font-size: 9px;\n    font-weight: 750;\n}\n\n.cq-empty {\n    padding: 35px 16px;\n    text-align: center;\n    background: var(--panel);\n    border: 1px dashed #344259;\n    border-radius: 15px;\n    color: var(--muted);\n    font-size: 12px;\n    line-height: 1.8;\n}\n\n.cq-empty b { color: var(--text); }\n\n/* Right AI chat panel */\n\n#cq-chat {\n    flex: 0 0 350px !important;\n    width: 350px !important;\n    min-width: 330px !important;\n    max-width: 380px !important;\n    background: var(--bg2);\n    border-left: 1px solid var(--border);\n    padding: 0 !important;\n    gap: 0 !important;\n}\n\n.cq-chat-heading {\n    display: flex;\n    align-items: center;\n    gap: 11px;\n    padding: 19px 16px;\n    border-bottom: 1px solid var(--border);\n}\n\n.cq-chat-avatar {\n    height: 36px;\n    width: 36px;\n    flex: none;\n    border-radius: 10px;\n    background: linear-gradient(135deg,#3b82f6,#8b5cf6);\n    display: flex;\n    align-items: center;\n    justify-content: center;\n    color: white;\n    font-size: 16px;\n}\n\n.cq-chat-heading b {\n    display: block;\n    color: var(--text);\n    font-size: 13px;\n}\n\n.cq-chat-heading small {\n    color: var(--muted);\n    font-size: 10px;\n}\n\n.cq-chat-status {\n    color: #4ade80;\n    font-size: 9px;\n    margin-left: auto;\n    white-space: nowrap;\n}\n\n.cq-messages {\n    height: calc(100vh - 190px);\n    min-height: 430px;\n    overflow-y: auto;\n    display: flex;\n    flex-direction: column-reverse;\n    gap: 11px;\n    padding: 17px 13px;\n}\n\n.cq-msg {\n    display: flex;\n    gap: 8px;\n    align-items: flex-start;\n    max-width: 100%;\n}\n\n.cq-msg.user { justify-content: flex-end; }\n\n.cq-msg-icon {\n    width: 25px;\n    height: 25px;\n    flex: none;\n    display: flex;\n    align-items: center;\n    justify-content: center;\n    color: var(--cyan);\n    background: #142641;\n    border-radius: 8px;\n    font-size: 11px;\n}\n\n.cq-bubble {\n    max-width: 90%;\n    overflow-wrap: anywhere;\n    white-space: normal;\n    background: #131e30;\n    border: 1px solid var(--border);\n    color: #d7e0ed;\n    border-radius: 12px;\n    padding: 11px 12px;\n    font-size: 11px;\n    line-height: 1.7;\n}\n\n.cq-msg.user .cq-bubble {\n    color: white;\n    background: linear-gradient(135deg,#245eb0,#5144ac);\n    border: none;\n    border-bottom-right-radius: 3px;\n}\n\n.cq-chat-footer {\n    border-top: 1px solid var(--border);\n    padding: 12px;\n    gap: 9px !important;\n}\n\n.cq-chat-footer textarea {\n    background: #0a101c !important;\n    color: var(--text) !important;\n    border: 1px solid var(--border) !important;\n    border-radius: 11px !important;\n    font-size: 11px !important;\n}\n\n.cq-send button {\n    background: linear-gradient(135deg,#3b82f6,#6557d8) !important;\n    color: white !important;\n    border: none !important;\n    border-radius: 10px !important;\n    min-height: 42px !important;\n    font-weight: 750 !important;\n}\n\n.cq-chat-clear button {\n    background: transparent !important;\n    border: none !important;\n    color: var(--muted) !important;\n    font-size: 10px !important;\n}\n\n/* Responsive layout */\n\n@media(max-width:1150px) {\n    #cq-shell { flex-wrap: wrap !important; }\n\n    #cq-side {\n        flex: 0 0 225px !important;\n        width: 225px !important;\n        min-width: 225px !important;\n    }\n\n    #cq-main {\n        flex: 1 1 calc(100% - 225px) !important;\n        min-width: 480px !important;\n    }\n\n    #cq-chat {\n        flex: 1 1 100% !important;\n        width: 100% !important;\n        max-width: 100% !important;\n        border-left: none;\n        border-top: 1px solid var(--border);\n    }\n\n    .cq-messages { height: 410px; }\n}\n\n@media(max-width:720px) {\n    #cq-shell { display: block !important; }\n\n    #cq-side, #cq-main, #cq-chat {\n        width: 100% !important;\n        min-width: 0 !important;\n        max-width: 100% !important;\n        flex: none !important;\n    }\n\n    #cq-main { padding: 25px 14px !important; }\n\n    .cq-kpis {\n        grid-template-columns: repeat(2,minmax(0,1fr));\n        gap: 9px;\n    }\n\n    .cq-product-grid { grid-template-columns: 1fr; }\n\n    .cq-messages {\n        height: 380px;\n        min-height: 380px;\n    }\n}\n'

WELCOME = (
    "Hello! I'm your CatalogIQ AI Analyst. "
    "Ask me about your catalogue's products, prices, "
    "materials, inventory or product comparisons."
)

QUICK_PROMPTS = [
    "Find products below ₹5,000 that are in stock",
    "Find cotton products suitable for everyday use",
    "Show products with the lowest prices",
    "Find products with high inventory",
    "Find out-of-stock products"
]


def create_catalogiq_demo(
    catalogiq_app,
    catalogue_choices,
    default_catalogue_id
):

    con = catalogiq_app.con
    query_lock = threading.Lock()

    # -----------------------------------------------------
    # Helpers
    # -----------------------------------------------------

    def safe_value(value):
        if value is None:
            return ""
        try:
            if pd.isna(value):
                return ""
        except (TypeError, ValueError):
            pass
        return str(value)

    def format_number(value):
        try:
            return f"{int(value):,}"
        except (ValueError, TypeError):
            return "0"

    def format_price(value):
        try:
            number = float(value)
            if pd.isna(number):
                return "—"
            return "₹{:,.0f}".format(number)
        except (ValueError, TypeError):
            return "—"

    # -----------------------------------------------------
    # Real catalogue KPI summary
    # -----------------------------------------------------

    def catalogue_summary(catalogue_id):

        with query_lock:

            product_row = con.execute("""
                SELECT
                    COUNT(*) AS total_products,
                    COUNT(*) FILTER (
                        WHERE COALESCE(inventory_quantity, 0) > 0
                    ) AS in_stock,
                    COUNT(*) FILTER (
                        WHERE COALESCE(inventory_quantity, 0) = 0
                    ) AS out_of_stock,
                    AVG(selling_price) AS average_price
                FROM catalogue_records
                WHERE catalogue_id = ?
            """, [catalogue_id]).fetchone()

            attribute_row = con.execute("""
                SELECT
                    COUNT(DISTINCT source_record_id),
                    COUNT(*)
                FROM catalogue_attributes
                WHERE catalogue_id = ?
            """, [catalogue_id]).fetchone()

        total = product_row[0] or 0
        in_stock = product_row[1] or 0
        out_stock = product_row[2] or 0
        average_price = product_row[3]

        enriched = attribute_row[0] or 0
        attributes = attribute_row[1] or 0

        coverage = (
            100 * enriched / total
            if total else 0
        )

        return {
            "total": total,
            "in_stock": in_stock,
            "out_of_stock": out_stock,
            "average_price": average_price,
            "enriched": enriched,
            "attributes": attributes,
            "coverage": coverage
        }

    def kpi_card(label, note, icon, color, value, fill):

        fill = max(0, min(100, fill))

        return f"""
        <div class="cq-kpi cq-{color}">
            <div class="cq-kpi-head">
                <div>
                    <div class="cq-kpi-label">{html.escape(label)}</div>
                    <div class="cq-kpi-note">{html.escape(note)}</div>
                </div>
                <div class="cq-kpi-icon">{icon}</div>
            </div>
            <div class="cq-kpi-value">{html.escape(str(value))}</div>
            <div class="cq-kpi-bar">
                <span style="width:{fill:.1f}%"></span>
            </div>
        </div>
        """

    def stats_html(catalogue_id):

        data = catalogue_summary(catalogue_id)

        cards = [
            kpi_card(
                "Total products",
                "Registered catalogue products",
                "▦", "blue",
                format_number(data["total"]), 100
            ),
            kpi_card(
                "In stock",
                "Products currently available",
                "▥", "green",
                format_number(data["in_stock"]),
                100 * data["in_stock"] / max(data["total"], 1)
            ),
            kpi_card(
                "Average price",
                "Average catalogue selling price",
                "₹", "amber",
                format_price(data["average_price"]), 65
            ),
            kpi_card(
                "Enriched products",
                "Products with extracted attributes",
                "✦", "purple",
                f'{format_number(data["enriched"])} / {format_number(data["total"])}',
                data["coverage"]
            ),
            kpi_card(
                "Attributes extracted",
                "Evidence-backed product attributes",
                "◇", "cyan",
                format_number(data["attributes"]), 85
            ),
            kpi_card(
                "Out of stock",
                "Products with zero inventory",
                "⚑", "red",
                format_number(data["out_of_stock"]),
                100 * data["out_of_stock"] / max(data["total"], 1)
            )
        ]

        return (
            '<div class="cq-kpis">'
            + "".join(cards)
            + '</div>'
        )

    def sidebar_summary(catalogue_id):

        data = catalogue_summary(catalogue_id)

        return f"""
        <div class="cq-sidebar-card">
            <b>Catalogue health</b>
            <small>
                {format_number(data['total'])} products registered<br>
                {format_number(data['enriched'])} products enriched
            </small>
            <div class="cq-progress">
                <span style="width:{data['coverage']:.1f}%"></span>
            </div>
            <small>{data['coverage']:.1f}% attribute coverage</small>
        </div>
        """

    # -----------------------------------------------------
    # Product result cards
    # -----------------------------------------------------

    def cards_html(records):

        if records is None or records.empty:
            return """
            <div class="cq-empty">
                <div style="font-size:27px;margin-bottom:8px">⌕</div>
                <b>No matching products yet</b><br>
                Ask the AI Analyst a question to explore your catalogue.
            </div>
            """

        cards = []

        for number, row in enumerate(
            records.to_dict(orient="records"),
            start=1
        ):

            title = html.escape(
                safe_value(row.get("product_title"))
                or "Untitled product"
            )

            description = safe_value(
                row.get("product_description")
            )

            try:
                description = clean_html_text(description)
            except Exception:
                description = re.sub(
                    r"<[^>]+>", " ", description
                )

            description = html.escape(
                " ".join(description.split())[:190]
            )

            price = html.escape(
                format_price(row.get("selling_price"))
            )

            try:
                inventory = float(
                    row.get("inventory_quantity") or 0
                )
            except (TypeError, ValueError):
                inventory = 0

            if inventory > 0:
                stock_label = "● In stock"
                stock_class = "cq-stock-in"
            else:
                stock_label = "● Out of stock"
                stock_class = "cq-stock-out"

            try:
                score = (
                    f"Similarity "
                    f"{float(row.get('similarity_score')):.3f}"
                )
            except (ValueError, TypeError):
                score = "Catalogue match"

            record_id = html.escape(
                safe_value(row.get("source_record_id"))
            )

            cards.append(f"""
            <article class="cq-product-card">
                <div class="cq-product-top">
                    <span class="cq-product-index">
                        PRODUCT {number:02d}
                    </span>
                    <span class="cq-stock {stock_class}">
                        {stock_label}
                    </span>
                </div>

                <div class="cq-product-name">{title}</div>

                <div class="cq-price">{price}</div>

                <div class="cq-product-description">
                    {description or "Product details available in catalogue."}
                </div>

                <div class="cq-product-bottom">
                    <span class="cq-muted">{record_id}</span>
                    <span class="cq-score">{html.escape(score)}</span>
                </div>
            </article>
            """)

        return (
            '<div class="cq-product-grid">'
            + "".join(cards)
            + '</div>'
        )

    # -----------------------------------------------------
    # Chat rendering
    # -----------------------------------------------------

    def chat_html(history):

        messages = [("assistant", WELCOME)] + list(history or [])
        rendered = []

        for role, message in messages:

            safe = html.escape(str(message))
            safe = safe.replace("\n", "<br>")
            safe = re.sub(
                r"\*\*(.+?)\*\*",
                r"<strong>\1</strong>",
                safe
            )

            if role == "user":
                rendered.append(
                    '<div class="cq-msg user">'
                    f'<div class="cq-bubble">{safe}</div>'
                    '</div>'
                )
            else:
                rendered.append(
                    '<div class="cq-msg">'
                    '<div class="cq-msg-icon">✦</div>'
                    f'<div class="cq-bubble">{safe}</div>'
                    '</div>'
                )

        return (
            '<div class="cq-messages">'
            + "".join(reversed(rendered))
            + '</div>'
        )

    # -----------------------------------------------------
    # Main query callback
    # -----------------------------------------------------

    def search(question, catalogue_id, top_k, history):

        history = list(history or [])

        if not question or not question.strip():
            return (
                stats_html(catalogue_id),
                cards_html(None),
                chat_html(history),
                history,
                ""
            )

        question = question.strip()
        history.append(("user", question))

        try:

            with query_lock:
                response = catalogiq_app.ask(
                    catalogue_id=catalogue_id,
                    question=question,
                    top_k=int(top_k)
                )

            if response.get("status") != "success":

                error = str(
                    response.get("errors", "Unknown error")
                )

                history.append((
                    "assistant",
                    f"Search could not be completed: {error}"
                ))

                return (
                    stats_html(catalogue_id),
                    cards_html(None),
                    chat_html(history),
                    history,
                    ""
                )

            raw_records = response.get("records", [])

            if isinstance(raw_records, pd.DataFrame):
                records_df = raw_records.copy()
            else:
                records_df = pd.DataFrame(raw_records)

            matching = response.get(
                "matching_records",
                len(records_df)
            )

            displayed = response.get(
                "displayed_records",
                len(records_df)
            )

            mode = response.get(
                "retrieval_mode",
                "unknown"
            )

            answer = response.get(
                "answer",
                "No AI answer was generated."
            )

            history.append(("assistant", answer))

            history.append((
                "assistant",
                f"Search complete · {matching} matching products · "
                f"{displayed} displayed · {mode.title()} retrieval"
            ))

            return (
                stats_html(catalogue_id),
                cards_html(records_df),
                chat_html(history),
                history,
                ""
            )

        except Exception as error:

            history.append((
                "assistant",
                f"Application error: {error}"
            ))

            return (
                stats_html(catalogue_id),
                cards_html(None),
                chat_html(history),
                history,
                ""
            )

    # -----------------------------------------------------
    # Quick prompts and controls
    # -----------------------------------------------------

    def clear_chat(catalogue_id):

        return (
            stats_html(catalogue_id),
            cards_html(None),
            chat_html([]),
            [],
            ""
        )

    # -----------------------------------------------------
    # Static layout components
    # -----------------------------------------------------

    logo = """
    <div class="cq-logo">
        <div class="cq-logo-mark">IQ</div>
        <div class="cq-logo-text">Catalog<span>IQ</span></div>
    </div>
    <div class="cq-side-label">WORKSPACE</div>
    """

    title = """
    <div class="cq-main-heading">
        <h1>AI-Powered Product Intelligence Platform</h1>
        <p>Real-time catalogue insights and product discovery</p>
    </div>
    """

    product_heading = """
    <div class="cq-section">
        <span class="cq-section-dot"></span>
        <h2>Product Intelligence Deep-Dive</h2>
        <small>Catalogue results</small>
    </div>
    """

    chat_heading = """
    <div class="cq-chat-heading">
        <div class="cq-chat-avatar">✦</div>
        <div>
            <b>AI Analyst</b>
            <small>Ask about your catalogue data</small>
        </div>
        <div class="cq-chat-status">● ONLINE</div>
    </div>
    """

    # =====================================================
    # CREATE GRADIO APP
    # =====================================================

    with gr.Blocks(
        theme=gr.themes.Base(
            primary_hue="blue",
            secondary_hue="indigo",
            neutral_hue="slate"
        ),
        css=CSS,
        title="CatalogIQ | Product Intelligence",
        elem_id="catalogiq-app"
    ) as demo:

        history_state = gr.State([])

        with gr.Row(
            elem_id="cq-shell",
            equal_height=False
        ):

            # ---------------------------------------------
            # LEFT SIDEBAR
            # ---------------------------------------------

            with gr.Column(
                scale=2,
                min_width=238,
                elem_id="cq-side"
            ):

                gr.HTML(logo)

                gr.HTML("""
                <div class="cq-sidebar-card">
                    <div style="
                        height:38px;width:38px;
                        margin:0 auto 11px;
                        border-radius:11px;
                        background:#182943;
                        display:flex;
                        align-items:center;
                        justify-content:center;
                        color:#62c9ed;
                        font-size:18px;
                    ">⌕</div>
                    <b>Product Intelligence</b>
                    <small>Semantic + structured catalogue search</small>
                </div>
                """)

                gr.HTML('<div class="cq-side-label">ACTIVE CATALOGUE</div>')

                catalogue = gr.Dropdown(
                    choices=catalogue_choices,
                    value=default_catalogue_id,
                    label="",
                    show_label=False,
                    interactive=True
                )

                sidebar_health = gr.HTML(
                    sidebar_summary(default_catalogue_id)
                )

                gr.HTML('<div class="cq-side-label">QUICK PROMPTS</div>')

                quick_buttons = []

                for prompt in QUICK_PROMPTS:
                    button = gr.Button(
                        prompt,
                        size="sm",
                        elem_classes=["cq-quick"]
                    )
                    quick_buttons.append(button)

                gr.HTML('<div class="cq-side-label">RESULT SETTINGS</div>')

                top_k = gr.Slider(
                    minimum=1,
                    maximum=10,
                    value=5,
                    step=1,
                    label="Products to display"
                )

                clear_btn = gr.Button(
                    "Clear conversation",
                    size="sm",
                    elem_classes=["cq-clear"]
                )

                gr.HTML("""
                <div class="cq-sidebar-card">
                    <b>How CatalogIQ works</b>
                    <small>
                        Combines semantic retrieval, structured filters
                        and dynamically extracted product attributes
                        to answer catalogue questions.
                    </small>
                </div>
                """)

            # ---------------------------------------------
            # CENTRE DASHBOARD
            # ---------------------------------------------

            with gr.Column(
                scale=7,
                min_width=480,
                elem_id="cq-main"
            ):

                gr.HTML(title)

                kpis = gr.HTML(
                    stats_html(default_catalogue_id)
                )

                gr.HTML(product_heading)

                products = gr.HTML(cards_html(None))

            # ---------------------------------------------
            # RIGHT AI ANALYST PANEL
            # ---------------------------------------------

            with gr.Column(
                scale=3,
                min_width=330,
                elem_id="cq-chat"
            ):

                gr.HTML(chat_heading)

                chat = gr.HTML(
                    chat_html([])
                )

                with gr.Column(
                    elem_classes=["cq-chat-footer"]
                ):

                    question = gr.Textbox(
                        label="",
                        show_label=False,
                        placeholder=(
                            "Ask about prices, stock, materials..."
                        ),
                        lines=2,
                        max_lines=4
                    )

                    with gr.Row():
                        send = gr.Button(
                            "Send  ➤",
                            variant="primary",
                            elem_classes=["cq-send"]
                        )

                    clear_chat_button = gr.Button(
                        "Clear chat history",
                        size="sm",
                        elem_classes=["cq-chat-clear"]
                    )

        # =================================================
        # EVENT WIRING
        # =================================================

        inputs = [
            question,
            catalogue,
            top_k,
            history_state
        ]

        outputs = [
            kpis,
            products,
            chat,
            history_state,
            question
        ]

        send.click(
            fn=search,
            inputs=inputs,
            outputs=outputs
        )

        question.submit(
            fn=search,
            inputs=inputs,
            outputs=outputs
        )

        # Quick prompt fills the chat input.
        for button, prompt in zip(
            quick_buttons,
            QUICK_PROMPTS
        ):
            button.click(
                fn=lambda p=prompt: p,
                inputs=None,
                outputs=question
            )

        # Update dashboard when catalogue changes.
        def refresh_catalogue(selected_id):
            return (
                stats_html(selected_id),
                sidebar_summary(selected_id),
                cards_html(None),
                chat_html([])
            )

        catalogue.change(
            fn=refresh_catalogue,
            inputs=catalogue,
            outputs=[
                kpis,
                sidebar_health,
                products,
                chat
            ]
        )

        clear_btn.click(
            fn=clear_chat,
            inputs=catalogue,
            outputs=outputs
        )

        clear_chat_button.click(
            fn=lambda h: (
                chat_html([]),
                [],
                ""
            ),
            inputs=history_state,
            outputs=[
                chat,
                history_state,
                question
            ]
        )

    return demo
