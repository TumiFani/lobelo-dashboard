import streamlit as st
import pandas as pd
import re
import json
import os
from pathlib import Path
from datetime import datetime
from serpapi import GoogleSearch
from groq import Groq

# ── Configuration ─────────────────────────────────────────────────────────────

SERPAPI_KEY = "637991fa019cd58ab664be55a57f6408125989f855f8b566b91b516a8d5677fa"
MODEL = "llama-3.1-8b-instant"

SYSTEM_PROMPT = """You are Lobelo, an AI assistant for the Botswana Paralympic Athletics squad coaching team.
You have access to tools that query live squad data: athlete profiles, performance tests, injuries,
readiness scores, medals, training sessions, and competition results.

Rules:
- Always call the appropriate tool before answering any data question. Never invent or guess numbers.
- For world record questions, use the search_world_record tool.
- Be concise and factual. Use bullet points for lists of athletes or statistics.
- If a tool returns empty data, say so clearly.
- The squad uses Paralympic classifications: T11 (no light perception, guide runner required),
  T12 (moderate visual impairment), T13 (least severe visual impairment).
- Events in the squad: 100m, 200m, 400m, 800m, 1500m.

Clarification rules (IMPORTANT):
- If a question is ambiguous, DO NOT call a tool yet. Ask the user to clarify first.
- Only ask ONE clarifying question at a time. Keep it concise.
- Once you have enough context, call the tool and answer directly.
- If the question is already specific (e.g. "best 100m T12 athlete by medals"), go straight to the tool.

"Best / worst / top athlete" (SPECIAL CASE):
When the user asks who is the "best", "worst", "top", "greatest", or similar — without specifying
how to measure — present ALL available criteria and ask which one to use:

  "I can find that athlete based on several measures — which one do you mean?
   1. 🏃 **Performance** — fastest (or slowest) recorded times
   2. 🏅 **Medals** — most (or fewest) medals won
   3. 💪 **Readiness** — highest (or lowest) competition readiness score
   4. 📈 **Improvement** — most (or least) improved over career
   5. 🎯 **Training consistency** — most (or least) consistent training"

Wait for their choice, ask any remaining follow-up (e.g. event/classification for performance),
then call the tool and return THE SINGLE athlete that matches — not a list.

IMPORTANT distinction:
- "Who is the best athlete?" → return ONE athlete (the top result), not a ranking.
- "Who is the worst athlete?" → return ONE athlete (the bottom result), not a ranking.
- "Show me the top 5 athletes" or "rank athletes by X" → ONLY then return a list.
- Never produce a ranked list unless the user explicitly asks for one.

Other ambiguous cases:
- "Who has the most injuries?" → ask: "For the full squad, or a specific event or classification?"
- "How ready is the team?" → ask: "For the full squad or a specific event/classification?"
"""


# ── Shared data helpers ────────────────────────────────────────────────────────

def safe_df(data, key):
    aliases = {
        "athletes":           ["athletes"],
        "performance_tests":  ["performance_tests", "tests"],
        "training_sessions":  ["training_sessions", "sessions"],
        "injuries":           ["injuries"],
        "medals":             ["medals"],
        "readiness_scores":   ["readiness_scores", "readiness"],
        "competition_results":["competition_results", "results"],
        "coach_notes":        ["coach_notes", "notes"],
    }
    for candidate in aliases.get(key, [key]):
        df = data.get(candidate) if isinstance(data, dict) else None
        if isinstance(df, pd.DataFrame) and not df.empty:
            return df.copy()
    for folder in [Path(__file__).parent / "data", Path(__file__).parent]:
        for candidate in aliases.get(key, [key]):
            path = folder / f"{candidate}.csv"
            if path.exists():
                try:
                    return pd.read_csv(path)
                except Exception:
                    pass
    return pd.DataFrame()


def standardize_athletes(athletes):
    athletes = athletes.copy()
    if "name" not in athletes.columns and "athlete_name" in athletes.columns:
        athletes = athletes.rename(columns={"athlete_name": "name"})
    return athletes


