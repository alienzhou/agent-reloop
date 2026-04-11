# Architecture discussion notes (living doc)

> **Status**: In discussion  
> **Date**: 2026-04-11  

---

## Hand-drawn diagram index


| ID | File | Contents |
| -- | ---- | -------- |
| 01 | [Overview](../assets/final-overview-architecture.jpg) | Full picture: Init Phase, Iteration Phase, Project Layers |
| 02 | [Init phase](../assets/final-init-phase.jpg) | INTENT setup + evaluator generation + Mock validation |
| 03 | [Iteration phase](../assets/final-iteration-phase.jpg) | Init workspace -> executor -> evaluator -> checker |
| 04 | [Directory layout](../assets/final-directory-structure.jpg) | `task/` + `run-sets/` |
| 05 | [Project layers](../assets/final-project-layers.jpg) | Meta Skills -> Agent Roles -> Skills -> Artifacts -> Drivers |


---

## 1. Naming and positioning


| Name | Responsibility |
| ---- | -------------- |
| **Reloop (main framework)** | Orchestrates initialization + iteration |
| **Driver** | Unified interface to agent CLIs (Claude Code / Codex / Gemini / …) |
| **Meta Skill** | Three built-in generators for initialization |


---

## 2. Initialization phase

### Three Meta Skills (built in)


| Meta Skill | Role | Output | Positioning |
| ---------- | ---- | ------ | ----------- |
| Build INTENT | Conversational clarity | `INTENT.md` | Lightweight, fast |
| Build evaluator | Interactive criteria | Skill + scripts | Main focus |
| Build Mock (Mocker) | Infer outputs from definition | Mock executor artifacts | Validate evaluator |


### INTENT design

- Lightweight: task description + rough expected output only
- No acceptance criteria (evaluator’s job)
- Consumer: executor

### Evaluator design

- Evaluator = Agent (host) + Skill (Meta Skill output)
- Scripts for procedural checks + LLM for qualitative judgment
- Single evaluator; refine instead of creating new ones

### Framework default three layers


| Layer | Meaning | Detection |
| ----- | ------- | --------- |
| L0 | Preconditions / safety | Scripts |
| L1 | Mechanical (deterministic) | Scripts |
| L2 | Qualitative / semantic | LLM |


Short-circuit: L0 -> L1 -> L2; stop on failure

### Invocation rules

- Suggested: INTENT -> evaluator -> Mock; not a rigid pipeline
- Meta Skills can be re-entered anytime
- “Locking in” is user behavior, not enforced by the system

### Core principles

- INTENT = what is the goal?
- Evaluator = how do we know we met it?
- Mock = what does “met” look like?

---

## 3. Iteration phase

### Four steps


| Step | Role | Input | Output |
| ---- | ---- | ----- | ------ |
| (1) Init workspace | Reloop framework | — | Workspace ready |
| (2) Executor | Agent via Driver | INTENT + round N-1 eval + exec spec | Artifacts + logs |
| (3) Evaluator | Agent via Driver (may differ) | Artifacts + eval Skill | Evaluation report |
| (4) Checker | Agent via Driver | Evaluation report | Pass / fail |


### Executor design

- Fixed **scaffold** (generic execution pattern), not from Meta Skills
- Execution spec covers log paths, artifact dirs, solution dir
- Runtime: INTENT + round N-1 eval + exec spec -> prompt -> Driver -> Agent
- First round: round N-1 eval is empty

### Checker design

- Generic, minimal, task-agnostic
- Only reads whether the report wording indicates pass
- Why: report formats may vary

### Key constraints

- Commit after each execution (hard requirement)
- Progressive execution not in scope
- Drivers decouple executor and evaluator (may use different agents)

---

## 4. Directory layout

```
project-root/
├── task/                     <- task area
│   ├── intent (INTENT)
│   └── solution/             <- one evolving workspace
│       └── (shape not fixed: scripts / Skills / full project / ...)
│
└── run-sets/                 <- assets per iteration
    ├── run-001/
    │   ├── execution logs
    │   ├── execution artifacts   <- actual outputs from running solution (final, not intermediate)
    │   └── evaluation reports
    ├── run-002/
    └── ...
```

### Concept distinctions


| Concept | Meaning | Location | Examples |
| ------- | ------- | -------- | -------- |
| Solution | How the task is solved | `task/` | Scripts, Skills, dev project |
| Execution artifacts | Outputs from running the solution | `run-sets/run-xxx/` | Reports, processed data |
| Execution logs | Run trace | `run-sets/run-xxx/` | Run logs |
| Evaluation report | Evaluator verdict | `run-sets/run-xxx/` | L0/L1/L2 results |


---

## 5. Project layers

```
Initialization
       |
       v Meta Skills (generators)
       | generates
       v
    Skills (executable capabilities)
       ^                  |
       | invoked by       | produces
       |                  v
  Agent Roles  --------> Artifacts
       ^
       | runs on
    Drivers (agent adapters)
```


| Layer | Role | Contains | Predefined / dynamic |
| ----- | ---- | -------- | -------------------- |
| **Meta Skills** | Produce Skills layer | Evaluator builder, INTENT builder, Mocker | Built in |
| **Agent Roles** | Framework roles (prompts) invoking Skills | Evaluator, executor, checker | Framework predefined |
| **Skills** | Capabilities invoked by Agent Roles | Evaluator Skill, executor Skill | Evaluator dynamic; executor predefined |
| **Artifacts** | Outputs after Skills | Evaluation results, deliverables | Runtime |
| **Drivers** | Agent CLI adapters | Claude Code / Codex / Gemini / … | Framework predefined |


**Key**: Meta Skills only generate Skills, not Agent Roles.

---

## 6. Driver design

### Basics

- Language: Python
- Synchronous; async out of scope
- Streamed output: terminal + file

### Unified interface

```
driver run --prompt "xxx" --workdir "xxx"
```

- `--prompt`: string (Skill inlined, not separate)
- `--workdir`: agent working directory
- Other flags (`--output` / `--timeout`) TBD

### Driver list

- Claude Code
- Codex
- Gemini
- … (extensible)

---

## 7. How the two phases are driven


| Phase | Driver | Why |
| ----- | ------ | --- |
| **Initialization** | Agent (human in the loop) | Dialogue to produce INTENT / evaluator / Mock |
| **Iteration** | Python loop | Fully automated; code control is reliable |


The Python loop is the core of Reloop—it is code, not an agent. Agents only run when invoked via Driver.

---

## 8. Open topics

(None)
