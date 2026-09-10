"""Phase 1 - Synthetic data generator.

Simulates 24 months of B2B SaaS behaviour for ~500 fictional accounts, then
deliberately injects data-quality defects so that the Phase 3 checks have
something real to catch.

Design principles
-----------------
1. SEEDED. One random seed in config.yml -> anyone who clones this repo gets
   byte-identical data. Reproducibility is what makes the findings verifiable.
2. BEHAVIOURAL, not uniform. Random uniform data produces flat metrics and
   teaches nothing. Accounts here follow archetypes (healthy, declining,
   seasonal, zero-usage...) so the analysis has something real to find.
3. DEFECTS ARE INTENTIONAL and catalogued in docs/data_dictionary.md section 7.

Run with:  python -m src.generate_data
"""

from __future__ import annotations

import logging
import time

import numpy as np
import pandas as pd

from src.utils.config import RAW_DIR, ensure_dirs, load_config
from src.utils.logging_config import setup_logging

log = logging.getLogger("generate")


# =============================================================================
# Reference data: the feature catalog
# =============================================================================
# This is a SEED table - hand-maintained configuration, not generated data.
# It is the source of truth for two things:
#   - which feature_area an event belongs to
#   - is_core_action: whether the event counts as real "usage"
# Without it, "active" would mean "logged in", which overstates engagement.
FEATURE_CATALOG = [
    # event_name,             feature_area,     is_core, adoption_tier, launched
    ("doc_created",           "documents",      True,  "basic",    "2023-01-01"),
    ("doc_edited",            "documents",      True,  "basic",    "2023-01-01"),
    ("doc_viewed",            "documents",      False, "basic",    "2023-01-01"),
    ("doc_shared",            "documents",      True,  "advanced", "2023-01-01"),
    ("template_used",         "documents",      True,  "advanced", "2023-01-01"),
    ("report_run",            "reporting",      True,  "basic",    "2023-01-01"),
    ("dashboard_created",     "reporting",      True,  "advanced", "2023-01-01"),
    ("dashboard_viewed",      "reporting",      False, "basic",    "2023-01-01"),
    ("report_scheduled",      "reporting",      True,  "power",    "2023-01-01"),
    ("data_exported",         "reporting",      True,  "advanced", "2023-01-01"),
    ("comment_added",         "collaboration",  True,  "basic",    "2023-01-01"),
    ("mention_created",       "collaboration",  True,  "basic",    "2023-01-01"),
    ("task_assigned",         "collaboration",  True,  "advanced", "2023-01-01"),
    ("integration_connected", "integrations",   True,  "advanced", "2023-01-01"),
    ("integration_synced",    "integrations",   True,  "power",    "2023-01-01"),
    ("api_call",              "integrations",   True,  "power",    "2025-01-15"),
    ("automation_created",    "automation",     True,  "power",    "2025-06-01"),
    ("automation_run",        "automation",     True,  "power",    "2025-06-01"),
    ("user_invited",          "admin",          True,  "basic",    "2023-01-01"),
    ("permission_changed",    "admin",          False, "advanced", "2023-01-01"),
    ("session_start",         "admin",          False, "basic",    "2023-01-01"),
]

FEATURE_DESCRIPTIONS = {
    "doc_created": "A new document was created",
    "doc_edited": "An existing document was edited",
    "doc_viewed": "A document was opened for reading (passive)",
    "doc_shared": "A document was shared with another user",
    "template_used": "A document was created from a template",
    "report_run": "A report was executed",
    "dashboard_created": "A dashboard was created",
    "dashboard_viewed": "A dashboard was opened (passive)",
    "report_scheduled": "A recurring report schedule was configured",
    "data_exported": "Data was exported to CSV/Excel",
    "comment_added": "A comment was added to a document",
    "mention_created": "Another user was @-mentioned",
    "task_assigned": "A task was assigned to a user",
    "integration_connected": "A third-party integration was connected",
    "integration_synced": "An integration sync ran",
    "api_call": "A call was made to the public API",
    "automation_created": "An automation workflow was created",
    "automation_run": "An automation workflow executed",
    "user_invited": "A new user was invited to the workspace",
    "permission_changed": "A permission or role was changed (passive)",
    "session_start": "A user session began (passive - NOT real usage)",
}

