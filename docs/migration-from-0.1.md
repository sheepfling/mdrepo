# Migration from the 0.1 prototype

Version 0.2 is a deliberate breaking reset rather than an incremental plugin-platform release.

| 0.1 prototype                         | 0.2 focused tool                   |
|---------------------------------------|------------------------------------|
| Project `markdown-hygiene`            | Project `markdown-repo-policy`     |
| Commands `markdown-hygiene` and `mdh` | Command `mdrepo`                   |
| `[tool.markdown-hygiene]`             | `[tool.mdrepo]`                    |
| Pluggy entry points and `-p` loading  | Fixed typed built-in rule registry |
| External-tool runner                  | Removed                            |
| Rumdl configuration pass-through      | Run Rumdl independently            |
| Lychee configuration pass-through     | Removed                            |
| Opaque plugin tables                  | Strict typed configuration         |
| Missing-target checking enabled       | Optional, disabled by default      |

The useful repository policies remain, but they now have stable `MDR...` rule IDs, structured
exceptions, exact-case checks, safe fixes, and graph output.

A normal replacement for an old combined invocation is:

```bash
uvx rumdl check --fix .
mdrepo check .
```

Do not mechanically copy old plugin or tool tables into the new configuration. Start with the small
`[tool.mdrepo]` example in the main README and add only the repository policies the project uses.