def join_athletes(df, athletes):
    if df.empty:
        return df.copy()
    athletes = standardize_athletes(athletes)
    if athletes.empty or "athlete_id" not in df.columns or "athlete_id" not in athletes.columns:
        return df.copy()
    profile_cols = [c for c in [
        "athlete_id", "name", "gender", "classification", "primary_event",
        "secondary_event", "coach", "region", "development_stage",
        "availability_status", "injury_status", "guide_runner_required",
    ] if c in athletes.columns]
    dup = [c for c in profile_cols if c in df.columns and c != "athlete_id"]
    if dup:
        df = df.drop(columns=dup)
    return df.merge(athletes[profile_cols], on="athlete_id", how="left")


def _apply_filters(df, event=None, gender=None, classification=None, coach=None, region=None):
    if gender and "gender" in df.columns:
        df = df[df["gender"].astype(str).str.lower() == gender.lower()]
    if classification and "classification" in df.columns:
        df = df[df["classification"].astype(str).str.upper() == classification.upper()]
    if event:
        for col in ["primary_event", "event"]:
            if col in df.columns:
                df = df[df[col].astype(str).str.lower() == event.lower()]
                break
    if coach and "coach" in df.columns:
        df = df[df["coach"].astype(str).str.lower() == coach.lower()]
    if region and "region" in df.columns:
        df = df[df["region"].astype(str).str.lower() == region.lower()]
    return df


# ── Tool implementations ───────────────────────────────────────────────────────

def tool_count_athletes(data, athletes, event=None, gender=None, classification=None,
                        development_stage=None, availability_status=None, coach=None, region=None):
    df = standardize_athletes(athletes.copy())
    df = _apply_filters(df, event=event, gender=gender, classification=classification,
                        coach=coach, region=region)
    if development_stage and "development_stage" in df.columns:
        df = df[df["development_stage"].astype(str).str.lower() == development_stage.lower()]
    if availability_status and "availability_status" in df.columns:
        df = df[df["availability_status"].astype(str).str.lower() == availability_status.lower()]
    return {
        "total": len(df),
        "by_event":          df["primary_event"].value_counts().head(10).to_dict() if "primary_event" in df.columns else {},
        "by_classification": df["classification"].value_counts().head(5).to_dict() if "classification" in df.columns else {},
        "by_gender":         df["gender"].value_counts().head(5).to_dict() if "gender" in df.columns else {},
        "by_region":         df["region"].value_counts().head(10).to_dict() if "region" in df.columns else {},
        "by_coach":          df["coach"].value_counts().head(10).to_dict() if "coach" in df.columns else {},
    }


def tool_get_athlete_profile(data, athletes, name=None, athlete_id=None):
    df = standardize_athletes(athletes.copy())
    if athlete_id:
        match = df[df["athlete_id"].astype(str).str.lower() == athlete_id.lower()]
    elif name:
        match = df[df["name"].astype(str).str.lower().str.contains(name.lower(), na=False)]
    else:
        return {"error": "Provide athlete name or ID."}

    if match.empty:
        return {"error": f"No athlete found matching '{name or athlete_id}'."}

    if len(match) > 1:
        return {
            "multiple_matches": True,
            "athletes": match[["athlete_id", "name", "classification", "primary_event", "region"]]
                        .to_dict(orient="records"),
        }

    profile = match.iloc[0].to_dict()
    profile = {k: (None if (isinstance(v, float) and pd.isna(v)) else v) for k, v in profile.items()}
    return {"profile": profile}


