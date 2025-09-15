"""
fb_mapper.py - Improved version
Maps a lightweight "simple mode" CSV into Facebook Ads Manager bulk-import format.
Implements defaults, validation, and conflict resolution per spec.
"""
from __future__ import annotations
import pandas as pd
from typing import List, Dict, Any, Tuple
from datetime import datetime

VALID = {
    "status": {"ACTIVE", "PAUSED", "ARCHIVED", "DELETED"},
    "objectives": {
        "Traffic", "Leads", "Conversions", "Sales", "Video Views", "Reach", 
        "Engagement", "App Installs", "Brand Awareness", "Messages"
    },
    "buying_type": {"AUCTION", "FIXED_PRICE"},
    "bid_strategies": {"Lowest cost", "Cost cap", "ROAS goal", "Bid cap"},
    "cta": {
        "LEARN_MORE", "SIGN_UP", "GET_QUOTE", "SHOP_NOW", "SUBSCRIBE", 
        "APPLY_NOW", "CONTACT_US", "BOOK_NOW", "DOWNLOAD", "GET_DIRECTIONS"
    },
    "gender": {"All", "Male", "Female"},
    "placements": {
        "facebook", "instagram", "audience_network", "messenger",
        "feed", "stories", "reels", "instream_video", "marketplace"
    },
    "special_categories": {
        "CREDIT", "EMPLOYMENT", "HOUSING", "SOCIAL_ISSUES", "POLITICS"
    }
}

# Objective → default optimisation + CTA mapping
OBJ_DEFAULTS = {
    "Leads": {"optimisation": "LEAD_GENERATION", "cta": "SIGN_UP"},
    "Conversions": {"optimisation": "CONVERSIONS", "cta": "SHOP_NOW"},
    "Sales": {"optimisation": "VALUE", "cta": "SHOP_NOW"},
    "Traffic": {"optimisation": "LINK_CLICKS", "cta": "LEARN_MORE"},
    "Video Views": {"optimisation": "THRUPLAY", "cta": "LEARN_MORE"},
    "Brand Awareness": {"optimisation": "BRAND_AWARENESS", "cta": "LEARN_MORE"},
    "Reach": {"optimisation": "REACH", "cta": "LEARN_MORE"},
    "Engagement": {"optimisation": "POST_ENGAGEMENT", "cta": "LEARN_MORE"},
    "App Installs": {"optimisation": "APP_INSTALLS", "cta": "DOWNLOAD"},
    "Messages": {"optimisation": "CONVERSATIONS", "cta": "CONTACT_US"}
}

def _coerce_time(val: Any) -> str:
    """Convert various time formats to YYYY-MM-DD HH:MM format."""
    if pd.isna(val) or val == "":
        return ""
    
    try:
        # Handle common formats
        if isinstance(val, str):
            val = val.strip()
            # Handle "YYYY-MM-DD HH:MM" format
            if len(val) == 16 and val[10] == ' ':
                return datetime.strptime(val, "%Y-%m-%d %H:%M").strftime("%Y-%m-%d %H:%M")
            # Handle "YYYY-MM-DD" format - add default time
            if len(val) == 10:
                return f"{val} 00:00"
        
        # Use pandas to parse and normalise
        dt = pd.to_datetime(val, utc=False, errors="raise")
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        raise ValueError(f"Invalid time format: {val}. Use YYYY-MM-DD HH:MM or YYYY-MM-DD")

def _pos_number(val: Any, allow_blank=True) -> str:
    """Convert to positive number, handling blanks appropriately."""
    if pd.isna(val) or str(val).strip() == "":
        return "" if allow_blank else "1"
    try:
        v = float(val)
        if v <= 0:
            raise ValueError("must be > 0")
        # Return as integer for budgets (Meta expects whole numbers)
        return str(int(round(v)))
    except (ValueError, TypeError):
        raise ValueError(f"Invalid positive number: {val}")

