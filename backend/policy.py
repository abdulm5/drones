"""Fail-closed catalog lookup, separate from operator acceptance."""
import json

from .config import ROOT

CATALOG = ROOT / "data/policy/products.json"


def check_policy(state_fips, crop_cdl_code, product_name, human_go=False, catalog=None):
    rows = json.loads(CATALOG.read_text()) if catalog is None else catalog
    matches = [row for row in rows if row["state_fips"] == state_fips
               and row["crop_cdl_code"] == crop_cdl_code
               and row["product_name"].casefold() == product_name.strip().casefold()]
    # Prohibition wins even if a future catalog accidentally contains conflicting rows.
    priority = {"prohibited": 0, "restricted": 1, "allowed": 2}
    row = min(matches, key=lambda r: priority.get(r["status"], -1)) if matches else None
    status = row["status"] if row else "unknown"
    policy_go = status == "allowed" or (status == "restricted" and human_go)
    reason = {"unknown": "No verified state/crop/product row. Unknown is a veto.",
              "prohibited": "Product use is prohibited by the cited state authority.",
              "restricted": "Restricted use: human GO is required; all cited restrictions still apply.",
              "allowed": "Catalog match found for this state, crop, and product."}.get(status, "Unrecognized status: veto.")
    return {"status": status, "policy_go": policy_go, "human_go": human_go,
            "application_unlocked": bool(policy_go and human_go), "reason": reason,
            "state_fips": state_fips, "crop_cdl_code": crop_cdl_code,
            "product_name": product_name or "No approved product", "row": row}