def tool_get_performance(data, athletes, event=None, athlete_id=None, top_n=10):
    top_n = int(top_n) if top_n is not None else 10
    perf = safe_df(data, "performance_tests")
    if perf.empty:
        return {"error": "Performance data not available."}
    joined = join_athletes(perf, athletes)
    if event:
        joined = joined[joined["event"].astype(str).str.lower() == event.lower()]
    if athlete_id:
        joined = joined[joined["athlete_id"].astype(str).str.lower() == athlete_id.lower()]
    if joined.empty:
        return {"error": "No performance records for that selection."}

    stats = {
        "total_records":  len(joined),
        "fastest_time":   round(float(joined["time_seconds"].min()), 2),
        "slowest_time":   round(float(joined["time_seconds"].max()), 2),
        "average_time":   round(float(joined["time_seconds"].mean()), 2),
    }

    best = (
        joined.sort_values("time_seconds")
        .groupby("athlete_id", as_index=False).first()
        .sort_values("time_seconds")
        .head(top_n)
    )
    ranking = [
        {
            "rank":               i,
            "name":               row.get("name", row.get("athlete_id")),
            "athlete_id":         row.get("athlete_id"),
            "event":              row.get("event"),
            "best_time_seconds":  row.get("time_seconds"),
            "classification":     row.get("classification"),
        }
        for i, (_, row) in enumerate(best.iterrows(), 1)
    ]
    return {"stats": stats, "top_athletes": ranking}


def tool_get_injuries(data, athletes, event=None, classification=None, athlete_id=None):
    injuries = safe_df(data, "injuries")
    if injuries.empty:
        return {"error": "Injury data not available."}
    joined = join_athletes(injuries, athletes)
    if classification and "classification" in joined.columns:
        joined = joined[joined["classification"].astype(str).str.upper() == classification.upper()]
    if event and "primary_event" in joined.columns:
        joined = joined[joined["primary_event"].astype(str).str.lower() == event.lower()]
    if athlete_id:
        joined = joined[joined["athlete_id"].astype(str).str.lower() == athlete_id.lower()]
    if joined.empty:
        return {"total": 0, "message": "No injury records for that selection."}

    result = {
        "total_records":     len(joined),
        "by_type":           joined["injury_type"].value_counts().head(10).to_dict() if "injury_type" in joined.columns else {},
        "by_classification": joined["classification"].value_counts().to_dict() if "classification" in joined.columns else {},
        "by_event":          joined["primary_event"].value_counts().to_dict() if "primary_event" in joined.columns else {},
        "by_severity":       joined["severity"].value_counts().to_dict() if "severity" in joined.columns else {},
    }
    if "days_lost" in joined.columns:
        result["avg_days_lost"] = round(float(joined["days_lost"].mean()), 1)
        result["max_days_lost"] = int(joined["days_lost"].max())

    if "athlete_id" in joined.columns:
        group_cols = ["athlete_id"] + (["name"] if "name" in joined.columns else [])
        counts = (
            joined.groupby(group_cols).size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
            .head(10)
        )
        result["most_injured_athletes"] = counts.to_dict(orient="records")

    return result


def tool_get_readiness(data, athletes, event=None, athlete_id=None, classification=None):
    readiness = safe_df(data, "readiness_scores")
    if readiness.empty:
        return {"error": "Readiness data not available."}
    joined = join_athletes(readiness, athletes)
    if event and "primary_event" in joined.columns:
        joined = joined[joined["primary_event"].astype(str).str.lower() == event.lower()]
    if classification and "classification" in joined.columns:
        joined = joined[joined["classification"].astype(str).str.upper() == classification.upper()]
    if athlete_id:
        joined = joined[joined["athlete_id"].astype(str).str.lower() == athlete_id.lower()]
    if joined.empty:
        return {"error": "No readiness records for that selection."}

    result = {}
    if "status" in joined.columns:
        status_counts = joined["status"].value_counts().to_dict()
        total = len(joined)
        result["status_breakdown"] = status_counts
        result["ready_count"] = int(status_counts.get("Ready", 0))
        result["total"]       = total
        result["ready_pct"]   = round(result["ready_count"] / total * 100) if total else 0

    for col in ["overall_readiness_score", "competition_readiness", "training_consistency", "injury_risk"]:
        if col in joined.columns:
            vals = pd.to_numeric(joined[col], errors="coerce").dropna()
            if not vals.empty:
                avg = float(vals.mean())
                result[f"avg_{col}"] = round(avg * 100 if avg <= 1 else avg, 1)

    score_col = next((c for c in ["overall_readiness_score", "competition_readiness"] if c in joined.columns), None)
    if score_col:
        top = joined.copy()
        top[score_col] = pd.to_numeric(top[score_col], errors="coerce")
        top = top.dropna(subset=[score_col]).sort_values(score_col, ascending=False).head(5)
        result["top_ready_athletes"] = [
            {
                "name":           row.get("name", row.get("athlete_id")),
                "score":          round(float(row[score_col]) * 100 if float(row[score_col]) <= 1 else float(row[score_col]), 1),
                "event":          row.get("primary_event"),
                "classification": row.get("classification"),
            }
            for _, row in top.iterrows()
        ]
    return result


