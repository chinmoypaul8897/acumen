# Resuming work on Acumen — the architect / builder workflow

This project is built and maintained with a two-role loop that can be **reconstructed
entirely from this repository**, on any machine and with any AI coding assistant. Nothing
about the workflow depends on a particular chat, account, or tool. If you are returning to
this project after a break, start here — then open `prompt_templates.md` for the exact
prompts.

## The idea in one paragraph

Work happens in two separate sessions. A **builder** session does the actual work — it edits
code, runs tests, and commits. A read-only **architect** session reads the whole repository,
writes the precise prompt for each unit of work, and judges the report that comes back — but
it never edits, writes, or commits. Every non-trivial change is then checked by a **fresh
review** session that shares no context with the builder. This separation is what made the
code trustworthy the first time, and it is how it stays trustworthy.

## Where the knowledge lives

All of the durable context is committed, so a fresh architect session can read these and
fully re-assume the role — there is no hidden state in any past conversation.

| File | What it holds |
|------|----------------|
| `CONTEXT.md` | The frozen strategy specification and every ruling on it. The law. |
| `CLAUDE.md` | The working rules every session follows — git, stores, secrets, review. |
| `plan.md` | The build plan and per-chunk cards. |
| `PROCESS.md` | The reusable method (the architect loop) in general form. |
| `PROGRESS.md` | The session-by-session ledger, newest on top. |
| `STATUS.md` | The one-line-per-chunk state. |
| `QUESTIONS.md` | Open questions and the architect's rulings, recorded verbatim. |
| `docs/reviews/` | Every adversarial review report. |
| `prompt_templates.md` | The copy-paste prompt scaffolds this workflow runs on. |

## The three roles

**Builder session** — a normal Claude Code session in this folder.
- Does the work: edits, tests, commits, pushes.
- The ONLY session permitted to write to the repository.

**Architect session** — a second Claude Code session in this same folder, **read-only**.
- Reads the repo and reasons about it; writes the prompt for each build unit and judges the
  report and repo state that results.
- NEVER edits, writes, or commits. Enforce this: deny it edit/write/shell-write permissions,
  or run it strictly by instruction and approve no writes in it.

**Review session** — a **fresh** Claude Code session, one per review.
- Zero shared context with the builder. Attacks the change, produces
  `docs/reviews/REVIEW_<N>.md`, and returns PASS or FAIL.
- Never the same session as the architect — reviews stay blind.

## How to resume, step by step

1. Open the repo in VS Code. It is already on your machine and on GitHub; nothing here
   depends on any past chat. Run `git pull` so you are current.
2. Start the **architect** session and paste the *Architect bootstrap prompt* from
   `prompt_templates.md`. It reads the governance files above and re-assumes the role.
3. Tell it what you want to rework. It produces a **build prompt** (scaffold in
   `prompt_templates.md`), scope-fenced, with the safety rider attached.
4. Paste that into a separate **builder** session. It does the work, commits with the
   `(unreviewed)` suffix, and writes its report (into `PROGRESS.md` and/or a report block
   you hand back to the architect).
5. For anything non-trivial, open a **fresh review** session and paste the *Review prompt*.
   On PASS, the architect records the outcome and you move on; on FAIL, it writes a fix
   prompt and the loop repeats.
6. When the architect session's context fills, `/clear` it and re-bootstrap from the same
   files. The repository is the memory.

## Non-negotiables carried from the original build

- One session writes at a time; the architect and review sessions are read-only.
- Ambiguity the specification does not resolve goes to `QUESTIONS.md` and is escalated —
  never guessed. This is a money-touching tool.
- Secrets never enter git. The market-data stores live **outside** the repository tree and
  are never read from or written to by a session without an explicit, named sanction (see
  the hard safety rider in `prompt_templates.md`).
- No AI attribution in commit messages; atomic commits; push and record the SHA every
  session.

## Resume checklist

- [ ] Repo open, `git status` clean, `git pull` current.
- [ ] Architect session bootstrapped and confirmed read-only.
- [ ] Build prompt written — scope-fenced, safety rider attached.
- [ ] Builder ran, committed `(unreviewed)`, reported back.
- [ ] Fresh review passed; `docs/reviews/` and the ledgers updated.
- [ ] Pushed; SHA recorded in `PROGRESS.md`.
