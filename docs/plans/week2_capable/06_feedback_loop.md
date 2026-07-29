# Goal: Shorten the development feedback loop

## Files

| File | What It Does |
|------|-------------|
| `week2_capable/bin/rebuild` | Script that rebuilds both the Boukensha and Mud Manager gems together |
| `week1_baseline/ruby/12_context/Gemfile` | Boukensha gem dependencies |

## Key Architecture Decisions

- **Single rebuild command**: One script rebuilds both gems from source, ensuring they are always built from the same state. This prevents version mismatch errors where one gem is stale while the other is current.

## Key Findings

- Before the rebuild script, testing produced confusing errors caused by stale local gem builds. Code changes wouldn't take effect because `require` still loaded the old gem from the installed path.
- Hot-reloading and auto-detection were considered but rejected as more complex than a simple rebuild script.

## Verification

```bash
cd week2_capable && bin/rebuild
```
