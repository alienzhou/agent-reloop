# Project agent rules

This file defines rules agents working in this repository must follow.

---

## Evaluator optimization report rule

**Rule**: Any optimization to the evaluator must end with a written summary report.

### Report format

```markdown
## Evaluator optimization report

### 1. What changed
- Brief description of this optimization

### 2. Which parts of the evaluator were affected
- [ ] Evaluation criteria
- [ ] Verification scripts
- [ ] Evaluation workflow
- [ ] Feedback format
- [ ] Other: ___

### 3. Which criteria changed
| Level | Check | Change type | Notes |
|-------|-------|-------------|-------|
| L1 / L1.5 / L2 | Check name | add / modify / remove | Details |

### 4. Impact
- Which rounds need re-evaluation
- New criteria the executor must respect
```

### Example

```markdown
## Evaluator optimization report

### 1. What changed
Added L1.5 batched output validation so files are split into reasonable batches.

### 2. Which parts of the evaluator were affected
- [x] Evaluation criteria
- [x] Verification scripts
- [ ] Evaluation workflow
- [ ] Feedback format

### 3. Which criteria changed
| Level | Check | Change type | Notes |
|-------|-------|-------------|-------|
| L1.5 | Max entries per file | add | <= 50 threads |
| L1.5 | Max file size | add | <= 200KB |
| L1.5 | Max entry length | add | <= 8000 characters |
| L1.5 | Sequential file numbering | add | No gaps |

### 4. Impact
- Round 05 must be re-evaluated (previously passed but fails new criteria)
- Executor must implement batched writes
```

---

## Other rules

(To be extended)

<!-- [ABC:agent-better-checkpoint:start] -->
## Checkpoint Commit Rule

After completing any file edit (write_to_file, replace_in_file, multi_replace_in_file, or similar),
you MUST:

1. Load the "agent-better-checkpoint" skill (if not already loaded)
2. Follow its instructions to create a checkpoint commit
3. Do NOT proceed to the next task until the commit is done

This ensures every meaningful code change is tracked with a semantic Git commit.
<!-- [ABC:agent-better-checkpoint:end] -->
