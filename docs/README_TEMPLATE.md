# README template — quantitative research repository

Reusable skeleton extracted from this repository's README. Copy it into a new
project, replace every `{PLACEHOLDER}`, delete the sections that do not apply,
and delete this header block.

**The principle behind the structure:** a recruiter or reviewer reads top-down
and stops early, so the order is *claim → evidence → caveat*. The headline
finding appears before the method, and the limitations are stated by you rather
than discovered by the reader. Never let a section promise something the code
does not do — the roadmap is where unbuilt work belongs.

**Rules that keep it honest**

1. Every number in the README is reproducible by one documented command.
2. Anything listed under *Roadmap → Open* must never appear in the repo
   description, badges, topics or TL;DR as if it existed.
3. Charts ship in light and dark variants via `<picture>`; PNG renders more
   reliably than SVG on GitHub.
4. If a finding contradicts your original hypothesis, say so explicitly — it is
   the most credible thing on the page.
5. Do not redistribute third-party papers or licensed market data; link and
   document the schema instead.

---

# {EMOJI} {PROJECT TITLE} — {ONE-LINE POSITIONING}

[![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![{LIB}](https://img.shields.io/badge/{LIB}-{VERSION}-150458?logo={LIB}&logoColor=white)]({LIB_URL})
[![Status](https://img.shields.io/badge/status-research%20artifact-8A2BE2)]()

> Badges must be verifiable: the Python version matches `pyproject.toml`, the
> library version matches the declared dependency. Avoid metric badges that go
> stale (a hard-coded Sharpe or "tests passing" without CI).

{ONE-PARAGRAPH SUMMARY: what is replicated or built, on what instrument and
sample, and the question the source work does not ask.}

> **1. {QUESTION 1}** → *{SHORT ANSWER}*
> **2. {QUESTION 2}** → *{SHORT ANSWER}*
> **3. {QUESTION 3}** → *{SHORT ANSWER}*

> [!NOTE]
> **Companion repo, different {PAPER / INSTRUMENT}.** {LINK + ONE-LINE
> DISAMBIGUATION.} *(Include only when you own a repo a visitor could mistake
> for this one — state what differs: paper, instrument, method.)*

---

## 🧭 TL;DR

| | |
|---|---|
| 🎯 **{HEADLINE 1}** | {Result with the number, and the benchmark it beats or matches} |
| 💸 **{HEADLINE 2}** | {The finding that changes the conclusion} |
| 🔀 **{HEADLINE 3}** | {The test that could have falsified it, and what it returned} |
| ⚠️ **{HEADLINE 4}** | {The weakness a reviewer would find anyway} |

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/{HERO}_dark.png">
  <img alt="{DESCRIPTIVE ALT TEXT: state the actual values a screen-reader user needs}" src="assets/{HERO}_light.png">
</picture>

*{One-sentence caption stating the thesis the chart carries.}*

---

## ⚙️ Strategy rules *(or: Method)*

{INSTRUMENT}, **{SAMPLE START} → {SAMPLE END}**, {CAPITAL / UNIVERSE}.

```mermaid
flowchart LR
    A["{SIGNAL}"] -->|{CONDITION}| B["{ENTRY}"]
    A -->|{ELSE}| X["🚫 No trade"]
    B --> C["{EXIT RULES}"]
```

**Sizing & costs** — {position sizing formula}. {Cost assumptions, stated as
assumptions.} {Any rule that turns out to be inert in practice — say so.}

---

## 📊 Results

| Scenario | {METRIC 1} | Trades | {METRIC 2} | t-stat | Sharpe | CAGR | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| 📄 {BASELINE} | | | | | | | |
| 💸 {WITH COSTS} | | | | | | | |
| 🔀 {VARIANT} | | | | | | | |
| 🧪 {PLACEBO / CONTROL} | | | | | | | |
| 🧺 {BENCHMARK} | — | — | — | — | | | |

> Include a control row wherever a variant could be explained by something
> simpler. A variant that does not beat its own placebo is not a finding.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/{METRICS}_dark.png">
  <img alt="{ALT TEXT}" src="assets/{METRICS}_light.png">
</picture>

---

## 🔬 What the data actually said

**1. {CLAIM}.** {Evidence, with the number.}

**2. {CLAIM THAT SURPRISED YOU}.** {State plainly where your prior was wrong and
what the control experiment returned.}

**3. …but {THE LIMIT OF THE CLAIM}.** {Distinguish a significant component from
a significant strategy — e.g. per-trade significance vs overlapping bootstrap
confidence intervals at portfolio level.}

**4. {ROBUSTNESS / REGIME FINDING}.** {Where the result concentrates in time or
in state — the thing a risk review would flag.}

---

## ⚠️ Limitations

- **{Selection / in-sample bias}** — {how the variant was chosen, and what
  validation is still owed}.
- **{Sample coverage}** — {end date, and what fresh data would test}.
- **{Cost or execution model}** — {what is a point estimate rather than a model}.
- **{Benchmark treatment}** — {dividends, risk-free, financing}.
- **{Source conflicts of interest, data provenance, survivorship}**.

---

## 🗺️ Roadmap

**Done** *(pointers to the code that does it)*

- [x] {ITEM} — `{path}`

**Open**

- [ ] {ITEM NOT YET BUILT}

> Everything under **Open** is forbidden from the repo description, topics and
> TL;DR until it moves to **Done**.

---

## 📂 Repository structure

```
├── 📄 README.md · LICENSE · NOTICE.md · pyproject.toml
├── 🖼️ assets/            # README charts (light + dark)
├── 🗃️ data/              # not versioned — schema in data/README.md
├── 📚 docs/              # template, standalone figures
├── 📓 notebooks/         # narrative analysis
├── 🧩 src/{package}/     # importable, tested library code
├── 🧪 tests/             # runnable without market data
└── ⚙️ scripts/           # one command per reproducible output
```

## 🚀 Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
python -m pytest                     # tests must pass without proprietary data
# place data per data/README.md, then:
python scripts/{RUNNER}.py --{ARGS}
```

*{State that the README figures come from this command, and that a fresh run may
differ by rounding.}*

---

## ⚖️ Disclaimer

Research artifact, not investment advice and not a production trading system.
Historical results — especially net of *assumed* costs — do not guarantee future
performance. Reconcile all data against a proprietary feed before committing
capital.
