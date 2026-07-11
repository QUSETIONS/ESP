# ESP Monorepo Publishing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Safely publish the existing ESP32 firmware, meeting backend, browser administration UI, companion clients, and tests as one GitHub repository at `QUSETIONS/ESP`.

**Architecture:** Keep the existing `zectrix` repository root and Git history. Document the existing component boundaries, exclude local/runtime artifacts, audit all pending content, commit the working tree without rewriting history, then attach and push to the GitHub remote only after confirming remote compatibility.

**Tech Stack:** Git, GitHub, ESP-IDF C/C++, Python 3 standard-library HTTP server, pytest, WeChat Mini Program JavaScript.

## Global Constraints

- Do not include files from the outer `/home/tim/桌面/moshui` workspace.
- Preserve existing Git history and do not force-push.
- Do not commit secrets, `.env`, runtime state, caches, or generated logs.
- Stop instead of overwriting an incompatible non-empty remote.

---

### Task 1: Repository hygiene and project documentation

**Files:**
- Modify: `.gitignore`
- Create: `README.md`
- Verify: `.env.example`, `tools/meeting_server/README.md`

**Interfaces:**
- Consumes: existing firmware and tool directory layout.
- Produces: a documented monorepo entry point and ignore rules for local-only files.

- [ ] **Step 1: Audit tracked and untracked paths for credentials and runtime artifacts**

Run targeted filename and content scans for environment files, keys, tokens, passwords, Wi-Fi credentials, private keys, backend state, caches, logs, and build outputs. Inspect every match before staging.

- [ ] **Step 2: Extend ignore rules only where the audit finds uncovered local artifacts**

Keep `.env.example` trackable; ignore `.env`, `tools/meeting_server/state/`, recording/runtime outputs, caches, and logs.

- [ ] **Step 3: Create the root README**

Document `main/`, `tools/meeting_server/`, `tools/wechat_miniprogram/`, `tools/ble_meeting_sync/`, build prerequisites, backend start command, editor URL, and test command.

- [ ] **Step 4: Validate documentation and ignore behavior**

Run `git diff --check`, `git status --short --ignored`, and verify ignored sensitive/runtime examples with `git check-ignore -v`.

### Task 2: Validate and commit the monorepo contents

**Files:**
- Modify: all currently pending product files after audit.
- Test: `tools/tests/`

**Interfaces:**
- Consumes: the audited working tree from Task 1.
- Produces: tested local commits containing the complete product state.

- [ ] **Step 1: Run Python contract and backend tests**

Run `python3 -m pytest tools/tests/ -q`. Record the exact pass/fail summary and investigate failures before publishing.

- [ ] **Step 2: Review the complete staged change set**

Use `git diff --check`, `git status --short`, `git diff --stat`, and `git diff --cached` after staging. Confirm the outer workspace is absent and no generated/runtime files are staged.

- [ ] **Step 3: Commit repository documentation separately**

Commit `README.md`, `.gitignore`, and this implementation plan with a documentation-focused message.

- [ ] **Step 4: Commit the existing product work**

Stage only audited product source, tests, fixtures, and intentional preview assets. Commit with a message describing the meeting synchronization and administration capabilities present in the working tree.

- [ ] **Step 5: Verify local repository state**

Run `git status --short --branch` and `git log --oneline -5`; the working tree must be clean unless a consciously excluded local artifact remains ignored.

### Task 3: Attach and publish the GitHub remote

**Files:**
- Modify: `.git/config` through Git commands.

**Interfaces:**
- Consumes: clean, tested local `master` history.
- Produces: `origin` set to `https://github.com/QUSETIONS/ESP` and the local branch published upstream.

- [ ] **Step 1: Inspect GitHub authentication and remote state**

Check `gh auth status` when available, then query remote refs with `git ls-remote https://github.com/QUSETIONS/ESP`. An empty result is safe; an unrelated history requires stopping for reconciliation.

- [ ] **Step 2: Configure origin without overwriting another remote**

If no `origin` exists, run `git remote add origin https://github.com/QUSETIONS/ESP.git`; otherwise verify or update only the intended `origin` URL.

- [ ] **Step 3: Fetch and verify history compatibility**

Run `git fetch origin`. If `origin/master` or `origin/main` exists, verify it is an ancestor or otherwise compatible before pushing. Never use `--force`.

- [ ] **Step 4: Push and set upstream**

Run `git push -u origin master`. If authentication blocks the push, preserve the local commits and report the exact authentication action required.

- [ ] **Step 5: Verify publication**

Run `git remote -v`, `git status --short --branch`, and `git ls-remote --heads origin`; confirm the pushed commit hash matches local `HEAD`.
