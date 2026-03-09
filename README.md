# exoclaw-github

GitHub Actions channel for [exoclaw](https://github.com/Clause-Logic/exoclaw).

Runs the exoclaw agent stack inside a GitHub Actions workflow, turning issues, PR comments, and `workflow_dispatch` into agent turns. Responses are posted as GitHub comments. Session history is persisted to a `bot-state` branch so conversations carry context across runs.

**See it live:** [exoclaw-github-demo](https://github.com/Clause-Logic/exoclaw-github-demo) — open an issue or comment `@exoclawbot` and the bot will respond.

## Quick start

Drop this into `.github/workflows/exoclaw.yml`:

```yaml
name: exoclaw
on:
  issues:
    types: [opened]
  issue_comment:
    types: [created]
  pull_request:
    types: [opened]
  pull_request_review_comment:
    types: [created]
  workflow_dispatch:
    inputs:
      message:
        description: "Message to send to the agent"
        required: true
        type: string

jobs:
  run:
    runs-on: ubuntu-latest
    concurrency:
      group: ${{ github.event.issue.number || github.event.pull_request.number || github.run_id }}
      cancel-in-progress: false
    if: |
      github.event_name == 'workflow_dispatch' ||
      contains(fromJSON('["OWNER","MEMBER","COLLABORATOR","CONTRIBUTOR"]'), github.event.comment.author_association) ||
      contains(fromJSON('["OWNER","MEMBER","COLLABORATOR","CONTRIBUTOR"]'), github.event.issue.author_association) ||
      contains(fromJSON('["OWNER","MEMBER","COLLABORATOR","CONTRIBUTOR"]'), github.event.pull_request.author_association)
    permissions:
      issues: write
      pull-requests: write
      contents: write
      models: read
    steps:
      - uses: actions/checkout@v4
      - uses: Clause-Logic/exoclaw-github@main
        with:
          trigger: "@exoclawbot"
          tools: >-
            github_pr_diff,
            github_file,
            github_checks,
            github_search,
            github_review,
            github_label,
            github_reaction
```

No API keys required — uses [GitHub Models](https://github.com/marketplace/models) (`gpt-4.1-mini`) via the built-in `GITHUB_TOKEN`.

To use Anthropic or OpenAI instead, uncomment `model:` and add the key as a repo secret:

```yaml
        with:
          model: claude-sonnet-4-5
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

## Inputs

| Input | Default | Description |
|---|---|---|
| `model` | `github/gpt-4.1-mini` | LLM model. Use `claude-sonnet-4-5` or `gpt-4o` with the relevant API key secret. |
| `trigger` | `@exoclawbot` | Word that must appear in a comment to trigger the bot. Empty = respond to all. |
| `tools` | _(none)_ | Comma-separated list of GitHub tools to enable (see below). |
| `respond_to_issues_opened` | `true` | Respond when an issue is opened. |
| `respond_to_prs_opened` | `false` | Respond when a PR is opened. |

## Tools

Workspace tools (read files, write files, run shell commands) are always enabled. GitHub tools are opt-in:

| Tool | What it does |
|---|---|
| `github_pr_diff` | Fetch the unified diff for a PR |
| `github_file` | Read any file at any ref |
| `github_checks` | Read CI check run results |
| `github_search` | Search issues and code |
| `github_review` | Submit PR reviews with inline comments |
| `github_label` | Add, remove, or list labels |
| `github_reaction` | React to the triggering comment |
| `github_issue` | Create, update, or close issues _(higher-stakes — opt in explicitly)_ |

## Supported events

| Event | Default behaviour |
|---|---|
| `issues` (opened) | Always respond |
| `issue_comment` (created) | Respond if trigger word present |
| `pull_request` (opened) | Off by default |
| `pull_request_review_comment` (created) | Respond if trigger word present |
| `workflow_dispatch` | Always respond |

## Session state

Sessions are keyed by `github:issue:{number}` or `github:pr:{number}`. History is stored on the `bot-state` branch and restored at the start of each run, so the bot remembers prior exchanges in the same thread. Concurrent runs on the same issue are serialized via the `concurrency` key.

## Ideas

A few things this is well-suited for:

- **PR reviewer** — give it `github_pr_diff`, `github_file`, and `github_review`. Tag it on a PR and it reads the diff, checks context in related files, and submits a review with inline comments.
- **Issue triage** — auto-label new issues, ask clarifying questions, link to related issues via `github_search`.
- **CI explainer** — tag it on a failing PR and it fetches the check run logs (`github_checks`), reads the relevant source files, and explains what broke and why.
- **Documentation assistant** — ask it questions about the codebase directly in issues. It can read any file and has shell access to run grep, tests, etc.
- **Release notes** — trigger via `workflow_dispatch` with a version number; it searches merged PRs and generates a changelog.
- **Rubber duck** — leave a half-formed idea in an issue and let it poke holes, ask questions, or sketch an approach.
