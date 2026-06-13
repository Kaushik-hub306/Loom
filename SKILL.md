# Loom — Memory Layer for AI Agents

Loom is your shared memory. Everything you learn about this project's conventions
should be stored in Loom so it persists across sessions and benefits every other
agent working on this codebase.

## How Loom Works (For You, The Agent)

You have 18 tools. Five fire automatically — you don't need to think about them.
Twelve require your judgment. Here is exactly what you must do.

---

## Automatic (You Never Need to Call These)

These happen without your intervention:

- **session_init** — fires on your first tool call. Injects `<!-- LOOM:AUTO_CONTEXT -->`
  with relevant conventions into your context. You'll see Top Reminders, domain rules,
  coaching amplifications, and org-wide knowledge.
- **observe** — fires when you call `teach`, `learn`, `reflect`, `amplify`, `retain`,
  `succession`, `federate`, or `set_clearance`. Records the action as an observation
  in the background buffer.
- **learn** — auto-extracts rules when the observation buffer reaches threshold (3+
  observations) or at session end.
- **reflect** — auto-flushes all buffered observations at session end.
- **recall_relevant** — auto-injects context at session start. Also callable explicitly
  when your task changes mid-session.

---

## When to Use Each Tool

### `teach` — Most Important. Use This Constantly.

Call `teach` whenever:
- The user explicitly states a convention: "we use tabs not spaces", "always use type hints"
- You observe a pattern across the codebase: every file uses a certain import style
- The user corrects your work: "no, we do it this way"
- You discover a project-specific rule from reading configs, READMEs, or code

**Always include:**
- `domain` — the right domain (coding, testing, security, style, architecture, process, documentation, general)
- `rule` — a clear, actionable statement: "Do X" or "Never do Y"
- `rule_type` — a specific type within the domain (e.g., type_safety, naming, git_workflow)
- `confidence` — 7-8 for user-stated conventions, 9-10 for reinforced ones, 5-6 for patterns you noticed
- `example` — optional but helpful: a short code snippet showing the rule

```
teach(domain="coding", rule="All public functions must have type hints",
      rule_type="type_safety", confidence=8,
      example="def get_user(id: int) -> User:")
```

### `learn` — When You Observe Something Worth Remembering

Use `learn` for richer observations where you want to capture context beyond a single rule:

```
learn(context="Refactoring the payment service",
      observation="The old code had nested callbacks 4 levels deep. We flattened them
      with async/await. Error handling is now at the top level instead of scattered
      across callbacks. Much easier to reason about.",
      domain="coding")
```

Loom extracts rules from the observation text. LLM extraction produces smarter rules
than keyword extraction, but both work.

### `recall_memory` — Search for Something Specific

Use when you need to look up conventions mid-task:

```
recall_memory(query="error handling", domain="coding", min_confidence=5)
```

### `recall_relevant` — When Your Task Changes Mid-Session

The auto session_init covers your initial task. If you pivot to something completely
different, call `recall_relevant` to reload context:

```
recall_relevant(task="Fix the authentication bug in the login flow",
                role="backend-engineer")
```

### `amplify` — When a Top Performer's Rule Deserves More Weight

Use when a senior team member has articulated *why* a rule matters:

```
amplify(rule_id="coding::type_safety::all-public-functions-must-have-type-hints",
        coach="Sarah Chen", coach_role="Staff Engineer",
        amplification="Type hints caught 3 production bugs last quarter. The 5 seconds
        it takes to add annotations saves hours of debugging. Every public function
        without a type hint is a future incident.",
        target_roles=["backend-engineer", "fullstack-dev"])
```

This makes the rule appear under "Coaching Amplifications" in future session_init
injections, with the coach's name and reasoning.

### `retain` — Mark a Rule as Permanent

Use when a convention is foundational to the project. Permanent rules never decay:

```
retain(rule_id="security::secrets::never-hardcode-api-keys",
       reason="This caused a security incident in Q1 2025. Non-negotiable.")
```

### `onboard` — When a New Team Member Joins

Generates a complete onboarding pack for a specific role:

```
onboard(role="backend-engineer")
```

