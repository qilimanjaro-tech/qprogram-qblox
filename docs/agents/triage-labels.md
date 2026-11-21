# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in this repo's GitHub Issues.

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`               | `question`           | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`    | Requires human implementation            |
| `wontfix`                  | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.

`question` and `wontfix` already exist on the repository (GitHub's default set; `question` reads "Further information is requested"). `needs-triage`, `ready-for-agent` and `ready-for-human` do not exist yet: don't create them without the human's yes. TODO(human): create the three labels, or name existing ones to use instead.

The issue forms in `.github/ISSUE_TEMPLATE/` set the issue type (Bug, Feature, Task), not a label. Linear QHC tickets follow the team's Linear workflow states, not these labels.

Edit the "Label in our tracker" column to match whatever vocabulary you actually use.
