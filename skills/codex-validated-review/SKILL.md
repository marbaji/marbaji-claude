---
name: codex-validated-review
description: Run a Codex code review (standard or adversarial) with mandatory validation of findings against actual source code and project docs before presenting results. Use when you want Codex to review your work but need false positives filtered out.
user-invocable: true
argument-hint: '[adversarial] [--wait|--background] [--base <ref>] [focus ...]'
---

# Codex Validated Review

Run a Codex review with a validation gate that filters findings before presenting them.

## Why This Exists

Codex operates with limited project context. It will flag intentional design choices as bugs, misunderstand domain-specific patterns, and sometimes hallucinate issues that don't exist. This skill wraps `/codex:review` or `/codex:adversarial-review` with a mandatory validation step borrowed from the auditcodex discipline.

## Arguments

- `adversarial` (first word): Use adversarial review mode instead of standard review
- All other arguments are passed through to the underlying codex command (`--wait`, `--background`, `--base <ref>`, focus text for adversarial)

## Execution Flow

### Step 1: Determine Review Type

Check if the first argument is `adversarial`:
- If yes: strip it from args, use `/codex:adversarial-review` with remaining args
- If no: use `/codex:review` with all args

### Step 2: Run the Codex Review

Execute the appropriate codex companion script in **foreground** (always `--wait`, regardless of user args — validation requires the output):

```bash
# Standard review:
node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" review --wait $REMAINING_ARGS

# Adversarial review:
node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" adversarial-review --wait $REMAINING_ARGS
```

**Important:** `CLAUDE_PLUGIN_ROOT` refers to the codex plugin root at `~/.claude/plugins/marketplaces/openai-codex/plugins/codex`. If the env var isn't set, use the absolute path.

Capture the full output. Do NOT present it to the user yet.

### Step 3: Validate Every Finding

For EACH finding in the Codex output, perform these checks:

#### 3a. Verify the code location exists
- Read the file and line range cited in the finding
- If the file or lines don't exist, mark as **INVALID** (hallucinated)

#### 3b. Cross-reference with project documentation
- Check CLAUDE.md, README.md, and any relevant docs in the project
- If the finding contradicts a documented intentional design choice, mark as **INTENTIONAL**

#### 3c. Assess technical accuracy
- Read the surrounding code context (not just the cited lines)
- Determine if the issue is technically real or a misunderstanding of the codebase
- If Codex misunderstood the pattern, mark as **FALSE POSITIVE**

#### 3d. Check severity
- Is this a real bug, security issue, or design flaw? Keep it.
- Is this a style nit, naming preference, or trivial observation? Mark as **NOISE**

### Step 4: Present Validated Results

Present ONLY the findings that survived validation. For each validated finding:

1. **The finding** (from Codex, in its own words)
2. **Validation status**: CONFIRMED — with a one-line explanation of why it's real
3. **Your assessment**: Do you agree with Codex? Add context from your knowledge of the project.

If findings were filtered out, add a brief summary at the end:

```
---
Filtered: X findings removed
- N hallucinated (file/line didn't exist)
- N intentional design choices
- N false positives (misunderstood pattern)
- N noise (style/naming nits)
```

### Step 5: Ask What to Do

If there are confirmed findings, ask:
> "Want me to address any of these findings?"

If all findings were filtered out:
> "Codex review came back clean after validation. No actionable findings."