Returns core conventions, key decisions from the timeline, succession knowledge,
and coaching amplifications — all formatted for a new hire's first day.

### `succession` — When Someone Leaves the Team

Captures what a departing team member knows before they go. Three-step flow:

```
succession(member="jane-smith", role="staff-engineer", action="start")
succession(member="jane-smith", role="staff-engineer", action="capture",
           title="Why we chose PostgreSQL", importance=9,
           detail="Evaluated MySQL, Postgres, and Mongo in Q3 2024...",
           category="design_decision")
succession(member="jane-smith", role="staff-engineer", action="finalize")
```

### `timeline` — Audit What Was Learned and When

Query the organization's learning history:

```
timeline(days=90, domain="security", limit=10)
```

### `set_clearance` — Restrict Who Can See a Rule

For sensitive conventions (security practices, internal architecture):

```
set_clearance(rule_id="security::secrets::api-key-rotation-schedule",
              clearance="confidential",
              allowed_roles=["security-engineer", "tech-lead"],
              allowed_teams=["platform"])
```

Valid clearance levels: `public`, `internal`, `confidential`, `restricted`, `secret`.

### `federate` — Import Conventions from Another Project

```
federate(project_path="/path/to/other/project", project_name="shared-infra")
```

### `get_stats` — Check Learning Progress

Shows how many rules have been learned, by domain, with average confidence.
Also shows the extraction engine in use (LLM provider or keyword).

### `export` / `export_timeline` — Export Data

Export rules or timeline in markdown, JSON, or compact format.

---

## Domain Guide

Choose the right domain for every rule:

| Domain | Use For |
|--------|---------|
| `coding` | Type safety, error handling, function design, naming, imports, performance |
| `testing` | Unit tests, integration tests, coverage, mocking, fixtures, assertions |
| `security` | Auth, secrets management, input validation, cryptography, threat model |
| `style` | Formatting, quotes, indentation, line length, brace style, comments |
| `architecture` | Design patterns, module structure, service layer, dependencies |
| `process` | Git workflow, branching, commit messages, PR process, CI/CD, deployments |
| `documentation` | Docstrings, READMEs, API docs, inline comments, changelogs |
| `general` | Catch-all for preferences, best practices, habits that don't fit above |

---

## Confidence Guide

| Score | Meaning | When to Use |
|-------|---------|-------------|
| 9-10 | Explicitly stated AND reinforced by examples or outcomes | User said it multiple times, or it's documented in project README/CONTRIBUTING |
| 7-8 | Explicitly stated by the user | User just said "we do X" |
| 5-6 | Pattern you observed in the codebase | You noticed most files follow this pattern |
| 3-4 | Suggested or implied | You think this might be a convention but aren't sure |
| 1-2 | Vague mention | Someone mentioned it in passing |

---

## Best Practices

1. **Teach immediately.** When the user states a preference, call `teach` within the same turn. Don't wait.
2. **Be specific in rules.** "Use type hints" is weak. "All public functions must have type annotations on parameters and return values" is strong.
3. **Use the right domain.** A security rule in `coding` domain won't surface when someone searches security conventions.
4. **Boost confidence on repetition.** If the user mentions the same rule twice, the second `teach` auto-boosts confidence via deduplication.
5. **Call `recall_relevant` on task changes.** If the user says "actually, let's work on the deployment pipeline instead," reload context for that domain.
6. **Amplify sparingly.** Only amplify rules where the coach's reasoning adds real value. Don't amplify every rule.
7. **Check `get_stats` periodically.** See what's been learned and what domains are thin.
8. **Commit `.loom/rules.json` and `.loom/conventions.md` to git.** This is how your team shares conventions. Rules file = machine-readable. Conventions file = human-readable.

---

## What You Should Never Do

- Don't fabricate conventions. If you're unsure, use confidence 4-5 and say "I noticed a pattern."
- Don't teach the same rule repeatedly. Loom deduplicates by rule text — if the rule already exists, confidence auto-boosts.
- Don't use `general` domain unless no other domain fits. Specific domains improve recall relevance.
- Don't set clearance to `secret` or `restricted` unless the user explicitly asks you to.
- Don't call `observe` or `session_init` manually — they fire automatically.
