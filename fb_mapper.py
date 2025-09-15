
"""
fb_mapper.py
Maps a lightweight "simple mode" CSV into Facebook Ads Manager bulk-import format.
Implements defaults, validation, and conflict resolution per spec.
"""
from __future__ import annotations
import pandas as pd
from typing import List, Dict, Any
from datetime import datetime

VALID = {
    "status": {"ACTIVE", "PAUSED", "ARCHIVED", "DELETED"},
    "objectives": {
        "Traffic","Leads","Conversions","Sales","Video Views","Reach","Engagement","App Installs"
    },
    "buying_type": {"AUCTION","FIXED_PRICE"},
    "bid_strategies": {"Lowest cost","Cost cap","ROAS goal","Bid cap"},
    "cta": {
        "LEARN_MORE","SIGN_UP","GET_QUOTE","SHOP_NOW","SUBSCRIBE","APPLY_NOW","CONTACT_US","BOOK_NOW"
    },
    "gender": {"All","Male","Female"},
    "placements": {
        "facebook","instagram","audience_network","messenger",
        "feed","stories","reels","instream_video","marketplace"
    }
}

# Objective → default optimisation + CTA
OBJ_DEFAULTS = {
    "Leads": {"optimisation": "LEAD_GENERATION", "cta": "SIGN_UP"},
    "Conversions": {"optimisation": "CONVERSIONS", "cta": "SHOP_NOW"},
    "Sales": {"optimisation": "VALUE", "cta": "SHOP_NOW"},
    "Traffic": {"optimisation": "LINK_CLICKS", "cta": "LEARN_MORE"},
    "Video Views": {"optimisation": "THRUPLAY", "cta": "LEARN_MORE"},
}

def _coerce_time(val: Any) -> str:
    if pd.isna(val) or val == "":
        return ""
    # Accept "YYYY-MM-DD HH:MM" and ISO8601-ish
    try:
        return datetime.strptime(str(val), "%Y-%m-%d %H:%M").strftime("%Y-%m-%d %H:%M")
    except Exception:
        try:
            # Pandas parse then normalise
            dt = pd.to_datetime(val, utc=False, errors="raise")
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            raise ValueError(f"Invalid time format: {val}")

def _pos_number(val: Any, allow_blank=True) -> str:
    if pd.isna(val) or str(val).strip() == "":
        return "" if allow_blank else "0"
    try:
        v = float(val)
        if v <= 0:
            raise ValueError("must be > 0")
        # No decimals for budgets in CSV
        return str(int(round(v)))
    except Exception:
        raise ValueError(f"Invalid positive number: {val}")

def _enum(val: Any, allowed: set, field: str) -> str:
    if pd.isna(val) or val == "":
        return ""
    s = str(val)
    if s not in allowed:
        raise ValueError(f"{field}: '{s}' not in {sorted(allowed)}")
    return s

def _gender(val: Any) -> str:
    if pd.isna(val) or val == "":
        return "All"
    s = str(val).title()
    if s not in VALID["gender"]:
        raise ValueError(f"Gender: '{val}' invalid")
    return s

def _age_pair(minv: Any, maxv: Any, special: str) -> (str,str):
    if pd.isna(minv) and pd.isna(maxv):
        return "18","65"
    try:
        mi = int(minv) if not pd.isna(minv) else 18
        ma = int(maxv) if not pd.isna(maxv) else 65
        if mi > ma:
            raise ValueError("Age Min must be ≤ Age Max")
        # Special Ad Categories restrictions (simplified common case)
        if special and special.strip() != "":
            mi = max(mi, 18)
            ma = min(ma, 65)
        return str(mi), str(ma)
    except Exception:
        raise ValueError(f"Invalid age pair: {minv}, {maxv}")

def _default_cta(objective: str, cta: str) -> str:
    if cta and cta != "":
        return _enum(cta, VALID["cta"], "CTA")
    if objective in OBJ_DEFAULTS:
        return OBJ_DEFAULTS[objective]["cta"]
    return "LEARN_MORE"

def _default_opt_goal(objective: str, goal: str) -> str:
    if goal and goal != "":
        return goal
    if objective in OBJ_DEFAULTS:
        return OBJ_DEFAULTS[objective]["optimisation"]
    return ""

def _ensure_utm(link: str, utm: str) -> (str, str):
    if pd.isna(link) or link == "":
        return "", ""
    if pd.isna(utm) or utm == "":
        # Simple default
        return link, "utm_source=facebook&utm_medium=cpc"
    return link, utm

