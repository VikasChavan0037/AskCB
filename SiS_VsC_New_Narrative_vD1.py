import json
import html
import base64
from pathlib import Path
from functools import lru_cache
from typing import Optional

import pandas as pd
import streamlit as st
import _snowflake
from snowflake.snowpark.context import get_active_session

try:
    from centrIQ_logo_base64 import CENTRIQ_LOGO_BASE64 as LOGO_FALLBACK_BASE64
except Exception:
    LOGO_FALLBACK_BASE64 = ""

# ==========================================================
# CONFIG
# ==========================================================

DB_NAME = "CB_ASKCENTRIC_DB"
SCHEMA_NAME = "CORTEX_SCHEMA"
AGENT_NAME = "ASKCENTRIC_AGENT"

API_ENDPOINT = f"/api/v2/databases/{DB_NAME}/schemas/{SCHEMA_NAME}/agents/{AGENT_NAME}:run"
API_TIMEOUT_MS = 600000  # 10 minutes

NARRATIVE_MODEL = "openai-gpt-4.1"
REWRITE_MODEL = "openai-gpt-4.1"
MAX_ROWS_FOR_LLM = 50


# ==========================================================
# LOGO HANDLING
# ==========================================================

# Embedded CentrIQ logo (SVG) so the app remains fully single-file deployable.
# Embedded CentrIQ logo (SVG) so the app remains fully single-file deployable.
EMBEDDED_CENTRIQ_LOGO_BASE64 = """
PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI1MTIiIGhlaWdodD0iNTEyIiB2aWV3Qm94PSIwIDAgNTEyIDUxMiI+CgAgPGRlZnM+CiAgICA8bGluZWFyR3JhZGllbnQgaWQ9ImJnIiB4MT0iMCIgeDI9IjAiIHkxPSIwIiB5Mj0iMSI+CiAgICAgIDxzdG9wIG9mZnNldD0iMCUiIHN0b3AtY29sb3I9IiMwYjBjMTAiIC8+CiAgICAgIDxzdG9wIG9mZnNldD0iMTAwJSIgc3RvcC1jb2xvcj0iIzExMTgyNyIgLz4KICAgIDwvbGluZWFyR3JhZGllbnQ+CiAgPC9kZWZzPgogIDxyZWN0IHdpZHRoPSI1MTIiIGhlaWdodD0iNTEyIiByeD0iMzIiIGZpbGw9InVybCgjYmcpIiAvPgogIDxnIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzAwQUVFRiIgc3Ryb2tlLXdpZHRoPSIyNiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj4KICAgIDxwYXRoIGQ9Ik0xMjggMTg2bDY0IDM2IiAvPgogICAgPHBhdGggZD0iTTE5MiAxNTBsNjQtMzYiIC8+CiAgICA8cGF0aCBkPSJNMjU2IDExNGw2NCAzNiIgLz4KICAgIDxwYXRoIGQ9Ik0xOTIgMjIybDY0IDM2IiAvPgogICAgPHBhdGggZD0iTTI1NiAyNThsNjQtMzYiIC8+CiAgPC9nPgogIDxnIGZpbGw9IiMwMEFFRUYiIHN0cm9rZT0iIzAwQUVFRiIgc3Ryb2tlLXdpZHRoPSIxMCI+CiAgICA8Y2lyY2xlIGN4PSIxMjgiIGN5PSIxODYiIHI9IjM0IiAvPgogICAgPGNpcmNsZSBjeD0iMTkyIiBjeT0iMTUwIiByPSMzNCIgLz4KICAgIDxjaXJjbGUgY3g9IjI1NiIgY3k9IjExNCIgcj0iMzQiIC8+CiAgICA8Y2lyY2xlIGN4PSIyNTYiIGN5PSIyNTgiIHI9IjM0IiAvPgogICAgPGNpcmNsZSBjeD0iMzIwIiBjeT0iMjIyIiByPSIzNCIgLz4KICA8L2c+CiAgPGcgZm9udC1mYW1pbHk9IidNYW5yb3BlJywgJ1NlZ29lIFVJJywgQXJpYWwiIGZvbnQtc2l6ZT0iOTIiIGZvbnQtd2VpZ2h0PSI3MDAiIGxldHRlci1zcGFjaW5nPSItMSIgPgogICAgPHRleHQgeD0iOTIiIHk9IjM2MCIgZmlsbD0iI2ZmZmZmZiI+Q2VudHI8L3RleHQ+CiAgICA8dGV4dCB4PSIzMjAiIHk9IjM2MCIgZmlsbD0iIzAwQUVFRiI+SVE8L3RleHQ+CiAgPC9nPgo8L3N2Zz4=
"""

## Strip whitespace from the embedded asset to keep the data URI valid across platforms
EMBEDDED_CENTRIQ_LOGO_BASE64 = "".join(EMBEDDED_CENTRIQ_LOGO_BASE64.split())

STAGE_LOGO_PATH = (
    "snow://streamlit/CB_ASKCENTRIC_DB.CORTEX_SCHEMA.YP90S_178G0C7CJD/versions/live/image (7).png"
)


def _validate_b64(data: str) -> Optional[str]:
    """Return a clean base64 string if it decodes, otherwise None."""

    if not data:
        return None

    try:
        base64.b64decode(data)
    except Exception:
        return None

    return data.strip()


def _load_stage_logo_base64() -> Optional[str]:
    """Try to read the staged logo file from Snowflake Streamlit storage."""

    try:
        session = get_active_session()
    except Exception:
        return None

    try:
        with session.file.get_stream(STAGE_LOGO_PATH) as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None


def load_logo_base64():
    """Return the CentrIQ logo as base64, preferring embedded and module fallbacks."""

    stage_logo = _load_stage_logo_base64()

    for candidate in (
        stage_logo,
        EMBEDDED_CENTRIQ_LOGO_BASE64,
        LOGO_FALLBACK_BASE64,
    ):
        valid = _validate_b64(candidate)
        if valid:
            return valid

    for local_name in ("image (7).png", "centrIQ_logo.png"):
        logo_path = Path(__file__).parent / local_name
        if logo_path.exists():
            try:
                return base64.b64encode(logo_path.read_bytes()).decode("utf-8")
            except Exception:
                continue

    return ""


