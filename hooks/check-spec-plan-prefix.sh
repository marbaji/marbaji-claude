#!/bin/bash
# Hook: Enforce spec_/plan_ naming convention for superpowers documents
# Triggered by: PreToolUse on Write tool

fp=$(jq -r '.tool_input.file_path // ""')
BASENAME=$(basename "$fp")

# Only check .md files
case "$fp" in *.md) ;; *) exit 0;; esac

NEEDS_SPEC=0
NEEDS_PLAN=0

# Check if file is in a specs directory
if echo "$fp" | grep -q '/specs/'; then NEEDS_SPEC=1; fi
# Check if filename looks like a design/spec doc
if echo "$BASENAME" | grep -qiE '\-design\.md$'; then NEEDS_SPEC=1; fi

# Check if file is in a plans directory
if echo "$fp" | grep -q '/plans/'; then NEEDS_PLAN=1; fi
# Check if filename looks like a plan doc
if echo "$BASENAME" | grep -qiE '\-plan\.md$'; then NEEDS_PLAN=1; fi

if [ "$NEEDS_SPEC" = "1" ] && ! echo "$BASENAME" | grep -q '^spec_'; then
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Spec document missing spec_ prefix. Rename: %s -> spec_%s"}}' "$BASENAME" "$BASENAME"
elif [ "$NEEDS_PLAN" = "1" ] && ! echo "$BASENAME" | grep -q '^plan_'; then
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Plan document missing plan_ prefix. Rename: %s -> plan_%s"}}' "$BASENAME" "$BASENAME"
fi
