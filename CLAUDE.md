# CLAUDE.md — Session Handoff (2026-07-09, moving to a higher-RAM laptop)

> **This file is a debugging-session handoff, not project documentation.** It exists so a fresh
> Claude Code session on the new machine has full context instantly. **Delete this file before
> the repo is submitted/graded** — it's not meant to be part of the deliverable. For actual
> project docs (architecture, setup, module ownership), see [README.md](README.md), which is
> accurate and up to date.

## TL;DR — what you're picking up

AGENT P (solar analytics agent, STAI100 capstone) is fully built and has run correctly
end-to-end many times tonight. The **remaining open problem** is reliability: the LLM step
doesn't always follow the expected format, so `/chat` sometimes times out or asks an
unnecessary clarifying question instead of answering. We were mid-experiment switching from
`llama3.2:3b` (small, fast, fits in RAM, ~40-60% success rate) to `qwen2.5:7b` (bigger, was
believed more reliable, but **failed 0/7 times** on the old laptop due to insufficient free
RAM) when the user moved to this machine specifically to give qwen more headroom to work with.
**Your first job: retest qwen2.5:7b here now that more RAM is available.**

Presentation is imminent — prioritize getting a reliably-working demo over further
investigation. If qwen still doesn't work reliably here, fall back to `llama3.2:3b`, which is
proven to work (imperfectly) and is the safer choice under time pressure.

---

## Critical bug already found and fixed — do not rediscover this

**If `/chat` hangs for 90+ seconds with zero response, check MLflow is running first**, before
suspecting the LLM, NREL, or networking. Every traced function calls `_ensure_mlflow_configured()`
(`utils/telemetry.py`) before doing anything else. If nothing is listening on `localhost:5000`,
MLflow's own HTTP client retries with backoff before failing — this alone caused **hours** of
false debugging tonight (chased DNS, VPN, Windows firewall, proxy settings — all red herrings).
**Always start MLflow before the API**, every time, on any machine:
```powershell
mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri sqlite:///.mlflow/mlflow.db
```

## Code changes made tonight (already committed to working tree, not yet git-committed)

Check `git status` / `git diff` for the exact diffs. Summary:

1. **`src/database.py`** — the two NREL `requests.get()` calls were replaced with a
   `_curl_get()` helper that shells out to `curl.exe` instead. This was a workaround for a
   **machine-specific** issue on the old laptop where Python's own `requests`/socket stack hung
   indefinitely on outbound HTTPS to NREL, while `curl.exe` connected in <1s every time. Root
   cause was never fully isolated (DNS, hosts-file override, raw socket connects, and
   `NO_PROXY` were all tried and ruled out individually). **This workaround is likely
   unnecessary on this new machine** — if you want to simplify back to plain `requests`, test
   first that raw `requests.get()` to NREL doesn't hang here before reverting. Not urgent either
   way; the curl-based version works fine as-is.