CENTRIQ_LOGO_BASE64 = load_logo_base64()


# ==========================================================
# LANDING SUBMIT HANDLER
# ==========================================================


def submit_landing():
    """Placeholder; kept for compatibility (not used for rerun to avoid no-op)."""
    pass


# ==========================================================
# HELPERS: AGENT CALL + SSE PARSING + THREADS
# ==========================================================

def parse_sse(raw: str):
    """Parse text/event-stream into a list of {event, data} dicts."""
    events = []
    current = {"event": None, "data": []}

    for line in raw.splitlines():
        line = line.rstrip("\n")

        # Blank line = end of event
        if not line:
            if current["event"] is not None:
                data_str = "\n".join(current["data"])
                try:
                    obj = json.loads(data_str)
                except Exception:
                    obj = data_str
                events.append({"event": current["event"], "data": obj})
                current = {"event": None, "data": []}
            continue

        if line.startswith("event:"):
            current["event"] = line.split("event:", 1)[1].strip()
        elif line.startswith("data:"):
            current["data"].append(line.split("data:", 1)[1].strip())

    # Flush last event if needed
    if current["event"] and current["data"]:
        data_str = "\n".join(current["data"])
        try:
            obj = json.loads(data_str)
        except Exception:
            obj = data_str
        events.append({"event": current["event"], "data": obj})

    return events


def create_thread():
    """Create a Cortex thread and return its ID (int or None)."""
    resp = _snowflake.send_snow_api_request(
        "POST",
        "/api/v2/cortex/threads",
        {},
        {},
        {"origin_application": "askcentric_sis"},
        None,
        30000,
    )
    content = resp.get("content")

    if isinstance(content, str):
        try:
            return int(content)
        except ValueError:
            try:
                return int(json.loads(content))
            except Exception:
                return None

    if isinstance(content, dict):
        tid = content.get("thread_id") or content.get("id")
        if tid is not None:
            try:
                return int(tid)
            except Exception:
                return None

    return None


def call_agent(question_text, thread_id=None, parent_message_id=None):
    """
    Send a single user message to the Cortex agent (thread-aware).
    Returns (events, assistant_message_id, error_string_or_None).
    """
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": question_text},
            ],
        }
    ]

    body = {
        "messages": messages,
        "stream": True,
    }

    if thread_id is not None and parent_message_id is not None:
        body["thread_id"] = thread_id
        body["parent_message_id"] = parent_message_id

    try:
        resp = _snowflake.send_snow_api_request(
            "POST",
            API_ENDPOINT,
            {},
            {},
            body,
            None,
            API_TIMEOUT_MS,
        )
    except Exception as e:
        return [], None, f"Agent call failed: {e}"

    content = resp.get("content")

    if isinstance(content, list):
        events = content
    elif isinstance(content, str):
        try:
            parsed = json.loads(content)
        except Exception:
            parsed = None
        if isinstance(parsed, list):
            events = parsed
        else:
            events = parse_sse(content)
    else:
        return [], None, "Unexpected response format from agent"

    # Extract assistant message_id from metadata events
    assistant_msg_id = None
    for ev in events:
        if ev.get("event") == "metadata":
            data = ev.get("data") or {}
            if data.get("role") == "assistant":
                assistant_msg_id = data.get("message_id")

    return events, assistant_msg_id, None


# ==========================================================
# EXTRACTION HELPERS (SQL, TEXT, THINKING)
# ==========================================================

def extract_sql(events):
    """Scan events recursively for 'sql' keys; return last SQL string or None."""
    sqls = []

    def walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k.lower() == "sql" and isinstance(v, str):
                    sqls.append(v)
                else:
                    walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    for ev in events:
        walk(ev.get("data"))

    return sqls[-1] if sqls else None


def extract_answer_text(events):
    """Rebuild natural-language answer from response.text.delta + final response."""
    chunks = []

    for ev in events:
        name = ev.get("event")
        data = ev.get("data") or {}

        if name == "response.text.delta":
            t = data.get("text")
            if isinstance(t, str):
                chunks.append(t)

        if name == "response" and isinstance(data, dict):
            content = data.get("content", [])
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    t = part.get("text")
                    if isinstance(t, str):
                        chunks.append(t)

    return "".join(chunks).strip()


def extract_thinking(events):
    """Collect response.thinking.delta into a single markdown string."""
    chunks = []
    for ev in events:
        if ev.get("event") == "response.thinking.delta":
            data = ev.get("data") or {}
            t = data.get("text")
            if isinstance(t, str):
                chunks.append(t)
    return "".join(chunks).strip()


# ==========================================================
# STRUCTURED CONTEXT + FOLLOW-UP SUGGESTIONS
# ==========================================================

def build_context_from_df(question, sql, df: pd.DataFrame):
    """
    Build a shallow context object from the last result set:
    - metric / metric_label
    - dims_available
    - time_col / time_grain
    (Filters are left empty for now.)
    """
    if df is None or df.empty:
        return None

    numeric_cols = list(df.select_dtypes(include="number").columns)
    metric_col = None
    if numeric_cols:
        preferred = ["total_sales", "sales", "ship_dollars", "revenue", "amount", "value"]
        metric_col = numeric_cols[0]
        for c in numeric_cols:
            if str(c).lower() in preferred:
                metric_col = c
                break

    non_numeric_cols = [c for c in df.columns if c not in numeric_cols]

    time_col = None
    time_candidates = [
        c for c in df.columns
        if any(tok in str(c).lower() for tok in ["date", "month", "year", "week"])
    ]
    if time_candidates:
        time_col = time_candidates[0]

    dims_available = []
    for c in non_numeric_cols:
        cl = str(c).lower()
        if time_col and cl == str(time_col).lower():
            continue
        dims_available.append(c)

    time_grain = None
    if time_col:
        cl = str(time_col).lower()
        if "month" in cl:
            time_grain = "month"
        elif "week" in cl:
            time_grain = "week"
        elif "date" in cl or "day" in cl:
            time_grain = "day"
        elif "year" in cl:
            time_grain = "year"

    metric_label = None
    if metric_col:
        if "ship" in str(metric_col).lower():
            metric_label = "Total Sales"
        else:
            metric_label = str(metric_col)

    ctx = {
        "question": question,
        "sql": sql,
        "metric": metric_col,
        "metric_label": metric_label,
        "time_col": time_col,
        "time_grain": time_grain,
        "dims_available": dims_available,
        "filters": {},
    }
    return ctx