INDUSTRIES = [
    "Technology", "Retail", "Healthcare", "Financial Services",
    "Manufacturing", "Education", "Non-profit", "Professional Services",
]
COUNTRIES = ["United States", "United Kingdom", "Canada", "Germany", "Australia", "India"]
EMPLOYEE_BANDS = ["1-50", "51-200", "201-1000", "1000+"]
CHANNELS = ["inbound", "outbound", "partner", "self_serve", "referral"]
DEPARTMENTS = ["Engineering", "Marketing", "Sales", "Operations", "Finance", "Other"]
ROLES = ["admin", "editor", "viewer"]
CSM_NAMES = [
    "A. Okafor", "B. Lindqvist", "C. Moreau", "D. Sharma",
    "E. Rossi", "F. Tanaka", "G. Alvarez", "H. Nowak",
]

# Seats and pricing per plan tier: (min_seats, max_seats, mrr_per_seat)
PLAN_SPECS = {
    "starter":    (5,   20,  12.0),
    "growth":     (18,  55,  22.0),
    "business":   (45,  120, 34.0),
    "enterprise": (90,  240, 48.0),
}

# Words used to build fake company names
NAME_PREFIX = [
    "North", "Blue", "Iron", "Summit", "Cedar", "Vertex", "Harbor", "Lumen",
    "Quartz", "Aster", "Pinnacle", "Onyx", "Meridian", "Corvus", "Halcyon",
    "Granite", "Willow", "Cobalt", "Solstice", "Emberly", "Riverstone", "Kestrel",
]
NAME_SUFFIX = [
    "Labs", "Group", "Systems", "Partners", "Industries", "Collective",
    "Technologies", "Holdings", "Works", "Dynamics", "Analytics", "Solutions",
]


