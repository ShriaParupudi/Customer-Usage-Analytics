# Runbook — how to actually run this thing

Written for someone who has never confidently run a script from a terminal.
Nothing here is assumed. If a step doesn't match what you see, stop and say so.

---

## Part 0: The one mental model you need

Your computer has a **terminal** — a window where you type commands instead of
clicking. A command is just a sentence with three parts:

```
python    -m src.generate_data
^^^^^^    ^^^^^^^^^^^^^^^^^^^^
the tool  what you want it to do
```

Two rules that prevent 90% of beginner pain:

1. **You must be standing in the right folder.** The terminal always has a
   "current folder", like a File Explorer window you can't see. If you type a
   command in the wrong folder, you get `No such file or directory`. That error
   almost never means the file is missing — it means *you are in the wrong
   place*. Type `pwd` (Mac/Linux) or `cd` (Windows) to see where you are.
2. **A command that prints nothing usually worked.** Terminals are quiet on
   success and loud on failure. Silence is good news.

---

## Part 1: One-time setup (do this once, ever)

### Step 1.1 — Open a terminal

- **Mac:** press `Cmd + Space`, type `Terminal`, press Enter.
- **Windows:** press the Start key, type `PowerShell`, press Enter.

A window opens with a blinking cursor. That's it. That's the scary thing.

### Step 1.2 — Check Python is installed

Type this exactly, then press Enter:

```bash
python3 --version
```

**What you should see:** something like `Python 3.11.5`. Any version starting
with `3.10`, `3.11`, `3.12` or `3.13` is fine.

**If you see `command not found`:** try `python --version` instead. If that also
fails, install Python from https://www.python.org/downloads — download, run the
installer, and on Windows **tick the box that says "Add Python to PATH"** during
install. That box is the single most common cause of "it doesn't work".

> From here on, wherever I write `python3`, use whichever of `python3` or
> `python` worked for you.

### Step 1.3 — Get to the project folder

Unzip the project zip somewhere you can find it — Desktop is fine. Then:

```bash
cd ~/Desktop/customer-usage-analytics
```

`cd` means "change directory". `~` means your home folder.

**Shortcut if that path is wrong:** type `cd ` (with a space after it), then
**drag the project folder from Finder/Explorer into the terminal window**. The
path types itself. Press Enter.

**Confirm you're in the right place:**

```bash
ls          # Mac/Linux
dir         # Windows
```

**What you should see:** `README.md`, `Makefile`, `config`, `docs`, `src`, `sql`…
If you see that list, you are in the right folder and the hardest part is over.

### Step 1.4 — Create a virtual environment

A virtual environment is a private box of libraries just for this project, so
installing something here can't break anything else on your computer.

```bash
python3 -m venv .venv
```

Takes a few seconds and prints nothing. Silence = success.

### Step 1.5 — Activate it

**Mac/Linux:**
```bash
source .venv/bin/activate
```

**Windows PowerShell:**
```powershell
.venv\Scripts\Activate.ps1
```

**What you should see:** your prompt now starts with `(.venv)`. That prefix means
the box is open.