def suggest_followups(context):
    """
    Generate 3–5 follow-up question suggestions from context.
    """
    if not context:
        return []

    metric_label = context.get("metric_label") or context.get("metric") or "this metric"
    dims = [str(d) for d in (context.get("dims_available") or [])]
    lower_dims = [d.lower() for d in dims]

    suggestions = []

    def add(q):
        if q not in suggestions:
            suggestions.append(q)

    for d, dl in zip(dims, lower_dims):
        if "brand" in dl:
            add(f"What is {metric_label} by {d}?")
            add(f"Which {d} has the highest {metric_label}?")
        if "channel" in dl:
            add(f"How does {metric_label} vary by {d}?")
        if "country" in dl or "region" in dl:
            add(f"What is {metric_label} by {d}?")
        if "category" in dl or "segment" in dl:
            add(f"Break down {metric_label} by {d}.")
        if "mvp_business_stream" in dl or "business_stream" in dl or "stream" in dl:
            add(f"Compare {metric_label} across {d}.")

    time_col = context.get("time_col")
    time_grain = context.get("time_grain")
    if time_col:
        grain_label = time_grain or "time"
        add(f"How does {metric_label} trend by {grain_label}?")

    if metric_label:
        add(f"How does {metric_label} compare to last year?")

    return suggestions[:5]


# ==========================================================
# LLM PRE-PROCESSOR: QUESTION REWRITING WITH CONTEXT
# ==========================================================

def rewrite_question_with_context(session, turns, context, new_question, is_followup=False):
    """
    Use SNOWFLAKE.CORTEX.COMPLETE to rewrite the new question into a
    fully self-contained analytic question, optionally reusing context
    from the last 1–2 QA turns.

    is_followup=True is used when the question comes from our own
    suggested follow-up chips.
    """
    if not turns or not context:
        return new_question

    # Last 2 turns for Q/A context
    recent = turns[-2:]
    qa_lines = []
    for i, t in enumerate(recent, start=1):
        q = (t.get("question") or "").strip()
        a = (t.get("answer") or "").strip()
        if q:
            qa_lines.append(f"{i}) Q: {q}")
        if a:
            qa_lines.append(f"{i}) A: {a}")

    context_block = "\n".join(qa_lines)
    context_json = json.dumps(context, ensure_ascii=False)
    followup_flag = "YES" if is_followup else "MAYBE"

    prompt = (
        "You are an analytics assistant that rewrites user questions so that a "
        "separate text-to-SQL agent can interpret them correctly.\n\n"
        "You are given:\n"
        "1) Some previous Q&A context from the conversation.\n"
        "2) A structured context object (JSON) describing the last query's metric, "
        "dimensions, and time window.\n"
        "3) The user's NEW question.\n\n"
        "Your job is to decide whether the new question is:\n"
        "- A FOLLOW-UP to the previous answer (e.g., 'slice it by brand', "
        "'drill down by country', 'what about footwear?'), or\n"
        "- A NEW, INDEPENDENT analytic question.\n\n"
        f"Follow-up hint: {followup_flag} (if YES, you MUST treat it as a follow-up; "
        "if MAYBE, decide based on the text).\n\n"
        "If it is clearly a follow-up, you should:\n"
        "- Reuse the relevant metric, filters, and time window from the previous answer.\n"
        "- Rewrite the new question into a fully self-contained sentence that includes those details.\n\n"
        "If it looks like a new independent question, you should:\n"
        "- NOT carry over previous category/brand filters unless they are explicitly mentioned.\n"
        "- Rewrite the new question as-is, maybe clarifying metric names if needed, but do NOT force "
        "filters like 'Accessories' or previous brands/categories.\n\n"
        "Important:\n"
        "- Your output will be sent directly to a text-to-SQL agent.\n"
        "- DO NOT add extra explanation, JSON, or commentary.\n"
        "- Respond with ONLY the final rewritten question as plain text.\n\n"
        "Previous Q&A context:\n"
        f"{context_block}\n\n"
        "Structured context JSON:\n"
        f"{context_json}\n\n"
        "User's new question:\n"
        f"{new_question}\n\n"
        "Now rewrite the new question into a single, clear, self-contained analytic question:\n"
    )

    prompt_sql = prompt.replace("'", "''")

    sql = (
        "SELECT SNOWFLAKE.CORTEX.COMPLETE("
        f"'{REWRITE_MODEL}', "
        f"'{prompt_sql}'"
        ") AS RESP"
    )

    try:
        row = session.sql(sql).collect()[0]
        resp = row["RESP"]
    except Exception:
        return new_question

    try:
        if isinstance(resp, str):
            text = resp.strip()
        elif isinstance(resp, dict):
            text = (resp.get("output_text") or resp.get("text") or json.dumps(resp))
            text = str(text).strip()
        else:
            text = str(resp).strip()
    except Exception:
        return new_question

    if not text:
        return new_question

    return text


# ==========================================================
# LLM NARRATIVE + CHART CONFIG (DATA-ONLY)
# ==========================================================