2. **`src/agent.py`** — `_call_llm()` now passes `temperature=0.1` (previously unset, defaulting
   to Ollama's ~0.7-0.8). Rationale: this whole pipeline is structured extraction / faithful
   number-reporting, not creative writing, so low temperature should help consistency. **Effect
   was inconclusive on the old laptop** (small sample size, and a slow/constrained machine makes
   it hard to separate "temperature effect" from "resource contention effect"). Worth
   re-evaluating on a faster machine with a larger sample (10+ trials) — try both `0.1` and
   reverting to default/unset if reliability still looks off.
3. **`README.md`** — updated with real, verified run instructions (see that file for the
   authoritative setup/run steps — it's accurate, use it).

## The qwen vs. llama RAM finding (why you're on this laptop now)

Measured, not guessed, on the old laptop (15.6GB total RAM):
- `qwen2.5:7b` needs ~4.7GB just for weights (`ollama list` confirms `4683087332` bytes).
- Old laptop had **1.1GB free** at baseline (Windows + IDE/browser + MLflow + API + Streamlit
  all running). Killing 10 orphaned leftover python processes from earlier restarts recovered
  free RAM to 4.3GB — but the moment qwen loaded, free RAM dropped back to 1.6-2.5GB. Qwen's own
  footprint ate the recovered headroom.
- Result: **qwen2.5:7b timed out 7/7 attempts** on the old laptop — 5 trials at 120s timeout,
  1 at 240s timeout, 1 more at 180s after a memory cleanup. Every single one confirmed *actively
  computing* (Ollama's process CPU was climbing each time, checked via
  `Get-Process *ollama* | Select-Object CPU`), not stuck/hung — just too slow to finish before
  any reasonable timeout on that hardware.
- Meanwhile `llama3.2:3b` (2GB) completed successfully multiple times on the same old laptop in
  well under 90s each.
- **Hypothesis to test now**: with meaningfully more free RAM on this new machine, qwen should
  no longer be memory-starved and should complete in reasonable time. If it does, it may also
  turn out to be more *reliable* per-attempt (fewer clarification loops, better format
  adherence) since 7B models generally follow strict instructions better than 3B ones — but this
  was never actually confirmed, since qwen never once completed on the old hardware to measure.

## Known llama3.2:3b reliability baseline (for comparison)

Across two rounds of 4-5 trials each, same exact query, llama3.2:3b completed successfully
roughly **40-60% of the time**. Failure modes observed:
- Occasionally asks an unnecessary clarifying question (`needs_clarification: true`) despite the
  query matching the few-shot example almost exactly.
- Occasionally extracts wrong/nonsense coordinates.
- Even on structural success, the **prose answer text sometimes doesn't numerically match the
  real `monthly_metrics` field** — the structured data is always correct (deterministic Python
  math on real NREL data), but the LLM's natural-language summary of it can drift or fabricate
  slightly different numbers. Point to the structured sidebar table as authoritative if this
  happens live.

This reliability profile (and the qwen RAM story) are legitimate, real findings worth citing
directly in the technical write-up's Experiments/Reliability section — don't just fix and hide
them, they're evidence of real evaluation work.

## Exact setup on the new machine

Follow [README.md](README.md) "Running the project" section exactly — it's accurate and
verified. Quick version:

```powershell
git clone https://github.com/nakaraan/stai100-midtermcapstone-draft.git
cd stai100-midtermcapstone-draft
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass   # only if activation is blocked
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install mlflow
Copy-Item .env.example .env
notepad .env   # fill in NREL_API_KEY, NREL_API_EMAIL — same values as before
ollama pull llama3.2:3b
ollama pull qwen2.5:7b
```

**Four terminals, in this order** (MLflow before API is non-negotiable, see bug above):
```powershell
# 1
mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri sqlite:///.mlflow/mlflow.db
# 2 (skip if Ollama's already running as a background service — check with:
#    curl.exe -s http://localhost:11434/api/tags)
ollama serve
# 3
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
# 4
python -m streamlit run app/ui.py
```

Verify with the standard test query (matches the few-shot example in `config/prompts.yaml`,
year must be 2016-2020 — the only range the configured NSRDB endpoint covers):
```powershell
curl.exe -s --max-time 90 -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d "{\"query\": \"Give me the monthly average irradiation from Feb to June in 2019 at our warehouse location in Caloocan.\", \"session_id\": \"new-machine-test\"}"
```

To switch models: edit `.env`'s `LLM_MODEL` line, then **kill and restart the uvicorn process**
(settings are cached per-process — editing `.env` alone does nothing until restart):
```powershell
# find PID: netstat -ano | findstr ":8000" | findstr LISTENING
taskkill /F /PID <pid>
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

## Other gotchas hit tonight (unlikely to recur, but fast to check if something looks familiar)

- PowerShell's `curl` is an alias for `Invoke-WebRequest`, not real curl — use `curl.exe`
  explicitly for anything POST/header-related.
- `.venv\Scripts\Activate.ps1` can be blocked by execution policy —
  `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` fixes it for that window only.
- Every new terminal window needs the venv reactivated — it's per-session, not global.
- If deploying via a Cloudflare quick tunnel again: free tier has a hard ~100s timeout (524
  errors on slow requests) that can't be extended without an Enterprise account. The
  `Failed to initialize DNS local resolver` line in `cloudflared` logs is harmless noise, not a
  real error — confirmed by successful requests happening right alongside it.
- The Proxmox LXC deployment (separate from this laptop) is stable for MLflow+API+UI but
  **cannot run any local LLM** — crashed twice under memory pressure (once with qwen, once even
  with llama3.2:3b). If that deployment is still relevant for submission, the LLM there needs to
  point at a remote endpoint (the GPU server from the "first Docker assignment" — get details
  from Adrian Cayaco if not already obtained) via `LLM_BASE_URL` in that machine's `.env`, not
  run locally on the LXC.

## Immediate next step

1. Confirm services healthy (`curl.exe` the three `/health` endpoints).
2. Set `.env` to `LLM_MODEL=qwen2.5:7b`, restart uvicorn.
3. Run the verify query above, 5 times, same as the old-laptop trials — get a real completion
   rate, not one lucky/unlucky run.
4. If qwen's completion rate is clearly better than llama's ~40-60% baseline, keep it as final.
   If it's still poor or still timing out, revert to `llama3.2:3b` (proven) and stop
   experimenting — presentation time matters more than a marginal model upgrade at this point.