def tool_get_medals(data, athletes, event=None, athlete_id=None, coach=None, classification=None):
    medals = safe_df(data, "medals")
    if medals.empty:
        return {"error": "Medal data not available."}
    joined = join_athletes(medals, athletes)
    if event:
        for col in ["event", "race", "discipline"]:
            if col in joined.columns:
                joined = joined[joined[col].astype(str).str.lower() == event.lower()]
                break
    if athlete_id:
        joined = joined[joined["athlete_id"].astype(str).str.lower() == athlete_id.lower()]
    if coach and "coach" in joined.columns:
        joined = joined[joined["coach"].astype(str).str.lower() == coach.lower()]
    if classification and "classification" in joined.columns:
        joined = joined[joined["classification"].astype(str).str.upper() == classification.upper()]
    if joined.empty:
        return {"total": 0, "message": "No medal records for that selection."}

    result = {"total_records": len(joined)}
    if "medal_type" in joined.columns:
        result["by_medal_type"] = joined["medal_type"].value_counts().to_dict()
    if "coach" in joined.columns:
        result["by_coach"] = joined["coach"].value_counts().head(10).to_dict()

    if "athlete_id" in joined.columns:
        group_cols = ["athlete_id"] + [
            c for c in ["name", "classification", "primary_event"] if c in joined.columns
        ]
        counts = (
            joined.groupby(group_cols).size()
            .reset_index(name="medal_count")
            .sort_values("medal_count", ascending=False)
            .head(10)
        )
        result["top_athletes"] = counts.to_dict(orient="records")

    return result


def tool_get_training(data, athletes, event=None, athlete_id=None, classification=None):
    sessions = safe_df(data, "training_sessions")
    if sessions.empty:
        return {"error": "Training data not available."}
    joined = join_athletes(sessions, athletes)
    if event and "primary_event" in joined.columns:
        joined = joined[joined["primary_event"].astype(str).str.lower() == event.lower()]
    if athlete_id:
        joined = joined[joined["athlete_id"].astype(str).str.lower() == athlete_id.lower()]
    if classification and "classification" in joined.columns:
        joined = joined[joined["classification"].astype(str).str.upper() == classification.upper()]
    if joined.empty:
        return {"total": 0, "message": "No training records for that selection."}

    result = {"total_sessions": len(joined)}
    if "session_type" in joined.columns:
        result["by_session_type"] = joined["session_type"].value_counts().to_dict()
    if "intensity" in joined.columns:
        result["avg_intensity"] = round(float(pd.to_numeric(joined["intensity"], errors="coerce").mean()), 1)
    if "duration_minutes" in joined.columns:
        result["avg_duration_minutes"] = round(float(pd.to_numeric(joined["duration_minutes"], errors="coerce").mean()), 1)
    if "completion_status" in joined.columns:
        result["completion_breakdown"] = joined["completion_status"].value_counts().to_dict()
    return result