def _enum(val: Any, allowed: set, field: str, default: str = "") -> str:
    """Validate value against allowed set."""
    if pd.isna(val) or val == "":
        return default
    s = str(val).strip()
    if s not in allowed:
        raise ValueError(f"{field}: '{s}' not in {sorted(allowed)}")
    return s

def _gender(val: Any) -> str:
    """Handle gender field with proper defaults."""
    if pd.isna(val) or val == "":
        return "All"
    s = str(val).strip().title()
    if s not in VALID["gender"]:
        raise ValueError(f"Gender: '{val}' must be one of {sorted(VALID['gender'])}")
    return s

def _age_pair(minv: Any, maxv: Any, special_categories: str = "") -> Tuple[str, str]:
    """Handle age pair with Meta's minimum age requirements."""
    # Meta's minimum age is 13, but 18+ for special ad categories and many countries
    min_allowed = 13
    max_allowed = 65
    
    # Special ad categories require 18+ minimum
    if special_categories and str(special_categories).strip():
        min_allowed = 18
    
    # Handle blank values
    if pd.isna(minv) and pd.isna(maxv):
        return str(min_allowed), str(max_allowed)
    
    try:
        # Parse values
        min_age = int(minv) if not pd.isna(minv) and str(minv).strip() else min_allowed
        max_age = int(maxv) if not pd.isna(maxv) and str(maxv).strip() else max_allowed
        
        # Validate logical constraints
        if min_age > max_age:
            raise ValueError(f"Age Min ({min_age}) must be ≤ Age Max ({max_age})")
        
        # Enforce Meta platform constraints
        if min_age < min_allowed:
            min_age = min_allowed
        if max_age > max_allowed:
            max_age = max_allowed
            
        return str(min_age), str(max_age)
        
    except (ValueError, TypeError):
        raise ValueError(f"Invalid age pair: Min={minv}, Max={maxv}. Must be integers between {min_allowed}-{max_allowed}")

def _default_cta(objective: str, cta: str) -> str:
    """Get CTA with objective-based defaults."""
    if cta and str(cta).strip():
        return _enum(cta, VALID["cta"], "Call to Action")
    if objective in OBJ_DEFAULTS:
        return OBJ_DEFAULTS[objective]["cta"]
    return "LEARN_MORE"

def _default_opt_goal(objective: str, goal: str) -> str:
    """Get optimisation goal with objective-based defaults."""
    if goal and str(goal).strip():
        return str(goal).strip()
    if objective in OBJ_DEFAULTS:
        return OBJ_DEFAULTS[objective]["optimisation"]
    return "LINK_CLICKS"  # Safe default

def _process_utm_parameters(link: str, utm_params: str) -> Tuple[str, str]:
    """
    Process link and UTM parameters separately.
    UTM parameters should be proper query string format.
    """
    if pd.isna(link) or str(link).strip() == "":
        return "", ""
    
    clean_link = str(link).strip()
    
    if pd.isna(utm_params) or str(utm_params).strip() == "":
        # Generate default UTM parameters
        utm_default = "utm_source=facebook&utm_medium=cpc&utm_campaign=facebook_ads"
        return clean_link, utm_default
    
    clean_utm = str(utm_params).strip()
    
    # Validate UTM format (basic check for key=value pairs)
    if not ('=' in clean_utm and 'utm_' in clean_utm):
        raise ValueError(f"Invalid UTM format: '{clean_utm}'. Expected format: utm_source=facebook&utm_medium=cpc&utm_campaign=name")
    
    return clean_link, clean_utm

