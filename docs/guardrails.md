# Guardrails

## Purpose

The guardrail layer protects the local agent harness from invalid inputs,
unbounded execution, malformed planner output, and empty responses.

P1 focuses on execution safety rather than content moderation.

---

## Goals

- Reject invalid requests early
- Prevent infinite execution
- Prevent malformed planner output from crashing execution
- Return friendly user-facing messages
- Produce observable guardrail events

---

## Guardrail Categories

### Input Guardrails

Implemented in:

src/guardrails/input_guardrail.py

Checks:

- Empty prompt
- Whitespace-only prompt
- Maximum prompt length

Configuration

max_prompt_chars

Example

Input:

""

Result

EMPTY_PROMPT

---

### Execution Guardrails

Implemented in:

src/guardrails/execution_guardrail.py

Checks

- Maximum ReACT iterations
- Maximum execution time
- Maximum planner task count

Configuration

max_react_iterations

max_execution_seconds

max_tasks_per_execution

Example

Iteration > limit

↓

MAX_ITERATIONS

---

### Output Guardrails

Implemented in:

src/guardrails/output_guardrail.py

Checks

- Planner JSON validity
- Planner task count
- Empty final response

Planner JSON failures fall back to a single safe task using the original user goal rather than failing the request.

Example

Planner Output

INVALID JSON

↓

Fallback

[
    {
        "goal": original_goal
    }
]

---

## GuardrailViolationError

All guardrail failures raise GuardrailViolationError.

Fields

code

public_message

details

The public message is returned to the user.

The details field is intended only for logging and tracing.

---

## Configuration

Default values

max_prompt_chars = 8000

max_react_iterations = 5

max_tasks_per_execution = 3

max_execution_seconds = 60

Environment overrides follow the existing ConfigManager pattern.

---

## Observability

Guardrail violations should

- create structured log entries
- include request/session correlation
- set OpenTelemetry span attributes

Recommended span attributes

guardrail.triggered

guardrail.code

guardrail.limit

guardrail.elapsed

guardrail.iteration

Prompt and response bodies must never be logged.

---

## User Experience

Known guardrail violations return friendly messages instead of stack traces.

Examples

EMPTY_PROMPT

→ "Please enter a prompt."

MAX_ITERATIONS

→ "I couldn't safely complete that request."

TIMEOUT

→ "The request took too long."

EMPTY_RESPONSE

→ "I couldn't generate a response."

INVALID_PLAN

→ Planner falls back to a single safe task.

---

## Scope

Included in P1

- Input validation
- Execution limits
- Planner structured-output validation
- Empty-response protection
- Observability

Not included in P1

- Content moderation
- Prompt-injection detection
- Tool allow/deny lists
- PII redaction
- Output fact checking
- Hallucination detection

These are planned for future phases.