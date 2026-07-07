"""GP practices fetcher: NHS ODS API for practice count + NHS.UK for accepting status.

No API key required — both endpoints are public.

Data sources:
  - NHS ODS (Spine Directory): GP practices per postcode prefix (PrimaryRoleId=RO177)
  - NHS.UK: accepting new patients status per practice page
"""

import re
import requests
from .. import http

_ODS_BASE = "https://directory.spineservices.nhs.uk/ORD/2-0-0/organisations"
_NHSUK_GP = "https://www.nhs.uk/services/gp-surgery/x/{code}"

# Filter out non-GP entries (pharmacies, ENT specialists, etc.)
_GP_KEYWORDS = {"SURGERY", "PRACTICE", "MEDICAL", "HEALTH", "DOCTOR", "GP",
                "CENTRE", "CENTER", "GROUP", "CLINIC"}
_NON_GP = {"PHARMACY", "DENTAL", "OPTICIAN", "CATS -", "PHYSIO", "CHIROPOD"}


def _is_gp(name: str) -> bool:
    upper = name.upper()
    if any(kw in upper for kw in _NON_GP):
        return False
    # If it has a GP keyword, definitely a GP
    if any(kw in upper for kw in _GP_KEYWORDS):
        return True
    # Otherwise, assume it's a GP if it has "Dr" or ends in common patterns
    return "DR " in upper or "DR." in upper


def _fetch_practices(outcode: str) -> list[dict]:
    """Fetch GP practices for an outcode from NHS ODS API."""
    data = http.get_json(
        _ODS_BASE,
        params={
            "PostCode": outcode,
            "PrimaryRoleId": "RO177",
            "Status": "Active",
            "Limit": "100",
        },
        headers={"Accept": "application/json"},
        cache_key=f"ods_gp:{outcode}",
    )
    orgs = data.get("Organisations", [])
    return [o for o in orgs if _is_gp(o.get("Name", ""))]


def _check_accepting(code: str) -> bool | None:
    """Check if a practice is accepting new patients via NHS.UK."""
    try:
        text = http.get_text(
            _NHSUK_GP.format(code=code),
            cache_key=f"nhsuk_gp:{code}",
            timeout=15,
        )
        if "not accepting" in text.lower():
            return False
        if "accepting new patients" in text.lower():
            return True
        return None  # unknown
    except Exception:
        return None


def fetch(row: dict) -> dict:
    """GP coverage metrics for a district.

    Returns:
      gp_count: number of GP practices in the outcode
      gp_accepting: number accepting new patients
      gp_accepting_pct: % accepting new patients (0-100)
    """
    outcode = row["district"]
    practices = _fetch_practices(outcode)
    gp_count = len(practices)

    if gp_count == 0:
        return {
            "gp_count": 0,
            "gp_accepting": 0,
            "gp_accepting_pct": 0.0,
        }

    accepting = 0
    checked = 0
    for p in practices:
        code = p.get("OrgId", "")
        if not code:
            continue
        status = _check_accepting(code)
        if status is True:
            accepting += 1
            checked += 1
        elif status is False:
            checked += 1
        # None = unknown, don't count

    pct = (accepting / checked * 100) if checked > 0 else 0.0

    return {
        "gp_count": gp_count,
        "gp_accepting": accepting,
        "gp_accepting_pct": round(pct, 1),
        "gp_coverage": min(gp_count, 5),  # capped at 5 — diminishing returns
    }
