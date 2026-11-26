# Issue tracker: GitHub issues and Linear (team QHC)

TODO(human): confirm the tracker with the maintainers. This file records what the repository shows; it is not yet an agreed rule.

## What the repository shows

- **GitHub Issues is the public intake and backlog.** `.github/ISSUE_TEMPLATE/` holds three issue forms, Bug (`[Bug]: `), Feature (`[Feature]: `) and Task (`[Task]: `), and `docs/developer/contributing.md` sends bugs and design questions to an issue. Backlog items are filed there too: issue #7 is a Task.
- **Linear team QHC holds the work QHC picks up.** Recent PRs branch from a QHC ticket (`qhc-1692-...`, `qhc-1847-...`) and name it in the PR body (`Implements QHC-1692`), not in the title.
- Earlier PRs used topic branches with no ticket key, and issue #7 also points at a ticket on another Linear team. Which tracker owns which work is the open question above.

Until the maintainers confirm, ask the human which tracker a new item belongs in.

## Conventions

- **Read a GitHub issue:** `gh issue view <number> --json number,title,body,labels,comments`.
- **List GitHub issues:** `gh issue list --state open --json number,title,labels`.
- **Create a GitHub issue:** use the title prefix and the sections of the matching form in `.github/ISSUE_TEMPLATE/`, then `gh issue create --title "..." --body "..."` after the human approves the title and body.
- **Comment, label or close a GitHub issue:** only with the human's yes. The repository is public, and replies to outside users are the team's to write.
- **Read or search a Linear ticket:** use the Linear tools scoped to team QHC, and refer to tickets by their identifier (`QHC-1847`).
- **Create or update a Linear ticket:** use the Linear tools on team QHC, after the human approves the title and body.
- **Branches and PRs:** see `## Branches and PRs` in `AGENTS.md`.

## Pull requests as a triage surface

**PRs as a request surface: no.** External pull requests are not part of the triage queue.

## When a skill says "publish to the issue tracker"

Ask the human which tracker. Work QHC will pick up becomes a Linear ticket on team QHC; a public report or backlog item becomes a GitHub issue. Either one only after the human approves its title and body.

## When a skill says "fetch the relevant ticket"

A `#<number>` reference is a GitHub issue: read it as in **Read a GitHub issue** above. A `QHC-####` identifier is a Linear ticket: read it with the Linear tools.
