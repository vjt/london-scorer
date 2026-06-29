# Resuming london-scorer

This repository is **self-contained**. Everything needed to build the tool is in here —
do not read parent directories.

## What to do

1. Read `docs/design.md` (the spec) and `docs/plans/2026-06-29-london-scorer-v1.md`
   (the 12-task TDD plan).
2. Execute the plan **task-by-task** using the `superpowers:subagent-driven-development`
   skill — one fresh subagent per task: write failing test → run (fails) → implement →
   run (passes) → commit. Review between tasks. Start at **Task 1**, finish at **Task 12**.
3. **Milestone M1 = Tasks 1–6** (config, cached HTTP, geo, stations, commute, discovery)
   → a runnable district-discovery that outputs a ranked list of postcode districts north
   of King's Cross with **real AM/PM commute** times. Tasks 7–12 add schools, housing (EPC),
   crime, demographics, broadband, scoring, and Markdown/CSV output.

## Status

Spec + plan committed. **No implementation code yet** — `src/london_scorer/` has only
`__init__.py`.

## Secrets

`.env` (gitignored) holds `TFL_APP_KEY` (+ a fallback) and `EPC_BEARER_TOKEN`
(gov.uk "Find Energy Certificate" bearer auth). **Never commit `.env`.**

## Setup to run the tool (the tests are offline and need none of this)

- `python -m pip install -r requirements.txt`
- Download bulk CSVs into `data/` (gitignored): DfE GIAS schools, Ofsted ratings,
  Ofcom Connected Nations broadband. Census is a live Nomis API; crime/geo are live too.

## Gotchas

- EPC bearer auth may return 401 → revisit header/endpoint in Task 9 (isolated from the rest).
- GIAS/Ofsted CSV headers vary between exports → verify and adjust the rename map (Task 8).
- Confirm the Ofcom gigabit/FTTP column (Task 11) and the Nomis TS021/TS030 dataset ids (Task 10).

## Scope reminder

Open data only — **no listings/scraping**. Output ranks *areas to visit*, not individual
houses. Keep this repo free of any personal data.