> **Windows error `running scripts is disabled on this system`?** Run this once,
> answer `Y`, then retry the activate command:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```

> **You must re-run the activate command every time you open a new terminal.**
> Forgetting this is the #1 cause of `ModuleNotFoundError`. If you see that
> error, check for `(.venv)` in your prompt first.

### Step 1.6 — Install the libraries

```bash
pip install -r requirements.txt
```

Lots of scrolling text for 30–60 seconds. Ends with `Successfully installed …`.
Yellow `WARNING` lines are normal and safe to ignore. Red `ERROR` lines are not —
send me the last 15 lines if you see one.

**Setup is done.** You never repeat Part 1 (except step 1.5 in each new terminal).

---

## Part 2: Running the pipeline (the everyday part)

Every time: open terminal → `cd` to the project → activate → run.

```bash
cd ~/Desktop/customer-usage-analytics
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
```

Then run whichever step you want:

| Command | What it does | Roughly how long |
|---|---|---|
| `make data` | generates the synthetic datasets into `data/raw/` | ~30 s |
| `make ingest` | loads them into the DuckDB warehouse | ~10 s |
| `make dq` | runs data quality checks, writes `outputs/dq_report.md` | ~5 s |
| `make marts` | builds staging + the dimensional model | ~15 s |
| `make analytics` | builds metrics, segments, risk scores | ~10 s |
| `make export` | CSV exports **and** the HTML dashboard | ~5 s |
| `make all` | all of the above, in order | ~2 min |

When `make all` finishes, open
`dashboards/customer_health_dashboard.html` by double-clicking it. It is a single
self-contained file — no server, no internet, it just opens in your browser.

**If `make` isn't installed** (common on Windows), every step has a plain-Python
equivalent — same thing, no `make` needed:

```bash
python3 -m src.generate_data
python3 -m src.ingest
python3 -m src.quality_checks
python3 -m src.build_staging
python3 -m src.build_marts
python3 -m src.build_analytics
python3 -m src.export_bi
```

### Starting over when something looks wrong

```bash
make clean     # or: rm -rf data/raw/* data/warehouse/*
make all
```

The whole pipeline is **idempotent** — re-running it from scratch always produces
the identical result. You cannot break it by running it twice. Deleting
everything in `data/` is always safe, because everything in there is generated.

---

## Part 3: Looking at the data yourself

```bash
python3 -m src.peek
```

Prints the row counts and a preview of every table. Use it whenever you want to
check something is really there.

To poke around in SQL directly:

```bash
duckdb data/warehouse/warehouse.duckdb
```

Then type SQL and end each statement with a semicolon:

```sql
SELECT count(*) FROM raw.accounts;
SHOW TABLES;
.quit
```

`.quit` exits. (If `duckdb` isn't a command on your machine, that's the optional
standalone CLI — you don't need it, the Python pipeline is self-contained.)

---

## Part 4: Errors, decoded

| What you see | What it actually means | Fix |
|---|---|---|
| `command not found: python3` | Python isn't installed, or isn't on PATH | Reinstall, tick "Add to PATH" |
| `No such file or directory` | You're in the wrong folder | `pwd`, then `cd` to the project |
| `ModuleNotFoundError: No module named 'duckdb'` | Virtual environment isn't active | Re-run step 1.5, check for `(.venv)` |
| `ModuleNotFoundError: No module named 'src'` | You're one folder too deep or too shallow | `cd` to the folder containing `README.md` |
| `make: command not found` | `make` isn't installed | Use the `python3 -m src.…` list above |
| `Permission denied` | Usually a file open in Excel | Close Excel, retry |
| `DQ CHECK FAILED` + exit code 1 | **The pipeline worked.** It found bad data and stopped on purpose | Read `outputs/dq_report.md` |

That last row matters: a data quality failure is the pipeline **succeeding at its
job**. It is not a crash.

### How to ask me for help

Copy the **last 15 lines** of terminal output and paste them. Don't summarise it,
don't retype it — the exact text is what identifies the problem.

---

## Part 5: Putting it on GitHub

Once, at the start:

```bash
git init
git add .
git commit -m "Phase 0: business problem, data design, architecture, repo scaffold"
```

Then create an empty repo on github.com (**do not** tick "add a README" — the
repo must be empty), and run the two lines GitHub shows you, which look like:

```bash
git remote add origin https://github.com/YOUR-USERNAME/customer-usage-analytics.git
git push -u origin main
```

After each phase:

```bash
git add .
git commit -m "Phase 3: data quality framework with 15 checks and severity levels"
git push
```

**Commit message rule:** describe *what changed and why*, not "update". Your
commit history is part of the portfolio — a reviewer will scroll it. Ten
messages that read like a changelog beat one commit called "final version".

`git add .` will never commit your data files, because `.gitignore` excludes
them. Check with `git status` — if you ever see a `.parquet`, `.csv.gz`, or
`.duckdb` file listed, stop and tell me.
