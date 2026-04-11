# D01: Agent-Reloop framework architecture

> **Status**: Confirmed  
> **Date**: 2026-04-11  
> **Links**: [Back to Outline](../outline.md) | [Detailed notes](../notes/architecture-diagram-reading.md)

---

## Background

### Problem

We need a general self-iterating framework so an agent can execute tasks, evaluate outputs, and iterate fixes until acceptance. The framework does not implement domain features; it provides an “execute–evaluate–iterate” skeleton any task can plug into.

### Constraints

- Must support multiple agents (Claude Code / Codex / Gemini / …)
- Initialization needs human interaction; iteration must be fully automated
- Evaluation criteria are user-defined; the framework only supplies layering
- A git commit is required after each execution completes

## Goals

Build **Agent-Reloop** with:

1. Meta Skills that guide users to define intent and evaluation criteria
2. A Python loop that orchestrates execute–evaluate–check
3. Drivers that adapt different agent CLIs

---

## ✅ Decisions

### 1. Naming and positioning


| Name | Responsibility |
| ---- | -------------- |
| **Reloop (main framework)** | Orchestrates initialization + iteration; core is a Python loop |
| **Driver** | Unified interface to different agent CLIs |
| **Meta Skill** | Three built-in generators used in initialization |


### 2. Two phases

#### Initialization (agent-driven, human in the loop)

Three built-in Meta Skills:


| Meta Skill | Role | Output | Positioning |
| ---------- | ---- | ------ | ----------- |
| INTENT builder | Conversational clarity on direction | `INTENT.md` | Lightweight, finish fast |
| Evaluator builder | Interactive criteria definition | Skill file + scripts | Main time investment |
| Mocker | Read evaluator definition, infer outputs, simulate | Mock executor artifacts | Validate the evaluator |


Principles:

- INTENT = what is the goal?
- Evaluator = how do we know we met it?
- Mock = what does “met” look like?

Rules:

- Suggested order INTENT → evaluator → Mock, but **not a rigid pipeline**; re-enter anytime
- INTENT stays lightweight: task description + rough expectation; no acceptance criteria
- Only one evaluator; refine instead of adding new ones
- “Locking in” is user behavior, not a system requirement

#### Iteration (Python-driven, fully automated)

Four-step loop:

```python
while True:
    # (1) Initialize workspace
    init_workspace(run_id)

    # (2) Executor: INTENT + round N-1 eval + exec spec -> Driver -> Agent
    prompt = build_executor_prompt(intent, last_eval_result, exec_spec)
    driver.run(prompt=prompt, workdir=workdir)

    # (3) Evaluator: artifacts + eval Skill -> Driver -> Agent (may differ)
    prompt = build_evaluator_prompt(artifacts, eval_skill)
    driver.run(prompt=prompt, workdir=workdir)

    # (4) Checker: eval report -> Driver -> Agent
    prompt = build_checker_prompt(eval_report)
    result = driver.run(prompt=prompt, workdir=workdir)

    if result == "passed":
        break
```

Roles:

- **Executor**: fixed framework scaffold (execution spec), not produced by Meta Skills
- **Evaluator**: loads evaluator Skill from Meta Skill (L0/L1/L2 layers)
- **Checker**: generic, minimal, task-agnostic; only whether the report indicates pass
- First round: round N-1 evaluation is empty

### 3. Framework default three layers


| Layer | Meaning | Detection |
| ----- | ------- | --------- |
| L0 | Preconditions / safety | Scripts |
| L1 | Mechanical (deterministic) | Scripts |
| L2 | Qualitative / semantic | LLM |


Short-circuit: L0 → L1 → L2; stop if a layer fails.

### 4. Directory layout

```
project-root/
├── task/                        <- task area
│   ├── INTENT.md                <- intent
│   └── solution/                <- one evolving solution
│       └── (shape not fixed: scripts / Skills / full project / ...)
│
└── run-sets/                    <- run assets
    ├── run-001/
    │   ├── execution logs
    │   ├── execution artifacts  <- final outputs, not intermediates
    │   └── evaluation reports
    ├── run-002/
    └── ...
```

Concepts:

- **Solution**: how the task is solved; shape not fixed
- **Execution artifacts**: actual outputs from running the solution

### 5. Project layers

```
Meta Skills -> generate -> Skills
Agent Roles -> invoke -> Skills -> produce -> Artifacts
                                ^ run on
                             Drivers
```


| Layer | Role | Predefined / dynamic |
| ----- | ---- | -------------------- |
| **Meta Skills** | Produce the Skills layer | Built in |
| **Agent Roles** | Role prompts invoking Skills | Framework predefined |
| **Skills** | Executable capabilities | Evaluator dynamic; executor predefined |
| **Artifacts** | Outputs after Skills run | Runtime |
| **Drivers** | Agent CLI adapters | Framework predefined |


**Key point**: Meta Skills only produce Skills, not Agent Roles.

### 6. Driver design

- Language: **Python**
- Interface: `driver run --prompt "xxx" --workdir "xxx"`
- Skill inlined in prompt, not a separate argument
- Streamed output: live terminal + log file
- Synchronous; async out of scope for now
- One Driver per agent (Claude Code / Codex / Gemini / …)

---

## Rejected

| Option | Reason | Revisit when |
| ------ | ------ | ------------ |
| Progressive execution (2->4->8…) | Adds complexity; ship basic loop first | Single-run cost too high |
| `--skill` as separate Driver flag | Prompt inlining is simpler | Prompt assembly becomes unwieldy |

---

## References

- Hand-drawn diagrams: [assets/](../assets/) (five images)
- Discussion notes: [notes/architecture-diagram-reading.md](../notes/architecture-diagram-reading.md)