def get_llm_narrative_and_chart(session, question, df: pd.DataFrame):
    """
    Call SNOWFLAKE.CORTEX.COMPLETE to get:
    - narrative (markdown bullets + summary)
    - chart_type (bar | line | area | scatter)
    - x, y
    - aggregate (sum | avg | none)
    """
    if df is None or df.empty:
        return None

    sample = df.head(MAX_ROWS_FOR_LLM)
    records = json.loads(sample.to_json(orient="records", date_format="iso"))
    meta = [{"name": c, "dtype": str(sample[c].dtype)} for c in sample.columns]

    payload = {
        "question": question,
        "columns": meta,
        "rows": records,
    }
    payload_json = json.dumps(payload, ensure_ascii=False)

    prompt = (
        "You are a senior data analyst.\n\n"
        "You are given a tabular query result as JSON with:\n"
        "- 'columns': list of column names and dtypes\n"
        "- 'rows': sample rows\n\n"
        "Here is the JSON for the result set:\n"
        + payload_json +
        "\n\nThe user question is:\n"
        + question +
        "\n\nYour job:\n"
        "1) Carefully inspect ONLY the columns and rows provided in this JSON.\n"
        "2) Infer which numeric columns are most relevant to the user's question.\n"
        "3) Describe patterns, trends, spikes, drops, best/worst performers, etc.\n"
        "4) Always base your reasoning on the actual data values in the JSON.\n\n"
        "Important constraints:\n"
        "- DO NOT mention or assume any metric or column that is not present in the JSON.\n"
        "- If the user asks for 'sales', 'revenue', or similar terms, map them to the most appropriate\n"
        "  numeric column(s) in the result (for example, the largest or most obviously related metric).\n"
        "- NEVER say that a metric is missing or not available. Instead, explain what metrics ARE present\n"
        "  and how they relate to the user's question.\n"
        "- All numbers you quote must come from the data in the JSON.\n\n"
        "You must also propose a single chart configuration to visualize this result set:\n"
        "- chart_type: one of 'bar', 'line', 'area', 'scatter'\n"
        "  - Use 'line' when there is an obvious time dimension (e.g., dates, months).\n"
        "  - Use 'bar' when comparing categories (e.g., brand, country, product).\n"
        "  - Use 'area' for cumulative or volume-over-time views.\n"
        "  - Use 'scatter' for relationships between two numeric metrics.\n"
        "- x: name of the column for the x-axis.\n"
        "- y: name of the primary numeric metric for the y-axis.\n"
        "- aggregate: 'sum', 'avg', or 'none' (for pre-aggregated data).\n\n"
        "Format the narrative as MARKDOWN BULLETS plus a short summary. For example:\n"
        "- **Total metric in 2025:** 12.3M\n"
        "- **Best month by metric:** March 2025 – 2.1M\n"
        "- **Weakest month:** July 2025 – 0.8M\n"
        "- **Seasonality:** Q4 is ~35% higher than Q1.\n\n"
        "**Summary:** 1–2 line overall conclusion.\n\n"
        "Respond ONLY with a JSON object of the form:\n"
        "{\n"
        '  "narrative": "markdown bullet list with a short summary at the end",\n'
        '  "chart_type": "bar | line | area | scatter",\n'
        '  "x": "column_name_for_x_axis",\n'
        '  "y": "column_name_for_y_axis",\n'
        '  "aggregate": "sum | avg | none"\n'
        "}\n"
    )

    prompt_sql = prompt.replace("'", "''")

    sql = (
        "SELECT SNOWFLAKE.CORTEX.COMPLETE("
        f"'{NARRATIVE_MODEL}', "
        f"'{prompt_sql}'"
        ") AS RESP"
    )

    try:
        row = session.sql(sql).collect()[0]
        resp = row["RESP"]
    except Exception:
        return None

    # Parse JSON and normalize narrative
    try:
        if isinstance(resp, str):
            obj = json.loads(resp)
        elif isinstance(resp, dict):
            out = resp.get("output_text") or resp.get("text")
            if out:
                obj = json.loads(out)
            else:
                obj = resp
        else:
            obj = json.loads(str(resp))
    except Exception:
        return None

    narrative = obj.get("narrative")

    if isinstance(narrative, list):
        narrative = "\n".join(str(x) for x in narrative)
    elif not isinstance(narrative, str):
        narrative = str(narrative)

    narrative = narrative.replace("\r", "").strip()
    obj["narrative"] = narrative

    return obj


# ==========================================================
# CHART & SUMMARY HELPERS
# ==========================================================

def build_chart_df_with_agg(df: pd.DataFrame, x, y, agg):
    if df is None or df.empty or not x or not y:
        return None
    if x not in df.columns or y not in df.columns:
        return None

    out = df[[x, y]].copy()

    if agg == "sum":
        out = out.groupby(x, as_index=False)[y].sum()
    elif agg == "avg":
        out = out.groupby(x, as_index=False)[y].mean()

    if not pd.api.types.is_numeric_dtype(out[y]):
        return None

    return out.set_index(x)


def render_chart(df: pd.DataFrame, chart_type, container):
    if df is None or df.empty:
        return
    if not chart_type:
        chart_type = "bar"
    chart_type = str(chart_type).lower()

    if chart_type == "line":
        container.line_chart(df)
    elif chart_type == "area":
        container.area_chart(df)
    elif chart_type == "scatter":
        container.scatter_chart(df)
    else:
        container.bar_chart(df)


def simple_summary(question: str, df: Optional[pd.DataFrame]) -> str:
    """Basic bullet-style summary when LLM narrative isn't available."""
    if df is None:
        return f"No data available for: **{question}**."

    if df.empty:
        return (
            f"For **{question}**, the query ran successfully "
            f"but returned **no rows**. Please check filters/date range."
        )

    bullets = [f"- **Rows returned:** {len(df)}"]

    numeric_cols = list(df.select_dtypes(include="number").columns)
    if numeric_cols:
        m = numeric_cols[0]
        total_val = float(df[m].sum())
        avg_val = float(df[m].mean())
        bullets.append(f"- **Total `{m}`:** {total_val:,.2f}")
        bullets.append(f"- **Average `{m}` per row:** {avg_val:,.2f}")

    return f"For your question **{question}**, here is a quick overview:\n\n" + "\n".join(bullets)


# ==========================================================
# TURN RENDERING (PERSISTENCE + SUGGESTIONS)
# ==========================================================


def format_answer_html(answer: str) -> str:
    """Render a plain-text/markdown-ish answer into HTML with bullet support."""
    lines = [ln.rstrip() for ln in answer.splitlines()]
    blocks = []
    bullet_buf = []

    def flush_bullets():
        nonlocal bullet_buf
        if bullet_buf:
            items = "".join(f"<li>{html.escape(item)}</li>" for item in bullet_buf)
            blocks.append(f"<ul>{items}</ul>")
            bullet_buf = []

    for ln in lines:
        stripped = ln.strip()
        if stripped:
            if stripped[0] in {"-", "•", "*"}:
                payload = stripped[1:].lstrip()
                bullet_buf.append(payload if payload else stripped[0])
            else:
                flush_bullets()
                blocks.append(f"<p>{html.escape(stripped)}</p>")
        else:
            flush_bullets()
    flush_bullets()

    if not blocks:
        return html.escape(answer)

    return "".join(blocks)


