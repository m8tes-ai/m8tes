# SDK changelog fragments

Every change to the Python SDK drops **one file here** instead of editing
`## [Unreleased]` in `CHANGELOG.md`. Two PRs never touch the same file, so
they cannot conflict.

GitHub's conflict check is a plain 3-way merge. It ignores the `merge=union`
driver on `CHANGELOG.md`, so two PRs that both insert under `[Unreleased]`
still show "conflicts that must be resolved" and the PR stays DIRTY. Fragments
sidestep that.

## How to add an entry

Create `changelog.d/<slug>.<category>.md` in this directory:

- **`<slug>`** — short and unique to your PR. The branch name works.
- **`<category>`** — one of: `added`, `changed`, `deprecated`, `removed`,
  `fixed`, `security`.

The body is the markdown bullet as it should appear under that heading:

```md
- `client.settings.update(...)` — what the caller can do now.
```

## What happens at release

From the applications repo root:

```bash
python scripts/assemble_changelog.py --version X.Y.Z \
  --changelog sdk/py/CHANGELOG.md \
  --fragment-dir sdk/py/changelog.d \
  --date YYYY-MM-DD
```

That folds these fragments, plus anything still sitting under `[Unreleased]`,
into `## [X.Y.Z]` and deletes the fragments. Bump `pyproject.toml` in the same
release. CI's `assemble_changelog.py --check` validates this directory.
