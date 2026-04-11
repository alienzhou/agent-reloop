# Agent-Reloop framework architecture discussion

## Current Focus

- Main architecture discussion is done; ready to finalize Decision docs

## Pending

(None)

## Confirmed

### Naming and positioning

- **Reloop (main framework)**: orchestrates the full flow (initialization + iteration loop)
- **Driver**: unified interface for different agent CLIs (Claude Code / Gemini / Cursor / …)
- **Framework role**: does not implement domain features; owns process, not content

### Initialization phase

- **Three built-in Meta Skills** (generators):
  - Build INTENT → `INTENT.md` (lightweight, fast)
  - Build evaluator → Skill file + companion scripts (focus area)
  - Build Mock (Mocker) → mock executor artifacts
- **INTENT**: only task description + rough expected output; no acceptance criteria; consumer is the executor
- **Evaluator = Agent + Skill**: agent is the host; Skill is evaluation logic from the Meta Skill
- **Only one evaluator**; refine it instead of creating new ones
- **Two mechanisms**: scripts (procedural) + LLM (qualitative)
- **Framework default three layers**: L0 (safety/preconditions) → L1 (mechanical) → L2 (qualitative), with short-circuiting
- **How Mocker works**: read evaluator Skill + scripts, infer expected outputs, synthesize them
- **Meta Skills are not a rigid pipeline**; re-enter anytime; "locking in" is user behavior

### Iteration phase

- **Four steps**: (1) initialize workspace → (2) executor → (3) evaluator → (4) checker
- **Executor**: INTENT + round N-1 eval + execution spec → Driver → Agent; uses a fixed framework scaffold
- **Evaluator**: load evaluator Skill from Meta Skill → Driver → Agent (may be a different agent)
- **Checker**: generic, minimal, task-agnostic; reads whether the evaluation report indicates pass → Driver → Agent
- **First round**: round N-1 evaluation is empty
- **Must commit after each execution** (hard requirement)
- Progressive execution not in scope for now

### Directory layout

- **Two areas**: `task/` (task) + `run-sets/` (run assets)
- **`task/`**: INTENT + solution (one evolving workspace; shape not fixed)
- **`run-sets/`**: `run-001`, `run-002`, … each with execution logs, artifacts, evaluation reports
- **Solution**: how the task is solved (scripts / Skills / full projects)
- **Execution artifacts**: actual outputs from running the solution (final outputs, not intermediates)

### Project layers

| Layer | Role | Contains |
| ----- | ---- | -------- |
| **Initialization** | Entry | Triggers initialization |
| **Meta Skills** | Generators (produce Skills layer) | Evaluator builder, INTENT builder, Mocker |
| **Agent Roles** (prompts) | Framework-defined roles invoking Skills | Evaluator, executor, checker |
| **Skills** | Executable capabilities invoked by Agent Roles | Evaluator Skill (Meta Skill output), executor Skill (framework predefined) |
| **Artifacts** | Outputs after Skills run | Evaluation results, target deliverables (scripts / projects / Skills / docs / …) |
| **Drivers** | Agent CLI adapters | Claude Code / Codex / Gemini / … |

- **Key relationship**: Meta Skills → generate → Skills; Agent Roles → invoke → Skills → produce → Artifacts
- **Meta Skills do not produce Agent Roles**; Agent Roles are framework predefined

### Driver design

- Implemented as **Python** scripts
- **Unified interface**: `driver run --prompt "xxx" --workdir "xxx"` (`--output` / `--timeout` TBD)
- **Skill is not a separate flag**; inlined into the prompt
- **Streamed output**: live terminal + file
- **Synchronous**; async out of scope for now

### How the two phases differ

- **Initialization**: agent-driven (human in the loop; agent runs Meta Skills to guide the user)
- **Iteration**: Python-driven loop (program controls the cycle; Driver starts agents)

## Rejected

- Progressive execution (not kept for now)
- `--skill` flag (inline into prompt instead)