def render_turn(turn, session, turn_index):
    """
    Render a single historic turn (user + assistant) from stored state,
    including suggested follow-up questions.
    """
    question = turn.get("question", "")
    answer = turn.get("answer", "")
    thinking = turn.get("thinking", "")
    sql = turn.get("sql")
    df_records = turn.get("df_records")
    df_columns = turn.get("df_columns")
    chart_cfg = turn.get("chart_cfg")
    context = turn.get("context")

    assistant_avatar = data_uri_logo() or "💬"

    # USER
    with st.chat_message("user", avatar=_user_avatar()):
        st.markdown(f"<div class='bubble bubble-user'>{question}</div>", unsafe_allow_html=True)

    # ASSISTANT
    with st.chat_message("assistant", avatar=assistant_avatar):

        # Narrative
        if answer:
            answer_html = format_answer_html(answer)
            st.markdown(
                f"<div class='bubble bubble-assistant'>{answer_html}</div>",
                unsafe_allow_html=True,
            )

        # Suggested follow-up questions
        suggestions = suggest_followups(context)
        if suggestions:
            st.markdown("<div class='chip-row'>", unsafe_allow_html=True)
            for i, s in enumerate(suggestions):
                if st.button(s, key=f"suggest_{turn_index}_{i}"):
                    st.session_state["pending_question"] = s
                    st.session_state["pending_is_followup"] = True
                    st.session_state["view_mode"] = "Conversation"
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)


# ==========================================================
# STREAMLIT APP
# ==========================================================

st.set_page_config(
    page_title="CentrIQ — NLQ Insights Assistant",
    layout="wide",
    page_icon="💬",
)

# Brand palette + font
CENTRIC_NAVY = "#002A5C"  # approx Centric signature navy
CENTRIC_DARK = "#101010"  # Cod Gray from brand tools
CENTRIQ_BLUE = "#00AEEF"  # approx from CentrIQ logo


@lru_cache(maxsize=1)
def _user_avatar():
    return (
        "data:image/svg+xml;base64,"
        + base64.b64encode(
            """
            <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
              <circle cx="32" cy="32" r="30" fill="#002A5C"/>
              <text x="32" y="40" font-family="Arial, sans-serif" font-size="28" fill="#ffffff" text-anchor="middle">U</text>
            </svg>
            """
            .strip()
            .encode("utf-8")
        ).decode("ascii")
    )