def tool_search_world_record(query):
    try:
        params = {"engine": "google", "q": query, "api_key": SERPAPI_KEY, "num": 5}
        results = GoogleSearch(params).get_dict().get("organic_results", [])
        if not results:
            return {"error": "No results found."}
        time_pattern = r"\b(?:\d{1,2}:\d{2}\.\d{2}|\d{1,2}\.\d{2})\b"
        for result in results:
            snippet = result.get("snippet", "")
            title   = result.get("title", "")
            combined = f"{title}; {snippet}"
            time_match = re.search(time_pattern, combined)
            if time_match:
                return {
                    "source":       title,
                    "snippet":      snippet,
                    "time_found":   time_match.group(0),
                    "retrieved":    datetime.now().strftime("%B %Y"),
                }
        return {"snippet": results[0].get("snippet", ""), "retrieved": datetime.now().strftime("%B %Y")}
    except Exception as e:
        return {"error": str(e)}


# ── Tool schemas for Llama 3.3 70B ────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "count_athletes",
            "description": "Count athletes in the squad with optional filters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event":              {"type": ["string", "null"], "description": "e.g. '100m', '200m', '400m', '800m', '1500m'"},
                    "gender":             {"type": ["string", "null"], "description": "Male or Female"},
                    "classification":     {"type": ["string", "null"], "description": "e.g. 'T11', 'T12', 'T13'"},
                    "development_stage":  {"type": ["string", "null"]},
                    "availability_status":{"type": ["string", "null"]},
                    "coach":              {"type": ["string", "null"]},
                    "region":             {"type": ["string", "null"]},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_athlete_profile",
            "description": "Get the full profile of a specific athlete by name or athlete ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name":       {"type": ["string", "null"], "description": "Athlete full or partial name"},
                    "athlete_id": {"type": ["string", "null"], "description": "e.g. 'A0001'"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_performance",
            "description": "Get performance test data: best times, rankings, and stats for events or individual athletes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event":      {"type": ["string", "null"], "description": "e.g. '100m', '200m'"},
                    "athlete_id": {"type": ["string", "null"]},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_injuries",
            "description": "Get injury records: counts, types, severity, days lost, and which athletes/classes/events have the most injuries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event":          {"type": ["string", "null"]},
                    "classification": {"type": ["string", "null"]},
                    "athlete_id":     {"type": ["string", "null"]},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_readiness",
            "description": "Get athlete readiness scores: competition readiness, overall readiness, training consistency, and injury risk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event":          {"type": ["string", "null"]},
                    "athlete_id":     {"type": ["string", "null"]},
                    "classification": {"type": ["string", "null"]},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_medals",
            "description": "Get medal records by athlete, coach, event, or classification.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event":          {"type": ["string", "null"]},
                    "athlete_id":     {"type": ["string", "null"]},
                    "coach":          {"type": ["string", "null"]},
                    "classification": {"type": ["string", "null"]},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_training",
            "description": "Get training session data: session types, intensity, duration, completion rates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event":          {"type": ["string", "null"]},
                    "athlete_id":     {"type": ["string", "null"]},
                    "classification": {"type": ["string", "null"]},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_world_record",
            "description": "Search Google for current Paralympic world records. Use for any question about world records or record holders.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "e.g. 'Paralympic T12 100m men world record'"},
                },
                "required": ["query"],
            },
        },
    },
]


# ── Tool dispatcher ────────────────────────────────────────────────────────────

def _json_safe(obj):
    """Recursively convert non-serializable types so json.dumps never fails."""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if hasattr(obj, "isoformat"):  # datetime, date, Timestamp
        return obj.isoformat()
    if hasattr(obj, "item"):       # numpy int64, float64, etc.
        return obj.item()
    return obj


def dispatch_tool(name, args, data, athletes):
    # Strip empty strings so optional params behave as None
    args = {k: v for k, v in args.items() if v != "" and v is not None}
    dispatch = {
        "count_athletes":      lambda: tool_count_athletes(data, athletes, **args),
        "get_athlete_profile": lambda: tool_get_athlete_profile(data, athletes, **args),
        "get_performance":     lambda: tool_get_performance(data, athletes, **args),
        "get_injuries":        lambda: tool_get_injuries(data, athletes, **args),
        "get_readiness":       lambda: tool_get_readiness(data, athletes, **args),
        "get_medals":          lambda: tool_get_medals(data, athletes, **args),
        "get_training":        lambda: tool_get_training(data, athletes, **args),
        "search_world_record": lambda: tool_search_world_record(args.get("query", "")),
    }
    fn = dispatch.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return fn()
    except Exception as e:
        return {"error": str(e)}