# =============================================================================
# Behavioural archetypes
# =============================================================================
def monthly_curve(
    archetype: str,
    n_months: int,
    first_month: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Return a length-n_months array of usage multipliers for one account.

    Index 0 is the first month of the simulation window. Months before the
    account signed up are 0. This is the heart of the simulation: the shape of
    this curve is what the Phase 5 trend analysis will later have to detect.
    """
    t = np.arange(n_months)
    curve = np.ones(n_months, dtype=float)

    def pick_month(earliest: int, latest: int) -> int:
        """Choose a change-point month, safely.

        Late-joining accounts may have almost no runway left in the window, so
        the lower bound can exceed the upper bound. Guarding here rather than at
        every call site keeps the archetype logic readable.
        """
        lo = min(max(earliest, 1), n_months - 1)
        hi = max(lo + 1, min(latest, n_months))
        return int(rng.integers(lo, hi))

    if archetype == "healthy_stable":
        curve *= 1.0
    elif archetype == "growing":
        curve = 1.0 * np.power(rng.uniform(1.02, 1.06), t)
    elif archetype == "slow_decliner":
        # Healthy for a while, then a compounding decay of 8-16% per month.
        start = pick_month(first_month + 4, n_months - 3)
        decay = rng.uniform(0.84, 0.92)
        curve = np.where(t < start, 1.0, np.power(decay, t - start))
    elif archetype == "cliff_decliner":
        # A champion leaves: usage falls off a cliff in a single month.
        drop_at = pick_month(first_month + 5, n_months - 2)
        curve = np.where(t < drop_at, 1.0, rng.uniform(0.08, 0.22))
    elif archetype == "seasonal":
        # A genuine, expected annual cycle. These accounts exist to punish a
        # naive "any decline = risk" rule.
        phase = rng.uniform(0, 2 * np.pi)
        curve = 1.0 + 0.5 * np.sin(2 * np.pi * t / 12.0 + phase)
    elif archetype == "zero_usage":
        # Paid, never activated. A tiny flicker of onboarding then nothing.
        curve = np.zeros(n_months)
        curve[first_month : first_month + 1] = rng.uniform(0.0, 0.03)
    elif archetype == "power_user":
        curve = 1.7 * np.power(rng.uniform(1.01, 1.04), t)
    elif archetype == "single_champion":
        curve *= rng.uniform(0.6, 0.9)

    # Onboarding ramp: nobody hits full usage in week one.
    ramp = np.array([0.30, 0.65, 0.9])
    for i, r in enumerate(ramp):
        idx = first_month + i
        if idx < n_months:
            curve[idx] *= r

    # Month-to-month noise so trends are not suspiciously smooth.
    curve *= rng.normal(1.0, 0.13, n_months).clip(0.35, 1.9)

    # No usage before the account existed.
    curve[:first_month] = 0.0
    return curve.clip(0.0, None)


# =============================================================================
# Table generators
# =============================================================================
def make_accounts(cfg: dict, rng: np.random.Generator) -> pd.DataFrame:
    n = cfg["generation"]["n_accounts"]
    n_test = cfg["generation"]["internal_test_accounts"]
    start = pd.Timestamp(cfg["generation"]["start_date"])
    end = pd.Timestamp(cfg["generation"]["end_date"])

    # Signup dates: most accounts predate the window (established customer base),
    # the rest sign up during it, so we get real cohort variety.
    n_existing = int(n * 0.62)
    existing = start - pd.to_timedelta(rng.integers(30, 900, n_existing), unit="D")
    window_days = (end - start).days
    # Weight new signups toward earlier months so they have usage history.
    new_offsets = (rng.beta(1.4, 2.4, n - n_existing) * window_days * 0.8).astype(int)
    joiners = start + pd.to_timedelta(new_offsets, unit="D")
    signup = pd.to_datetime(np.concatenate([existing.values, joiners.values]))

    # Build plausible company names, made unique with a trailing number.
    names = [
        f"{NAME_PREFIX[i % len(NAME_PREFIX)]}{NAME_SUFFIX[(i * 7) % len(NAME_SUFFIX)]} {i + 1:03d}"
        for i in range(n)
    ]

    df = pd.DataFrame({
        "account_id": [f"ACC-{i:05d}" for i in range(1, n + 1)],
        "account_name": names,
        "industry": rng.choice(INDUSTRIES, n, p=[.22, .14, .13, .15, .11, .09, .06, .10]),
        "country": rng.choice(COUNTRIES, n, p=[.46, .16, .11, .10, .09, .08]),
        "employee_band": rng.choice(EMPLOYEE_BANDS, n, p=[.34, .31, .24, .11]),
        "signup_date": signup.normalize(),
        "acquisition_channel": rng.choice(CHANNELS, n, p=[.28, .18, .14, .30, .10]),
        "csm_owner": rng.choice(CSM_NAMES, n),
        "is_internal_test": False,
    })
    df = df.sort_values("signup_date").reset_index(drop=True)
    df["account_id"] = [f"ACC-{i:05d}" for i in range(1, n + 1)]

    # Internal/demo accounts - realistic pollution that must be excluded.
    test_rows = pd.DataFrame({
        "account_id": [f"ACC-9{i:04d}" for i in range(1, n_test + 1)],
        "account_name": [f"INTERNAL DEMO {i}" for i in range(1, n_test + 1)],
        "industry": "Technology",
        "country": "United States",
        "employee_band": "1000+",
        "signup_date": start - pd.Timedelta(days=800),
        "acquisition_channel": "self_serve",
        "csm_owner": None,
        "is_internal_test": True,
    })
    return pd.concat([df, test_rows], ignore_index=True)


def assign_archetypes(accounts: pd.DataFrame, cfg: dict, rng: np.random.Generator) -> pd.Series:
    mix = cfg["generation"]["archetype_mix"]
    kinds = list(mix.keys())
    probs = np.array([mix[k] for k in kinds], dtype=float)
    probs = probs / probs.sum()
    arche = pd.Series(rng.choice(kinds, len(accounts), p=probs), index=accounts.index)
    arche[accounts["is_internal_test"].to_numpy()] = "power_user"
    return arche


def make_subscriptions(
    accounts: pd.DataFrame, cfg: dict, rng: np.random.Generator, archetypes: pd.Series
) -> pd.DataFrame:
    """One row per subscription TERM. Accounts that renew get multiple rows.

    This grain is the single most common modelling mistake in SaaS data: assume
    one row per account, join it to usage, and silently multiply your revenue.
    """
    mix = cfg["generation"]["plan_mix"]
    tiers = list(mix.keys())
    probs = np.array([mix[t] for t in tiers], dtype=float) / sum(mix.values())
    end_window = pd.Timestamp(cfg["generation"]["end_date"])

    rows = []
    sub_n = 0
    for i, acct in accounts.iterrows():
        tier = rng.choice(tiers, p=probs)
        lo, hi, price = PLAN_SPECS[tier]
        seats = int(rng.integers(lo, hi + 1))
        annual = rng.random() < (0.75 if tier in ("business", "enterprise") else 0.35)
        # NOTE: billing_frequency is how the customer is INVOICED (monthly or
        # up-front). The contract TERM is 12 months either way - which is how
        # most B2B SaaS actually works. Modelling monthly invoices as separate
        # subscription terms would give ~24 rows per account and make the
        # "one row per term" grain meaningless.
        term_len = 365

        # Decliners are the ones who eventually churn.
        will_churn = archetypes[i] in ("slow_decliner", "cliff_decliner", "zero_usage")
        churn_roll = rng.random() < (0.55 if will_churn else 0.05)

        cursor = acct["signup_date"]
        term_no = 0
        while cursor < end_window:
            sub_n += 1
            term_no += 1
            term_end = cursor + pd.Timedelta(days=term_len)
            last_term = term_end >= end_window

            if churn_roll and not last_term and rng.random() < 0.35 and term_no >= 2:
                status, cancel_reason = "churned", rng.choice(
                    ["low_usage", "budget_cut", "competitor", "champion_left", "merger"]
                )
            elif last_term:
                status, cancel_reason = "active", None
            else:
                status, cancel_reason = "renewed", None

            rows.append({
                "subscription_id": f"SUB-{sub_n:05d}",
                "account_id": acct["account_id"],
                "plan_tier": tier,
                "seats_licensed": seats,
                "mrr_usd": round(seats * price * rng.uniform(0.85, 1.05), 2),
                "billing_frequency": "annual" if annual else "monthly",
                "term_start_date": cursor,
                "term_end_date": term_end,
                "status": status,
                "cancel_reason": cancel_reason,
            })

            if status == "churned":
                break

            cursor = term_end
            # Expansion / contraction at renewal
            if rng.random() < 0.18:
                seats = max(3, int(seats * rng.uniform(1.05, 1.45)))
            elif rng.random() < 0.10:
                seats = max(3, int(seats * rng.uniform(0.6, 0.92)))

    return pd.DataFrame(rows)


def make_users(
    accounts: pd.DataFrame, subs: pd.DataFrame, cfg: dict, rng: np.random.Generator
) -> pd.DataFrame:
    """One row per user seat. Provisioned over time, some deactivated."""
    end_window = pd.Timestamp(cfg["generation"]["end_date"])
    first_seats = (
        subs.sort_values("term_start_date")
        .groupby("account_id", as_index=False)
        .first()[["account_id", "seats_licensed"]]
        .set_index("account_id")["seats_licensed"]
    )

    rows = []
    uid = 0
    for _, acct in accounts.iterrows():
        seats = int(first_seats.get(acct["account_id"], 8))
        # Accounts rarely fill every seat they buy.
        n_users = max(1, int(seats * rng.uniform(0.55, 1.0)))
        signup = acct["signup_date"]
        max_days = max(1, (end_window - signup).days)

        for j in range(n_users):
            uid += 1
            # The first user (admin) is created at signup; the rest trickle in.
            offset = 0 if j == 0 else int(min(max_days, rng.exponential(120)))
            created = signup + pd.Timedelta(days=offset)
            role = "admin" if j == 0 else rng.choice(ROLES, p=[0.08, 0.62, 0.30])

            deactivated = None
            if rng.random() < 0.14:
                life = int(rng.integers(60, 700))
                cand = created + pd.Timedelta(days=life)
                if cand < end_window:
                    deactivated = cand

            rows.append({
                "user_id": f"USR-{uid:06d}",
                "account_id": acct["account_id"],
                "user_created_date": created.normalize(),
                "deactivated_date": None if deactivated is None else deactivated.normalize(),
                "role": role,
                "department": rng.choice(DEPARTMENTS, p=[.22, .18, .20, .17, .10, .13]),
                "email_domain": acct["account_name"].split()[0].lower().replace(" ", "") + ".com",
                "invited_by_user_id": None if j == 0 else f"USR-{uid - j:06d}",
            })
    return pd.DataFrame(rows)


def make_events(
    accounts: pd.DataFrame,
    users: pd.DataFrame,
    subs: pd.DataFrame,
    archetypes: pd.Series,
    cfg: dict,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """The big one: one row per product event.

    Strategy (vectorised, ~seconds rather than ~hours):
      1. Build a daily intensity (lambda) array per account across the window.
      2. Draw a Poisson count per day -> how many events happened that day.
      3. Expand counts into rows with np.repeat.
      4. Assign users by weighted sampling, respecting who existed at the time.
    """
    start = pd.Timestamp(cfg["generation"]["start_date"])
    end = pd.Timestamp(cfg["generation"]["end_date"])
    days = pd.date_range(start, end, freq="D")
    n_days = len(days)
    day_ord = np.arange(n_days)
    months = pd.PeriodIndex(days, freq="M")
    month_index = (months - months[0]).n if hasattr(months - months[0], "n") else None
    month_of_day = np.array([(p.year - months[0].year) * 12 + (p.month - months[0].month) for p in months])
    n_months = int(month_of_day.max()) + 1
    days_per_month = np.bincount(month_of_day, minlength=n_months)

    # Weekday seasonality: Mon-Fri busy, weekends quiet. dayofweek: Mon=0 .. Sun=6
    dow = days.dayofweek.to_numpy()
    weekday_factor = np.where(dow >= 5, 0.18, 1.0) * np.where(dow == 4, 0.85, 1.0)

    catalog = pd.DataFrame(
        FEATURE_CATALOG, columns=["event_name", "feature_area", "is_core_action", "adoption_tier", "launched_date"]
    )
    catalog["launched_date"] = pd.to_datetime(catalog["launched_date"])
    ev_names = catalog["event_name"].to_numpy()
    ev_area = dict(zip(catalog["event_name"], catalog["feature_area"]))
    ev_area_arr = catalog["feature_area"].to_numpy()
    ev_tier_arr = catalog["adoption_tier"].to_numpy()
    ev_launch = catalog["launched_date"].to_numpy()
    # Every account does some admin; these are the areas they may or may not adopt.
    optional_areas = np.array(
        ["documents", "reporting", "collaboration", "integrations", "automation"]
    )
    tier_weight = {"basic": 1.0, "advanced": 0.45, "power": 0.18}

    # Last day each account is "alive" (churn ends the event stream).
    sub_end = subs.groupby("account_id")["term_end_date"].max()
    churned = subs[subs["status"] == "churned"].groupby("account_id")["term_end_date"].min()

    users_by_acct = {aid: g for aid, g in users.groupby("account_id", sort=False)}

    frames = []
    total = 0
    for i, acct in accounts.iterrows():
        aid = acct["account_id"]
        u = users_by_acct.get(aid)
        if u is None or len(u) == 0:
            continue

        arch = archetypes[i]
        signup = acct["signup_date"]
        first_month = int(max(0, (signup.year - start.year) * 12 + (signup.month - start.month)))
        if first_month >= n_months:
            continue

        # ---- 1. monthly shape -> daily lambda -----------------------------
        curve = monthly_curve(arch, n_months, first_month, rng)

        seats = int(subs.loc[subs["account_id"] == aid, "seats_licensed"].iloc[0])
        active_users = max(1, int(seats * rng.uniform(0.30, 0.65)))
        per_user_month = rng.uniform(9, 24)
        if acct["is_internal_test"]:
            per_user_month *= 14  # absurd volume: the classic test-account outlier
        base_monthly = active_users * per_user_month

        monthly_events = base_monthly * curve
        daily_lambda = monthly_events[month_of_day] / days_per_month[month_of_day]
        daily_lambda = daily_lambda * weekday_factor

        # Silence the stream before signup and after churn.
        daily_lambda[day_ord < (signup - start).days] = 0.0
        if aid in churned.index:
            stop = (churned.loc[aid] - start).days
            daily_lambda[day_ord >= stop] = 0.0
        elif aid in sub_end.index:
            stop = (sub_end.loc[aid] - start).days
            daily_lambda[day_ord >= stop] = 0.0

        counts = rng.poisson(daily_lambda)
        n_ev = int(counts.sum())
        if n_ev == 0:
            continue
        total += n_ev

        # ---- 2. expand counts into one row per event ----------------------
        ev_day = np.repeat(day_ord, counts)

        # ---- 3. assign users -------------------------------------------------
        u = u.sort_values("user_created_date")
        created_ord = ((pd.to_datetime(u["user_created_date"]) - start).dt.days).to_numpy()
        uids = u["user_id"].to_numpy()
        deact = pd.to_datetime(u["deactivated_date"])
        deact_ord = np.where(deact.isna(), 10**6, (deact - start).dt.days).astype(float)

        # Pareto weights: a few power users do most of the work (realistic).
        w = rng.pareto(1.3, len(u)) + 0.25
        if arch == "single_champion":
            w[:] = 0.05
            w[0] = 20.0
        cumw = np.cumsum(w)

        # How many users existed on each event's day?
        k = np.searchsorted(created_ord, ev_day, side="right")
        keep = k > 0
        ev_day, k = ev_day[keep], k[keep]
        if len(ev_day) == 0:
            continue
        r = rng.random(len(ev_day)) * cumw[k - 1]
        u_idx = np.searchsorted(cumw, r, side="left").clip(0, len(u) - 1)

        # Drop events by users who had already been deactivated.
        alive = ev_day < deact_ord[u_idx]
        ev_day, u_idx = ev_day[alive], u_idx[alive]
        if len(ev_day) == 0:
            continue

        # ---- 4. event names, weighted by this account's adoption profile ---
        # Each account ADOPTS ONLY SOME feature areas. Breadth of adoption is
        # one of the strongest health signals in real B2B SaaS, so it has to
        # vary genuinely between accounts - if everyone uses everything, the
        # Phase 6 adoption analysis has nothing to say.
        if arch in ("power_user", "growing"):
            n_areas = int(rng.integers(4, 6))
        elif arch in ("zero_usage", "single_champion", "cliff_decliner"):
            n_areas = int(rng.integers(1, 3))
        elif seats >= 90:
            n_areas = int(rng.integers(2, 5))
        else:
            n_areas = int(rng.integers(1, 4))
        adopted = set(rng.choice(optional_areas, size=n_areas, replace=False))
        adopted.add("admin")

        # Within adopted areas, advanced/power features are used far less than
        # basic ones - that is what makes "depth of adoption" a real metric.
        prof = np.array([
            tier_weight[t] * rng.uniform(0.35, 1.7) if a in adopted else 0.0
            for a, t in zip(ev_area_arr, ev_tier_arr)
        ])
        if prof.sum() <= 0:
            continue
        prof = prof / prof.sum()
        ev_name_idx = rng.choice(len(ev_names), size=len(ev_day), p=prof)
        names_arr = ev_names[ev_name_idx]

        # Features cannot be used before they launched.
        ev_ts_day = start + pd.to_timedelta(ev_day, unit="D")
        launched_ok = ev_ts_day.to_numpy() >= ev_launch[ev_name_idx]
        ev_day, u_idx, ev_name_idx = ev_day[launched_ok], u_idx[launched_ok], ev_name_idx[launched_ok]
        names_arr = names_arr[launched_ok]
        if len(ev_day) == 0:
            continue

        n = len(ev_day)
        # Timestamp within the working day (business-hours shaped).
        secs = (rng.normal(13.5, 3.0, n).clip(5.5, 23.0) * 3600).astype(int)
        ts = start + pd.to_timedelta(ev_day, unit="D") + pd.to_timedelta(secs, unit="s")

        surface = rng.choice(["web", "mobile", "api"], n, p=[0.80, 0.13, 0.07])
        qty = np.where(names_arr == "api_call", rng.integers(1, 40, n), 1)

        frames.append(pd.DataFrame({
            "account_id": aid,
            "user_id": uids[u_idx],
            "event_ts": ts,
            "event_name": names_arr,
            "feature_area": pd.Series(names_arr).map(ev_area).to_numpy(),
            "surface": surface,
            "session_bucket": (u_idx.astype(np.int64) * 1000 + ev_day) * 3 + rng.integers(0, 3, n),
            "event_qty": qty,
            "duration_ms": rng.lognormal(7.4, 0.9, n).astype(int),
        }))

    log.info("expanding %s raw event rows into a single frame", f"{total:,}")
    events = pd.concat(frames, ignore_index=True)
    events = events.sort_values("event_ts", kind="stable").reset_index(drop=True)
    events.insert(0, "event_id", [f"EVT-{i:09d}" for i in range(1, len(events) + 1)])
    events["session_id"] = "SES-" + events["session_bucket"].astype(str)
    events = events.drop(columns=["session_bucket"])
    return events


def make_support_tickets(
    accounts: pd.DataFrame, users: pd.DataFrame, cfg: dict, rng: np.random.Generator
) -> pd.DataFrame:
    start = pd.Timestamp(cfg["generation"]["start_date"])
    end = pd.Timestamp(cfg["generation"]["end_date"])
    span = (end - start).days

    n = 6000
    acct_pick = rng.choice(accounts["account_id"].to_numpy(), n)
    user_lookup = users.groupby("account_id")["user_id"].apply(list).to_dict()
    requester = [
        rng.choice(user_lookup[a]) if (a in user_lookup and rng.random() < 0.85) else None
        for a in acct_pick
    ]
    created = start + pd.to_timedelta(rng.integers(0, span, n), unit="D") + pd.to_timedelta(
        rng.integers(0, 86400, n), unit="s"
    )
    resolve_hours = rng.lognormal(2.6, 1.1, n)
    resolved = created + pd.to_timedelta(resolve_hours, unit="h")
    open_mask = rng.random(n) < 0.06

    return pd.DataFrame({
        "ticket_id": [f"TIC-{i:06d}" for i in range(1, n + 1)],
        "account_id": acct_pick,
        "user_id": requester,
        "created_ts": created,
        "resolved_ts": pd.Series(resolved).where(~open_mask),
        "priority": rng.choice(["low", "medium", "high", "urgent"], n, p=[.34, .40, .19, .07]),
        "category": rng.choice(
            ["bug", "how_to", "billing", "feature_request", "outage"], n, p=[.28, .38, .14, .17, .03]
        ),
        # Most surveys go unanswered - realistic, and a good NULL-handling lesson.
        "csat_score": pd.Series(rng.integers(1, 6, n)).where(rng.random(n) < 0.22),
    }).sort_values("created_ts").reset_index(drop=True)


# =============================================================================
# Defect injection - see docs/data_dictionary.md section 7
# =============================================================================
def inject_defects(
    accounts: pd.DataFrame,
    users: pd.DataFrame,
    subs: pd.DataFrame,
    events: pd.DataFrame,
    cfg: dict,
    rng: np.random.Generator,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]:
    d = cfg["generation"]["defects"]
    notes: list[str] = []

    # (2) duplicate account rows
    dup_a = accounts.sample(d["duplicate_account_rows"], random_state=1)
    accounts = pd.concat([accounts, dup_a], ignore_index=True)
    notes.append(f"{len(dup_a)} duplicate account_id rows")

    # (12)(13) casing / whitespace / country-code variants
    n_case = int(len(accounts) * d["casing_variant_rate"])
    idx = rng.choice(accounts.index, n_case, replace=False)
    accounts.loc[idx, "industry"] = accounts.loc[idx, "industry"].apply(
        lambda s: rng.choice([f" {s} ", str(s).upper(), str(s).lower()]) if pd.notna(s) else s
    )
    notes.append(f"{n_case} casing/whitespace variants in industry")

    us = accounts.index[accounts["country"] == "United States"]
    swap = rng.choice(us, min(len(us), 90), replace=False)
    accounts.loc[swap, "country"] = rng.choice(["US", "USA", "u.s.a."], len(swap))
    notes.append(f"{len(swap)} country values written as US/USA/u.s.a.")

    # (3) NULLs
    n_null = int(len(accounts) * d["null_industry_rate"])
    accounts.loc[rng.choice(accounts.index, n_null, replace=False), "industry"] = None
    n_dep = int(len(users) * d["null_department_rate"])
    users.loc[rng.choice(users.index, n_dep, replace=False), "department"] = None
    notes.append(f"{n_null} null industries, {n_dep} null departments")

    # (9) orphan users - account_id that does not exist
    orph_u = rng.choice(users.index, d["orphan_account_users"], replace=False)
    users.loc[orph_u, "account_id"] = "ACC-99999"
    notes.append(f"{len(orph_u)} users pointing at a non-existent account")

    # (6) invalid subscription terms: end before start
    bad = rng.choice(subs.index, d["invalid_subscription_terms"], replace=False)
    subs.loc[bad, "term_end_date"] = subs.loc[bad, "term_start_date"] - pd.Timedelta(days=20)
    notes.append(f"{len(bad)} subscription terms ending before they start")

    # (7) overlapping terms - breaks point-in-time joins
    ov = rng.choice(subs.index, d["overlapping_subscription_terms"], replace=False)
    subs.loc[ov, "term_start_date"] = subs.loc[ov, "term_start_date"] - pd.Timedelta(days=95)
    notes.append(f"{len(ov)} overlapping subscription terms")

    # (11) impossible values
    inv = rng.choice(subs.index, d["invalid_seats"], replace=False)
    subs.loc[inv, "seats_licensed"] = rng.choice([0, -5, -1], len(inv))
    notes.append(f"{len(inv)} subscriptions with zero/negative seats")

    neg = rng.choice(events.index, d["negative_event_qty"], replace=False)
    events.loc[neg, "event_qty"] = -rng.integers(1, 9, len(neg))
    notes.append(f"{len(neg)} events with negative quantity")

    # (4) events before the account signed up
    n_pre = int(len(events) * d["pre_signup_event_rate"])
    pre = rng.choice(events.index, n_pre, replace=False)
    events.loc[pre, "event_ts"] = events.loc[pre, "event_ts"] - pd.Timedelta(days=1200)
    notes.append(f"{n_pre} events dated before the account existed")

    # (5) future-dated events
    fut = rng.choice(events.index, d["future_dated_events"], replace=False)
    events.loc[fut, "event_ts"] = pd.Timestamp("2027-03-14 09:00:00")
    notes.append(f"{len(fut)} future-dated events")

    # (8) orphan user_id on events
    orph_e = rng.choice(events.index, d["orphan_user_events"], replace=False)
    events.loc[orph_e, "user_id"] = "USR-999999"
    notes.append(f"{len(orph_e)} events referencing a non-existent user")

    # (10) event account_id disagrees with the user's account
    mism = rng.choice(events.index, d["account_mismatch_events"], replace=False)
    events.loc[mism, "account_id"] = rng.choice(accounts["account_id"].to_numpy(), len(mism))
    notes.append(f"{len(mism)} events whose account_id contradicts the user's account")

    # (16) denormalised feature_area drifts away from the catalog
    n_fa = d.get("feature_area_mismatch_events", 0)
    if n_fa:
        fa = rng.choice(events.index, n_fa, replace=False)
        events.loc[fa, "feature_area"] = rng.choice(
            ["documents", "reporting", "collaboration", "integrations"], n_fa
        )
        notes.append(f"{n_fa} events whose feature_area disagrees with the catalog")

    # (1) exact duplicate event rows
    n_dup = int(len(events) * d["duplicate_event_rate"])
    dup_e = events.sample(n_dup, random_state=7)
    events = pd.concat([events, dup_e], ignore_index=True)
    notes.append(f"{n_dup} exact duplicate event rows")

    return accounts, users, subs, events, notes


# =============================================================================
# Main
# =============================================================================
def main() -> None:
    setup_logging()
    t0 = time.time()
    cfg = load_config()
    ensure_dirs()
    rng = np.random.default_rng(cfg["project"]["random_seed"])

    log.info("generating accounts ...")
    accounts = make_accounts(cfg, rng)
    archetypes = assign_archetypes(accounts, cfg, rng)

    log.info("generating subscriptions ...")
    subs = make_subscriptions(accounts, cfg, rng, archetypes)

    log.info("generating users ...")
    users = make_users(accounts, subs, cfg, rng)

    log.info("generating usage events (this is the slow part) ...")
    events = make_events(accounts, users, subs, archetypes, cfg, rng)

    log.info("generating support tickets ...")
    tickets = make_support_tickets(accounts, users, cfg, rng)

    log.info("injecting deliberate data-quality defects ...")
    accounts, users, subs, events, notes = inject_defects(accounts, users, subs, events, cfg, rng)

    catalog = pd.DataFrame(
        FEATURE_CATALOG,
        columns=["event_name", "feature_area", "is_core_action", "adoption_tier", "launched_date"],
    )
    catalog["description"] = catalog["event_name"].map(FEATURE_DESCRIPTIONS)

    # ---- write -----------------------------------------------------------
    # Small tables as plain CSV (human-readable, diffable).
    # Events gzipped: millions of rows, and DuckDB reads .csv.gz natively.
    log.info("writing files to %s", RAW_DIR)
    accounts.to_csv(RAW_DIR / "accounts.csv", index=False)
    users.to_csv(RAW_DIR / "users.csv", index=False)
    subs.to_csv(RAW_DIR / "subscriptions.csv", index=False)
    tickets.to_csv(RAW_DIR / "support_tickets.csv", index=False)
    catalog.to_csv(RAW_DIR / "feature_catalog.csv", index=False)
    events.to_csv(RAW_DIR / "product_usage_events.csv.gz", index=False, compression="gzip")

    # A generation manifest: what was produced, and what defects were planted.
    lines = [
        "# Data Generation Summary",
        "",
        f"Seed: `{cfg['project']['random_seed']}` - re-running produces identical data.",
        "",
        "## Row counts",
        "",
        "| table | rows |",
        "|---|---|",
        f"| accounts | {len(accounts):,} |",
        f"| users | {len(users):,} |",
        f"| subscriptions | {len(subs):,} |",
        f"| product_usage_events | {len(events):,} |",
        f"| support_tickets | {len(tickets):,} |",
        f"| feature_catalog | {len(catalog):,} |",
        "",
        "## Deliberately injected defects",
        "",
        *[f"- {n}" for n in notes],
        "",
        "> These are planted on purpose so the Phase 3 quality checks have",
        "> something real to catch. See docs/data_dictionary.md section 7.",
    ]
    (RAW_DIR / "GENERATION_SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")

    log.info("done in %.1fs | %s events", time.time() - t0, f"{len(events):,}")
    for n in notes:
        log.info("  defect: %s", n)


if __name__ == "__main__":
    main()