st.markdown(
    f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&display=swap');

        body, p, li, div {{
            color: {CENTRIC_DARK};
            font-family: 'Manrope', system-ui, -apple-system, sans-serif;
        }}

        /* Elevated top ribbon */
        .top-ribbon {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            background: linear-gradient(90deg, #ffffff 0%, #f5f7fb 100%);
            border: 1px solid #e5e7eb;
            border-radius: 16px;
            padding: 0.65rem 1rem;
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.05);
            margin-bottom: 0.15rem;
        }}
        .top-left {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}
        .top-logo {{
            width: 60px;
            height: 60px;
            border-radius: 14px;
            border: 1px solid #e5e7eb;
            object-fit: contain;
            background: #ffffff;
            padding: 6px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
        }}
        .top-logo-placeholder {{
            width: 60px;
            height: 60px;
            border-radius: 14px;
            border: 1px solid #e5e7eb;
            background: #eef2f7;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            color: {CENTRIC_NAVY};
        }}

        /* Landing hero */
        .landing-container {{
            min-height: 22vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 0.9rem;
            text-align: center;
            padding-top: 0.05rem;
        }}
        .landing-logo {{
            width: 110px;
            height: 110px;
            border-radius: 999px;
            border: 1px solid #e5e7eb;
            object-fit: contain;
            background: #ffffff;
            padding: 14px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
        }}
        .landing-title {{
            font-size: 1.6rem;
            font-weight: 600;
            color: #6b6c7a;
            letter-spacing: 0.02em;
        }}
        .landing-sub {{
            font-size: 0.98rem;
            color: #6b6c7a;
            max-width: 760px;
            line-height: 1.5;
        }}
        .landing-chip-row {{
            margin-top: 0.75rem;
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 0.35rem;
        }}
        /* Landing input: border around the field itself */
        div[data-testid="stTextInput"]:has(input#landing_query) {{
            width: min(86vw, 960px);
            margin: 0 auto;
            padding: 0;
            border-radius: 12px;
            border: none;
            background: transparent;
            box-shadow: none;
        }}
        div[data-testid="stTextInput"]:has(input#landing_query) > div > div {{
            padding: 0 !important;
            background: transparent !important;
        }}
        input#landing_query {{
            width: 100%;
            border: 2px solid {CENTRIC_NAVY} !important;
            box-shadow: none !important;
            padding: 0.9rem 1rem !important;
            font-size: 1rem !important;
            color: #6b6c7a !important;
            background: #f2f4f8 !important;
            border-radius: 12px !important;
        }}
        .top-title {{
            font-size: 1.25rem;
            font-weight: 700;
            color: {CENTRIC_NAVY};
            margin-bottom: 0.15rem;
        }}
        .top-subtitle {{
            font-size: 0.95rem;
            color: #4b5563;
            margin: 0;
        }}

        .top-ribbon {{
            margin-bottom: 0.4rem;
        }}

        /* Reduce top padding, add breathing room overall */
        .main .block-container {{
            padding-top: 0.05rem;
            padding-bottom: 1.1rem;
            padding-left: 2.2rem;
            padding-right: 2.2rem;
        }}

        /* Header title + subtitle */
        .centriq-title {{
            font-size: 1.5rem;
            font-weight: 700;
            color: {CENTRIC_NAVY};
            margin-bottom: 0.15rem;
        }}
        .centriq-subtitle {{
            font-size: 0.90rem;
            color: #6B7280;
            margin-top: 0.1rem;
        }}

        /* Section headings inside columns */
        .section-title {{
            font-size: 0.85rem;
            font-weight: 600;
            color: {CENTRIC_NAVY};
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 0.15rem;
            margin-top: 0.35rem;
        }}

        /* Chat area cards */
        .chat-wrapper {{
            border-radius: 16px;
            border: none;
            padding: 0.4rem 0.9rem 0.75rem 0.9rem;
            background-color: #ffffff;
            color: {CENTRIC_DARK};
            display: flex;
            flex-direction: column;
            gap: 0.35rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.04);
        }}
        .panel-left, .panel-right {{
            height: calc(100vh - 160px);
            min-height: 520px;
        }}
        .panel-left {{
            display: flex;
            flex-direction: column;
            gap: 0.35rem;
        }}
        .chat-scroll {{
            flex: 1;
            overflow-y: auto;
            padding-right: 0.35rem;
        }}
        .panel-right {{
            display: flex;
            flex-direction: column;
            position: sticky;
            top: 0;
            align-self: flex-start;
        }}
        div[data-testid="stHorizontalBlock"] > div {{
            align-items: flex-start !important;
        }}
        div[data-testid="column"] {{
            display: flex;
            flex-direction: column;
            align-items: stretch;
        }}
        .details-scroll {{
            flex: 1;
            overflow-y: auto;
            padding-right: 0.35rem;
            margin-top: 0.25rem;
            display: flex;
            flex-direction: column;
            gap: 0.45rem;
            max-height: calc(100vh - 320px);
        }}
        .tab-scroll {{
            max-height: calc(100vh - 360px);
            overflow-y: auto;
            padding-right: 0.35rem;
        }}
        /* Trim Streamlit chat container padding */
        div[data-testid="stChatMessage"] {{
            padding: 0.1rem 0;
            background: transparent;
            box-shadow: none;
        }}
        div[data-testid="stChatMessage"] p {{
            margin: 0;
        }}

        /* Right details panel styling */
        .details-panel {{
            border-radius: 16px;
            border: none;
            padding: 0.6rem 0.5rem 0.9rem 0.5rem;
            background-color: #ffffff;
            color: {CENTRIC_DARK};
            box-shadow: 0 4px 12px rgba(0,0,0,0.04);
            height: 100%;
            display: flex;
            flex-direction: column;
        }}
        .panel-right > .details-panel {{ height: 100%; }}

        /* Stretch columns so the details card stays aligned with the chat area */
        div[data-testid="column"] > div:first-child {{
            height: 100%;
            display: flex;
            flex-direction: column;
        }}

        /* Chat bubbles */
        .bubble {{
            border-radius: 14px;
            padding: 0.85rem 1rem;
            max-width: 100%;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.04);
        }}
        .bubble-user {{
            background: #f3f4f6;
            border: 1px solid #e5e7eb;
            align-self: flex-end;
        }}
        .bubble-assistant {{
            background: rgba(0, 174, 239, 0.10);
            border: 1px solid rgba(0, 174, 239, 0.35);
            align-self: flex-start;
        }}

        /* Follow-up chips */
        .chip-row {{
            margin-top: 0.75rem;
            display: flex;
            flex-wrap: wrap;
            gap: 0.2rem;
        }}
        .chip, .chip-row button {{
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 999px;
            border: 1px solid {CENTRIQ_BLUE};
            color: {CENTRIQ_BLUE};
            font-size: 0.78rem;
            margin-right: 0.35rem;
            margin-bottom: 0.35rem;
            background-color: #ECFEFF;
            transition: all 0.15s ease;
            box-shadow: none !important;
        }}
        .chip:hover, .chip-row button:hover {{
            background-color: {CENTRIQ_BLUE};
            color: #ffffff;
            box-shadow: 0 6px 16px rgba(0, 174, 239, 0.25);
        }}
        .chip-row button {{
            cursor: pointer;
            border: 1px solid {CENTRIQ_BLUE} !important;
            background: #ECFEFF;
            color: {CENTRIQ_BLUE};
            border-radius: 999px !important;
        }}
        .chat-wrapper div[data-testid="stButton"] {{
            display: inline-block;
            margin-right: 0.35rem;
            margin-bottom: 0.35rem;
        }}
        .chat-wrapper div[data-testid="stButton"] > button {{
            border-radius: 999px !important;
            padding: 0.25rem 0.75rem;
            background: #ECFEFF;
            border: 1px solid {CENTRIQ_BLUE};
            color: {CENTRIQ_BLUE};
            font-size: 0.78rem;
            box-shadow: none;
            height: auto;
        }}
        .chat-wrapper div[data-testid="stButton"] > button:hover {{
            background-color: {CENTRIQ_BLUE};
            color: #ffffff;
        }}

        /* Keep the chat input docked near bottom of the viewport */
        .chat-bar {{
            position: sticky;
            bottom: 0.2rem;
            left: 0;
            right: 0;
            padding-top: 0.25rem;
            padding-bottom: 0.25rem;
            background: #ffffff;
            z-index: 6;
        }}
        div[data-testid="stTextInput"]:has(input#chat_query) {{
            width: 100%;
            margin: 0;
        }}
        div[data-testid="stTextInput"]:has(input#chat_query) > div > div {{
            padding: 0 !important;
            background: transparent !important;
        }}
        input#chat_query {{
            width: 100%;
            border: 2px solid {CENTRIC_NAVY} !important;
            box-shadow: none !important;
            padding: 0.9rem 1rem !important;
            font-size: 1rem !important;
            color: #6b6c7a !important;
            background: #f2f4f8 !important;
            border-radius: 12px !important;
        }}

        /* Reduce spacing of preview toggle */
        div[data-testid="stRadio"] {{
            margin-top: 0.2rem;
            margin-bottom: 0.2rem;
            padding: 0;
        }}

        /* Expander headers accent */
        [data-testid="stExpander"] > summary {{
            background: #f7f9fc;
            border: 1px solid #e5e7eb;
            border-left: 4px solid {CENTRIC_NAVY};
            border-radius: 12px;
            padding: 0.6rem 0.9rem;
            font-weight: 600;
            color: {CENTRIC_NAVY};
        }}
        [data-testid="stExpander"][open] > summary {{
            background: #eef4fb;
        }}
        [data-testid="stExpander"] {{
            margin-bottom: 0.45rem;
        }}

        /* Focus states */
        button, input, textarea {{
            outline-color: {CENTRIQ_BLUE};
        }}
    </style>
    """,
    unsafe_allow_html=True,
)

# Snowpark session
if "session" not in st.session_state:
    st.session_state["session"] = get_active_session()
session = st.session_state["session"]

# Conversation + thread state
if "turns" not in st.session_state:
    st.session_state["turns"] = []
if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = None
if "parent_message_id" not in st.session_state:
    st.session_state["parent_message_id"] = 0
if "pending_question" not in st.session_state:
    st.session_state["pending_question"] = None
if "pending_is_followup" not in st.session_state:
    st.session_state["pending_is_followup"] = False
if "view_mode" not in st.session_state:
    st.session_state["view_mode"] = "Landing"
if "chat_query" not in st.session_state:
    st.session_state["chat_query"] = ""


def _start_conversation_from_landing():
    landing_q = st.session_state.get("landing_query", "").strip()
    if landing_q:
        st.session_state["pending_question"] = landing_q
        st.session_state["pending_is_followup"] = False
        st.session_state["view_mode"] = "Conversation"
        st.session_state["landing_query"] = ""


def _submit_chat_input():
    text = st.session_state.get("chat_query", "").strip()
    if text:
        st.session_state["pending_question"] = text
        st.session_state["pending_is_followup"] = False
        st.session_state["view_mode"] = "Conversation"
        st.session_state["chat_query"] = ""

# Sidebar: reset + debug toggle
with st.sidebar:
    view_mode = st.radio(
        "Preview state",
        ["Landing", "Conversation"],
        index=0 if st.session_state["view_mode"] == "Landing" else 1,
    )
    st.session_state["view_mode"] = view_mode

    if st.button("Reset conversation"):
        st.session_state["turns"] = []
        st.session_state["thread_id"] = None
        st.session_state["parent_message_id"] = 0
        st.session_state["pending_question"] = None
        st.session_state["pending_is_followup"] = False
        st.session_state["view_mode"] = "Landing"
        st.rerun()

    show_debug_tab = st.checkbox("Show debug tab", value=False)


def data_uri_logo():
    return f"data:image/svg+xml;base64,{CENTRIQ_LOGO_BASE64}" if CENTRIQ_LOGO_BASE64 else ""


logo_src = data_uri_logo()
top_ribbon_html = f"""
<div class="top-ribbon">
    <div class="top-left">
        {f'<img class="top-logo" src="{logo_src}" alt="CentrIQ logo" />' if logo_src else '<div class="top-logo-placeholder">CI</div>'}
        <div>
            <div class="top-title">CentrIQ NLQ Insights</div>
            <div class="top-subtitle">Conversational answers for marketing &amp; sales KPIs</div>
        </div>
    </div>