# ── LobeloAssistant ────────────────────────────────────────────────────────────

class LobeloAssistant:

    def __init__(self, data, filtered_athletes):
        self.data = data
        self.filtered_athletes = filtered_athletes
        api_key = os.getenv("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY", "")
        self.client = Groq(api_key=api_key)

    def _active_athletes(self):
        fa = self.filtered_athletes
        if fa is not None and isinstance(fa, pd.DataFrame) and not fa.empty:
            return fa
        return self.data["athletes"]

    def answer(self, question):
        athletes = self._active_athletes()

        # Last 2 turns of chat as context (keeps token usage low)
        history = [
            {"role": role, "content": msg}
            for role, msg in st.session_state.get("lobelo_chat", [])[-4:]
        ]

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *history,
            {"role": "user", "content": question},
        ]

        # Agentic loop — up to 5 tool-call rounds
        for _ in range(5):
            response = self.client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                max_tokens=512,
                temperature=0.3,
            )

            msg = response.choices[0].message

            if not msg.tool_calls:
                return msg.content or "I couldn't find an answer to that."

            # Append assistant message with tool calls
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id":   tc.id,
                        "type": "function",
                        "function": {
                            "name":      tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            })

            # Execute each tool and append results
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                result = dispatch_tool(tc.function.name, args, self.data, athletes)
                messages.append({
                    "role":         "tool",
                    "tool_call_id": tc.id,
                    "content":      json.dumps(_json_safe(result)),
                })

        return "I wasn't able to complete that request. Please try rephrasing."


# ── Streamlit UI ───────────────────────────────────────────────────────────────

def render_ask_lobelo(data, filtered_athletes):

    st.subheader("Ask Lobelo 🤖")

    st.markdown("""
    <style>
    /* User bubble */
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        background: rgba(55, 65, 81, 0.85) !important;
        border-radius: 12px;
        padding: 10px 14px;
        color: #ffffff !important;
    }
    /* Assistant bubble */
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
        background: rgba(255, 255, 255, 0.92) !important;
        border-radius: 12px;
        padding: 10px 14px;
        color: #0f172a !important;
    }
    /* Force text color inside assistant bubble */
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) p,
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) li,
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) span {
        color: #0f172a !important;
    }
    /* Force text color inside user bubble */
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) p,
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) span {
        color: #ffffff !important;
    }
    </style>
    """, unsafe_allow_html=True)

    api_key = os.getenv("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY", "")
    if not api_key:
        st.error(
            "**GROQ_API_KEY not set.** "
            "Add it as an environment variable (`export GROQ_API_KEY=your_key`) "
            "or in `.streamlit/secrets.toml` as `GROQ_API_KEY = \"your_key\"`."
        )
        return

    if "lobelo_chat" not in st.session_state:
        st.session_state.lobelo_chat = []

    if st.button("Reset chat"):
        st.session_state.lobelo_chat = []
        st.rerun()

    assistant = LobeloAssistant(data, filtered_athletes)

    for role, msg in st.session_state.lobelo_chat:
        with st.chat_message(role):
            st.markdown(msg)

    prompt = st.chat_input(
        "Ask Lobelo about athletes, readiness, injuries, medals, coaches, performance, or training"
    )

    if prompt:
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("⏳ _Thinking..._")
            try:
                response = assistant.answer(prompt)
            except Exception as e:
                import traceback
                traceback.print_exc()
                response = f"⚠️ **Error:** {type(e).__name__}: {e}"
            placeholder.markdown(response)

        st.session_state.lobelo_chat.append(("user", prompt))
        st.session_state.lobelo_chat.append(("assistant", response))