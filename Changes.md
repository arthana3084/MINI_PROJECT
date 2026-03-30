# MindWatch — Recent Changes

This document summarizes the updates made to the **MindWatch** mental health screening application, written for **presentation and demo** purposes. It covers what changed, why it matters, and where it lives in the project.

---

## 1. Overview

The app now supports:

- **Guests** — full use of the assessment flow with **browser-only history** (no login required).
- **Optional accounts** — sign in to **save reports on the server** and open them later from a dedicated **Past reports** area.
- A **consistent navigation bar** across main screens, including sign-in links or a **profile-style display** when logged in.

---

## 2. Session History in the Browser (localStorage)

### What we built

- After each completed checklist assessment, key summary fields are stored in **`localStorage`** under the key `mindwatch_assessment_history_v1`.
- Up to **12** recent snapshots are kept (oldest entries are dropped when the limit is exceeded).
- A **“Before · After”** block on the results page compares the **previous** run in this browser with the **current** run (overall risk, depression level, anxiety level, and assessment category).

### Why it helps (presentation angle)

- **No account needed** to see progress across retakes on the same device/browser.
- Supports talking points such as *“track how you feel over time”* or *“compare this week to last time”* in a **demo-friendly** way.

### Technical notes

- Duplicate saves on accidental refresh are reduced by setting **`sessionStorage.mw_result_pending`** only when the checklist form is submitted successfully (valid submission).
- Users can **clear** only this browser history via **“Clear session history”** on the results page.

**Primary UI:** `templates/result.html` (comparison block + client script).

---

## 3. Optional Sign-In & Account Creation

### What we built

| Route | Purpose |
|--------|---------|
| **`/register`** | Create a local account (username + password). |
| **`/signin`** | Sign in; supports optional **`?next=`** redirect (e.g. after trying to open **Past reports** while logged out). |
| **`/signout`** | End the session and return to the home/landing flow. |

### User rules

- **Username:** 3–32 characters, letters, numbers, and underscores only (`a-z`, `A-Z`, `0-9`, `_`).
- **Password:** minimum **6** characters.
- Passwords are stored using **Werkzeug** password hashing (`generate_password_hash` / `check_password_hash`), not plain text.

### Data storage

- User accounts and **saved report payloads** are stored in **`data/users.json`** (file path is **gitignored** to avoid committing personal data in class projects).

**Backend:** `app.py` (e.g. `register`, `signin`, `signout`, `_load_user_store`, `_save_user_store`, `_append_user_report`).

---

## 4. Server-Side “Past Reports” (Signed-In Users)

### What we built

- When a user completes an assessment **while signed in**, the same structured result that is kept in the session is **appended** to that user’s record in `users.json` (with a **unique id** and **UTC timestamp**).
- **`/reports`** – list view: date/time, category, depression/anxiety labels, overall risk, link to open each report.
- **`/reports/<report_id>`** – opens the **full results view** (same layout as a live result), with a short **banner** indicating this is a **saved** report and a link back to the list.
- Opening a saved report **sets the session** so **Download PDF** still works for that snapshot.

### Why it helps (presentation angle)

- Clear separation: **browser history** = quick, device-local; **signed-in history** = **named user** and **persistent** on the server for the demo.
- Easy demo script: *register → complete assessment → open Past reports → show PDF download.*

**Templates:** `templates/reports.html`, reuse of `templates/result.html` for detail.

---

## 5. Navigation Bar (Navbar)

### What we built

- A shared **`templates/partials/nav.html`** partial used across:
  - Landing (`index.html`), choice screen, text input, checklist, results, sign-in, register, and reports.
- **Not logged in:** links to **Sign in** and **Create account**.
- **Logged in:** **Past reports**, **username** (truncated if long), **Sign out**.

### Why it helps (presentation angle)

- One place to show **branding + auth** without cluttering every page’s markup.
- **Profile** is visible in the bar when signed in, matching common app patterns.

---

## 6. Results Page UX Improvements

### What we built

- **Retake assessment** → **`/choice`** (new route so users can return to the “how to continue” screen without re-posting the landing form).
- **Home** link back to the main landing entry.
- Short note explaining that **local** history is in the browser and that **sign-in** also saves reports on the server.
- **Saved report** view: banner with **timestamp** and link back to **Past reports** (when opened from `/reports/<id>`).

**Route:** `GET /choice` in `app.py` → `choice.html`.

---

## 7. Backend & Data Model Adjustments

### Assessment snapshot

- The session **`latest_result`** object now includes everything needed for both **PDF generation** and **replay**:
  - Scores, levels, risk, responses, support lists, and **`message_html`** (interpretation HTML).

### Files touched (high level)

| Area | Files |
|------|--------|
| Server logic & routes | `app.py` |
| Shared nav | `templates/partials/nav.html` |
| Auth UI | `templates/signin.html`, `templates/register.html` |
| Reports list | `templates/reports.html` |
| Results + local history | `templates/result.html` |
| Navbar integration | `templates/index.html`, `choice.html`, `text.html`, `checklist.html` |
| Privacy / data | `.gitignore` (e.g. `data/users.json`) |

---

## 8. Suggested Presentation Flow (2–3 minutes)

1. **Guest path:** Run an assessment → show **Before · After** after a second run (same browser).
2. **Account path:** **Create account** → run assessment → **Past reports** → open one → **Download PDF**.
3. **Optional:** Mention **localStorage** vs **server** storage and **privacy** (demo data in `data/users.json`, not for production).

---

## 9. Limitations (for Q&A)

- **Not production-grade security** (e.g. single JSON file, no HTTPS, no email verification, no rate limiting).
- **localStorage** is per-device/per-browser; clearing site data removes history.
- **Static assets** (e.g. `static/logo.png`) must exist for the navbar logo to display; paths are consistent with existing PDF/report code.

---

*Document generated to reflect the current feature set for MindWatch. Update this file when you add new milestones.*