def transform(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Transform lightweight CSV format to Facebook Ads Manager bulk import format.
    
    Input: DataFrame with 'Input Level' column ('campaign' or 'adset')
    Campaign rows define campaign-level settings
    Adset rows inherit campaign settings and define ad set + creative
    
    Returns: (output_df, errors_df)
    """
    errors = []
    rows = []

    # Create copy and forward-fill campaign-level values
    df_ff = df.copy()
    
    # Campaign columns that should propagate down to adset rows
    campaign_cols = [
        "Campaign Name", "Campaign Status", "Special Ad Categories", 
        "Special Ad Category Country", "Campaign Objective", "Buying Type", 
        "Campaign Bid Strategy", "Campaign Daily Budget", "Campaign Start Time", 
        "Campaign Stop Time"
    ]
    
    # Forward fill campaign values
    for col in campaign_cols:
        if col in df_ff.columns:
            df_ff[col] = df_ff[col].ffill()

    # Process each row
    for idx, row in df_ff.iterrows():
        row_num = idx + 2  # Excel row number (1-indexed + header)
        level = str(row.get("Input Level", "")).lower().strip()
        
        if level not in {"campaign", "adset"}:
            errors.append({
                "row": row_num, 
                "field": "Input Level", 
                "error": "Must be 'campaign' or 'adset'"
            })
            continue

        try:
            if level == "campaign":
                # Process campaign row - simpler structure
                objective = _enum(
                    row.get("Campaign Objective", ""), 
                    VALID["objectives"], 
                    "Campaign Objective"
                )
                
                output_row = {
                    "Campaign Name": str(row.get("Campaign Name", "")).strip(),
                    "Campaign Status": _enum(
                        row.get("Campaign Status", "ACTIVE"), 
                        VALID["status"], 
                        "Campaign Status", 
                        "ACTIVE"
                    ),
                    "Special Ad Categories": str(row.get("Special Ad Categories", "")).strip(),
                    "Special Ad Category Country": str(row.get("Special Ad Category Country", "")).strip(),
                    "Campaign Objective": objective,
                    "Buying Type": _enum(
                        row.get("Buying Type", "AUCTION"), 
                        VALID["buying_type"], 
                        "Buying Type", 
                        "AUCTION"
                    ),
                    "Campaign Bid Strategy": _enum(
                        row.get("Campaign Bid Strategy", "Lowest cost"), 
                        VALID["bid_strategies"], 
                        "Campaign Bid Strategy", 
                        "Lowest cost"
                    ),
                    "Campaign Daily Budget": _pos_number(row.get("Campaign Daily Budget", "")),
                    "Campaign Start Time": _coerce_time(row.get("Campaign Start Time", "")),
                    "Campaign Stop Time": _coerce_time(row.get("Campaign Stop Time", "")),
                }
                rows.append(output_row)
                
            else:  # adset level
                # Process adset row - includes campaign, adset, and ad data
                objective = _enum(
                    row.get("Campaign Objective", ""), 
                    VALID["objectives"], 
                    "Campaign Objective"
                )
                
                # Handle budget conflict resolution
                campaign_budget = str(row.get("Campaign Daily Budget", "")).strip()
                adset_budget = str(row.get("Ad Set Daily Budget", "")).strip()
                
                # If both are specified, prefer adset budget and clear campaign budget
                if campaign_budget and adset_budget:
                    campaign_budget = ""
                
                # Process age ranges
                age_min, age_max = _age_pair(
                    row.get("Age Min", ""), 
                    row.get("Age Max", ""), 
                    row.get("Special Ad Categories", "")
                )
                
                # Process link and UTM parameters
                link, utm_tags = _process_utm_parameters(
                    row.get("Link", ""), 
                    row.get("URL Tags", "")
                )
                
                # Get defaults based on objective
                cta = _default_cta(objective, row.get("Call to Action", ""))
                opt_goal = _default_opt_goal(objective, row.get("Optimisation Goal", ""))
                
                output_row = {
                    # Campaign level (inherited)
                    "Campaign Name": str(row.get("Campaign Name", "")).strip(),
                    "Campaign Status": _enum(
                        row.get("Campaign Status", "ACTIVE"), 
                        VALID["status"], 
                        "Campaign Status", 
                        "ACTIVE"
                    ),
                    "Special Ad Categories": str(row.get("Special Ad Categories", "")).strip(),
                    "Special Ad Category Country": str(row.get("Special Ad Category Country", "")).strip(),
                    "Campaign Objective": objective,
                    "Buying Type": _enum(
                        row.get("Buying Type", "AUCTION"), 
                        VALID["buying_type"], 
                        "Buying Type", 
                        "AUCTION"
                    ),
                    "Campaign Bid Strategy": _enum(
                        row.get("Campaign Bid Strategy", "Lowest cost"), 
                        VALID["bid_strategies"], 
                        "Campaign Bid Strategy", 
                        "Lowest cost"
                    ),
                    "Campaign Daily Budget": _pos_number(campaign_budget) if campaign_budget else "",
                    "Campaign Start Time": _coerce_time(row.get("Campaign Start Time", "")),
                    "Campaign Stop Time": _coerce_time(row.get("Campaign Stop Time", "")),
                    
                    # Ad Set level
                    "Ad Set Name": str(row.get("Ad Set Name", "")).strip(),
                    "Ad Set Run Status": _enum(
                        row.get("Ad Set Run Status", "ACTIVE"), 
                        VALID["status"], 
                        "Ad Set Run Status", 
                        "ACTIVE"
                    ),
                    "Ad Set Daily Budget": _pos_number(adset_budget) if adset_budget else "",
                    "Ad Set Time Start": _coerce_time(row.get("Ad Set Time Start", "")),
                    "Ad Set Time Stop": _coerce_time(row.get("Ad Set Time Stop", "")),
                    "Countries": str(row.get("Countries", "")).strip(),
                    "Age Min": age_min,
                    "Age Max": age_max,
                    "Gender": _gender(row.get("Gender", "All")),
                    "Custom Audiences": str(row.get("Custom Audiences", "")).strip(),
                    "Excluded Custom Audiences": str(row.get("Excluded Custom Audiences", "")).strip(),
                    "Optimisation Goal": opt_goal,
                    
                    # Ad/Creative level
                    "Ad Name": str(row.get("Ad Name", "")).strip(),
                    "Ad Status": _enum(
                        row.get("Ad Status", "ACTIVE"), 
                        VALID["status"], 
                        "Ad Status", 
                        "ACTIVE"
                    ),
                    "Title": str(row.get("Title", "")).strip(),
                    "Body": str(row.get("Body", "")).strip(),
                    "Link": link,
                    "URL Tags": utm_tags,
                    "Call to Action": cta,
                    "Image File Name": str(row.get("Image File Name", "")).strip(),
                    
                    # Meta best practices
                    "Advantage+ placements": "true",  # Let Meta optimise placements
                }
                rows.append(output_row)
                
        except Exception as e:
            errors.append({
                "row": row_num,
                "field": level,
                "error": str(e)
            })

    # Create output DataFrame
    output_df = pd.DataFrame(rows)
    
    # Define column order for Meta Ads Manager compatibility
    column_order = [
        # Campaign
        "Campaign Name", "Campaign Status", "Special Ad Categories", 
        "Special Ad Category Country", "Campaign Objective", "Buying Type", 
        "Campaign Bid Strategy", "Campaign Daily Budget", "Campaign Start Time", 
        "Campaign Stop Time",
        
        # Ad Set
        "Ad Set Name", "Ad Set Run Status", "Ad Set Daily Budget", 
        "Ad Set Time Start", "Ad Set Time Stop", "Countries", "Age Min", "Age Max", 
        "Gender", "Custom Audiences", "Excluded Custom Audiences", "Optimisation Goal",
        
        # Ad/Creative
        "Ad Name", "Ad Status", "Title", "Body", "Link", "URL Tags", 
        "Call to Action", "Image File Name"
    ]
    
    # Ensure all columns exist and reorder
    for col in column_order:
        if col not in output_df.columns:
            output_df[col] = ""
    
    output_df = output_df[column_order]
    
    # Create errors DataFrame
    errors_df = pd.DataFrame(errors)
    
    return output_df, errors_df