</div>
"""


# Landing state
if st.session_state["view_mode"] == "Landing":
    st.markdown(
        f"""
        <div class="landing-container">
            {f'<img class="landing-logo" src="{logo_src}" alt="CentrIQ logo" />' if logo_src else '<div class="top-logo-placeholder">CI</div>'}
            <div class="landing-title">Start a conversation to uncover hidden insights in your marketing data</div>
            <div class="landing-sub">
                Ask about your marketing &amp; sales KPIs. I’ll summarize, show the chart, surface the SQL, and provide the table.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.text_input(
        "Start a conversation…",
        placeholder="Start a conversation…",
        label_visibility="collapsed",
        key="landing_query",
        on_change=_start_conversation_from_landing,
    )
    st.markdown(
        """
        <div class="landing-chip-row">
            <span class="chip">Top brands by MQLs</span>
            <span class="chip">Weekly trend vs last year</span>
            <span class="chip">Conversions by device</span>
            <span class="chip">Top countries by revenue</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

# Conversation layout
st.markdown(top_ribbon_html, unsafe_allow_html=True)

left_col, right_col = st.columns([1.9, 1.4], gap="large")
latest_turn = st.session_state["turns"][-1] if st.session_state["turns"] else None

with left_col:
    st.markdown('<div class="panel-left">', unsafe_allow_html=True)
    st.markdown('<div class="chat-scroll">', unsafe_allow_html=True)
    st.markdown('<div class="chat-wrapper">', unsafe_allow_html=True)

    for idx, t in enumerate(st.session_state["turns"]):
        render_turn(t, session, idx)

    pending_q = st.session_state.get("pending_question")
    pending_is_followup = st.session_state.get("pending_is_followup", False)

    user_q = None
    is_followup = False

    if pending_q:
        user_q = pending_q
        is_followup = pending_is_followup
        st.session_state["pending_question"] = None
        st.session_state["pending_is_followup"] = False

    if user_q:
        if st.session_state["thread_id"] is None:
            st.session_state["thread_id"] = create_thread()
            st.session_state["parent_message_id"] = 0

        thread_id = st.session_state["thread_id"]
        parent_id = st.session_state["parent_message_id"]

        with st.chat_message("user", avatar=_user_avatar()):
            st.markdown(f"<div class='bubble bubble-user'>{user_q}</div>", unsafe_allow_html=True)

        with st.chat_message("assistant", avatar=logo_src or "💬"):
            last_context = st.session_state["turns"][-1].get("context") if st.session_state["turns"] else None

            if last_context:
                rewritten_q = rewrite_question_with_context(
                    session,
                    st.session_state["turns"],
                    last_context,
                    user_q,
                    is_followup=is_followup,
                )
            else:
                rewritten_q = user_q

            with st.spinner("Working on your answer..."):
                events, assistant_msg_id, err = call_agent(
                    rewritten_q,
                    thread_id=thread_id,
                    parent_message_id=parent_id,
                )

            if assistant_msg_id is not None:
                st.session_state["parent_message_id"] = assistant_msg_id

            turn = {
                "question": user_q,
                "answer": "",
                "thinking": "",
                "sql": None,
                "df_records": None,
                "df_columns": None,
                "chart_cfg": None,
                "context": None,
            }
            sql = None
            df = None
            sql_error = None
            chart_cfg = None

            if err:
                st.error(err)
                turn["answer"] = err
            else:
                thinking = extract_thinking(events)
                agent_answer = extract_answer_text(events)
                sql = extract_sql(events)

                turn["thinking"] = thinking
                turn["sql"] = sql

                if sql:
                    try:
                        df = session.sql(sql).to_pandas()
                        turn["df_records"] = df.to_dict(orient="records")
                        turn["df_columns"] = list(df.columns)
                    except Exception as e:
                        sql_error = str(e)
                        st.error(sql_error)

                if sql and not sql_error and df is not None and not df.empty:
                    ctx = build_context_from_df(user_q, sql, df)
                    turn["context"] = ctx

                    numeric_cols = list(df.select_dtypes(include="number").columns)
                    is_scalar_kpi = len(df) == 1 and len(numeric_cols) > 0

                    if is_scalar_kpi:
                        preferred = ["total_sales", "sales", "ship_dollars", "revenue"]
                        metric_col = numeric_cols[0]
                        for c in numeric_cols:
                            if str(c).lower() in preferred:
                                metric_col = c
                                break

                        val = float(df.iloc[0][metric_col])
                        formatted_val = f"${{val:,.2f}}"

                        bullets = [f"- **{metric_col} (single KPI):** {formatted_val}"]
                        summary = (
                            f"**Summary:** For your question **{user_q}**, "
                            f"the data shows **{metric_col} = {formatted_val}**."
                        )
                        narrative = "\\n".join(bullets) + "\\n\\n" + summary

                        turn["answer"] = narrative
                        turn["chart_cfg"] = None

                    else:
                        cfg = get_llm_narrative_and_chart(session, user_q, df)

                        if cfg:
                            narrative = cfg.get("narrative")
                            chart_cfg = {
                                "chart_type": cfg.get("chart_type"),
                                "x": cfg.get("x"),
                                "y": cfg.get("y"),
                                "aggregate": cfg.get("aggregate"),
                            }
                        else:
                            narrative = simple_summary(user_q, df)
                            chart_cfg = None

                        turn["answer"] = narrative
                        turn["chart_cfg"] = chart_cfg

                elif sql and not sql_error and df is not None and df.empty:
                    narrative = simple_summary(user_q, df)
                    turn["answer"] = narrative

                elif sql and sql_error:
                    narrative = agent_answer or (
                        f"For **{user_q}**, the agent generated SQL but there was an execution error. "
                        f"Please review the error above or contact the data team."
                    )
                    turn["answer"] = narrative
                else:
                    narrative = agent_answer or simple_summary(user_q, df)
                    turn["answer"] = narrative

            if turn["answer"]:
                answer_html = format_answer_html(turn["answer"])
                st.markdown(
                    f"<div class='bubble bubble-assistant'>{answer_html}</div>",
                    unsafe_allow_html=True,
                )

                if show_debug_tab and "events" in locals() and events:
                    with st.expander("Debug (events)"):
                        st.markdown("#### Raw Cortex events")
                        if err:
                            st.error(err)
                        else:
                            st.json(events)
                        st.markdown("#### Extracted SQL")
                        st.code(sql or "None", language="sql")
                        st.markdown("#### Rewritten question sent to agent")
                        st.write(rewritten_q)
                        if df is not None:
                            st.markdown("#### Result sample (head)")
                            st.dataframe(df.head(), use_container_width=True)

                st.session_state["turns"].append(turn)
                latest_turn = turn

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# Determine latest turn for details panel
if st.session_state["turns"]:
    latest_turn = st.session_state["turns"][-1]

with right_col:
    st.markdown("<div class='panel-right'>", unsafe_allow_html=True)
    st.markdown("<div class='details-panel'>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'>Details</div>", unsafe_allow_html=True)
    st.markdown("<div class='details-scroll'>", unsafe_allow_html=True)
    if st.session_state["turns"]:
        for idx, t in enumerate(st.session_state["turns"], start=1):
            q_label = t.get("question", "Question")
            st.markdown(f"**Q{idx}:** {q_label}")

            l_sql = t.get("sql")
            l_thinking = t.get("thinking")
            l_chart_cfg = t.get("chart_cfg")
            l_df_records = t.get("df_records")
            l_df_columns = t.get("df_columns")

            l_df = None
            if l_df_records and l_df_columns:
                try:
                    l_df = pd.DataFrame(l_df_records, columns=l_df_columns)
                except Exception:
                    l_df = None

            l_tab_chart_df = None
            if l_df is not None and l_chart_cfg:
                l_tab_chart_df = build_chart_df_with_agg(
                    l_df,
                    l_chart_cfg.get("x"),
                    l_chart_cfg.get("y"),
                    l_chart_cfg.get("aggregate"),
                )

            viz_tab, think_tab, sql_tab, table_tab = st.tabs(
                ["📊 Visuals", "🧠 Thinking", "🧮 SQL Query", "📄 Data Table"]
            )

            with viz_tab:
                st.markdown("<div class='tab-scroll'>", unsafe_allow_html=True)
                if l_tab_chart_df is not None and l_chart_cfg:
                    render_chart(l_tab_chart_df, l_chart_cfg.get("chart_type"), st)
                else:
                    st.caption("No chart available.")
                st.markdown("</div>", unsafe_allow_html=True)

            with think_tab:
                st.markdown("<div class='tab-scroll'>", unsafe_allow_html=True)
                if l_thinking:
                    st.markdown(l_thinking)
                else:
                    st.caption("No thinking available.")
                st.markdown("</div>", unsafe_allow_html=True)

            with sql_tab:
                st.markdown("<div class='tab-scroll'>", unsafe_allow_html=True)
                if l_sql:
                    st.code(l_sql, language="sql")
                else:
                    st.caption("No SQL generated.")
                st.markdown("</div>", unsafe_allow_html=True)

            with table_tab:
                st.markdown("<div class='tab-scroll'>", unsafe_allow_html=True)
                if l_df is not None and not l_df.empty:
                    st.dataframe(l_df, use_container_width=True)
                elif l_sql:
                    st.caption("No data returned.")
                else:
                    st.caption("No data available.")
                st.markdown("</div>", unsafe_allow_html=True)

            st.divider()
    else:
        st.caption("No answers yet. Ask a question to see details.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='chat-bar'>", unsafe_allow_html=True)
st.text_input(
    "Ask a new question…",
    placeholder="e.g., How do total MQLs compare to last year?",
    key="chat_query",
    label_visibility="collapsed",
    on_change=_submit_chat_input,
)
st.markdown("</div>", unsafe_allow_html=True)