def transform(df: pd.DataFrame) -> (pd.DataFrame, pd.DataFrame):
    """
    Input: lightweight rows tagged by Input Level: 'campaign' or 'adset'
    Each adset row carries creative fields for one ad for simplicity.
    Output: Facebook bulk CSV rows with proper headers + errors table.
    """
    errors = []
    rows = []

    # Forward fill campaign-level values so adset rows inherit
    df_ff = df.copy()
    # propagate campaign values down until next campaign row
    campaign_cols = [
        "Campaign Name","Campaign Status","Special Ad Categories","Special Ad Category Country",
        "Campaign Objective","Buying Type","Campaign Bid Strategy","Campaign Daily Budget",
        "Campaign Start Time","Campaign Stop Time"
    ]
    for c in campaign_cols:
        df_ff[c] = df_ff[c].ffill()

    # Process row by row
    for i, r in df_ff.iterrows():
        level = str(r.get("Input Level","")).lower()
        if level not in {"campaign","adset"}:
            errors.append({"row": i+1, "field": "Input Level", "error": "Must be 'campaign' or 'adset'"})
            continue

        if level == "campaign":
            # Emit one campaign row
            try:
                objective = _enum(str(r.get("Campaign Objective","")), VALID["objectives"], "Objective")
                out = {
                    "Campaign Name": r.get("Campaign Name",""),
                    "Campaign Status": _enum(r.get("Campaign Status","ACTIVE"), VALID["status"], "Status"),
                    "Special Ad Categories": r.get("Special Ad Categories",""),
                    "Special Ad Category Country": r.get("Special Ad Category Country",""),
                    "Buying Type": _enum(r.get("Buying Type","AUCTION"), VALID["buying_type"], "Buying Type"),
                    "Campaign Objective": objective,
                    "Campaign Bid Strategy": _enum(r.get("Campaign Bid Strategy","Lowest cost"), VALID["bid_strategies"], "Bid Strategy"),
                    "Campaign Daily Budget": _pos_number(r.get("Campaign Daily Budget","")),
                    "Campaign Start Time": _coerce_time(r.get("Campaign Start Time","")),
                    "Campaign Stop Time": _coerce_time(r.get("Campaign Stop Time","")),
                    # Defaults
                    "Advantage+ placements": "true",
                }
                # Campaign-level budget vs adset budgets will be checked when processing adsets
                rows.append(out)
            except Exception as e:
                errors.append({"row": i+1, "field": "campaign", "error": str(e)})
            continue

        # adset rows produce both ad set and ad rows in the same record for Ads Manager
        try:
            objective = _enum(str(r.get("Campaign Objective","")), VALID["objectives"], "Objective")

            # Budget conflict resolution
            c_budget = r.get("Campaign Daily Budget","")
            as_budget = r.get("Ad Set Daily Budget","")
            c_budget_s = str(c_budget).strip()
            as_budget_s = str(as_budget).strip()
            if c_budget_s and as_budget_s:
                # Prefer ad set budget for ad set row and blank campaign budget in emitted row
                c_budget_s = ""
            age_min, age_max = _age_pair(r.get("Age Min",""), r.get("Age Max",""), r.get("Special Ad Categories",""))
            link, utm = _ensure_utm(r.get("Link",""), r.get("URL Tags",""))
            cta = _default_cta(objective, r.get("Call to Action",""))
            opt_goal = _default_opt_goal(objective, r.get("Optimisation Goal",""))

            out = {
                # Campaign
                "Campaign Name": r.get("Campaign Name",""),
                "Campaign Status": _enum(r.get("Campaign Status","ACTIVE"), VALID["status"], "Status"),
                "Special Ad Categories": r.get("Special Ad Categories",""),
                "Special Ad Category Country": r.get("Special Ad Category Country",""),
                "Buying Type": _enum(r.get("Buying Type","AUCTION"), VALID["buying_type"], "Buying Type"),
                "Campaign Objective": objective,
                "Campaign Bid Strategy": _enum(r.get("Campaign Bid Strategy","Lowest cost"), VALID["bid_strategies"], "Bid Strategy"),
                "Campaign Daily Budget": _pos_number(c_budget_s) if c_budget_s else "",
                "Campaign Start Time": _coerce_time(r.get("Campaign Start Time","")),
                "Campaign Stop Time": _coerce_time(r.get("Campaign Stop Time","")),
                "Advantage+ placements": "true",

                # Ad set
                "Ad Set Name": r.get("Ad Set Name",""),
                "Ad Set Run Status": _enum(r.get("Ad Set Run Status","ACTIVE"), VALID["status"], "Status"),
                "Ad Set Daily Budget": _pos_number(as_budget) if as_budget_s else "",
                "Ad Set Time Start": _coerce_time(r.get("Ad Set Time Start","")),
                "Ad Set Time Stop": _coerce_time(r.get("Ad Set Time Stop","")),
                "Countries": r.get("Countries",""),
                "Age Min": age_min,
                "Age Max": age_max,
                "Gender": _gender(r.get("Gender","All")),
                "Custom Audiences": r.get("Custom Audiences",""),
                "Excluded Custom Audiences": r.get("Excluded Custom Audiences",""),
                "Optimisation Goal": opt_goal,

                # Placements optional explicit left blank in simple mode

                # Creative
                "Ad Name": r.get("Ad Name",""),
                "Ad Status": _enum(r.get("Ad Status","ACTIVE"), VALID["status"], "Status"),
                "Title": r.get("Title",""),
                "Body": r.get("Body",""),
                "Link": link,
                "URL Tags": utm,
                "Call to Action": cta,
                "Image File Name": r.get("Image File Name",""),
            }
            rows.append(out)
        except Exception as e:
            errors.append({"row": i+1, "field": "adset", "error": str(e)})

    out_df = pd.DataFrame(rows)

    # Reorder columns to match expected template shape for bulk import
    desired_cols = [
        # Campaign
        "Campaign Name","Campaign Status","Special Ad Categories","Special Ad Category Country",
        "Buying Type","Campaign Objective","Campaign Bid Strategy","Campaign Daily Budget",
        "Campaign Start Time","Campaign Stop Time","Advantage+ placements",
        # Ad set
        "Ad Set Name","Ad Set Run Status","Ad Set Daily Budget","Ad Set Time Start","Ad Set Time Stop",
        "Countries","Age Min","Age Max","Gender","Custom Audiences","Excluded Custom Audiences","Optimisation Goal",
        # Creative
        "Ad Name","Ad Status","Title","Body","Link","URL Tags","Call to Action","Image File Name"
    ]
    # Add missing columns if any
    for c in desired_cols:
        if c not in out_df.columns:
            out_df[c] = ""
    out_df = out_df[desired_cols]

    err_df = pd.DataFrame(errors, columns=["row","field","error"])
    return out_df, err_df
