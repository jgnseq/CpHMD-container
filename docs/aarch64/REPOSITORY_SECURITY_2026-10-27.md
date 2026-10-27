# Repository credential and artifact review

The working tree was clean at commit `5e20356` before this review. All 3,820
tracked files were inspected for private-key headers, GitHub token formats,
AWS access-key formats, credential-bearing HTTP URLs and sensitive filenames.
There were **no matches**. Both configured Git remotes were checked without
printing their values: neither contains HTTP user information. The 203 files
in the last commit introduced **no ELF executables/libraries**.

This is a scoped review, not a claim that every file is harmless or that all
historical credentials have been excluded. Arbitrary passwords do not have a
reliably recognizable format. Settings and shell scripts are executable code:
only trusted, reviewed settings/source should be run. The source tree already
contains 50 ELF files, including legacy scientific utilities and vendored PLUMED
build products, plus a historical tutorial ZIP and large PLUMED library. Their
presence predates this sprint's latest commit; they are not newly uploaded ARM
images. Removing inherited binary payloads is deferred, rather than rewriting
repository history during the ARM deadline.

The earlier password entered as an HTTPS username must be treated as potentially
exposed if it was a real password: change it if not already done, and revoke it
if it was actually a token. Cleaning a URL does not invalidate a credential.
Do not paste credentials into issues, command examples, logs or this report.
This follows [GitHub's exposed-secret guidance](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository):
revoke/rotate first; history rewriting is a separate coordinated decision.

## Guard used before future commits

`tests/check_repository_safety.py` inspects tracked working files and untracked
non-ignored files. `--staged` instead reads the actual index blobs, so a staged
secret cannot be hidden by subsequently editing the working copy. It reports
only relative paths and categories, never matching secret values. An immutable
`5e20356` baseline permits unchanged historical binary/archive payloads; new or
modified payloads, generated TPR/XTC/EDR/CPT files, files over 10 MiB, suspicious
authentication filenames and symlinks escaping the repository are rejected.
Credential patterns are checked even in grandfathered files. The check is local
and does not upload data or contact GitHub. It is not a complete history audit,
malware scanner or substitute for reviewing executable source.

Run from the repository root before staging, and again before committing:

```bash
python3 tests/check_repository_safety.py
# Stage only the explicit files documented for the development step.
python3 tests/check_repository_safety.py --staged
git diff --cached --check
git diff --cached --stat
```

The root `.gitignore` now excludes common authentication files and local
`artifacts/`/`validation-runs/` directories. Ignore rules do not remove already
tracked files and must not be bypassed using `git add -f` for credentials or
runtime payloads. Nothing installs a Git hook or changes Git configuration
silently. No commit/push is performed by the assistant.
The distinction between untracked ignore rules and existing tracked files is
documented in the [Git gitignore reference](https://git-scm.com/docs/gitignore).

## Native validation boundaries

New runs receive a source-only snapshot with per-file SHA-256 hashes and a Git
revision/dirty-state record; they do not receive `.git`, authentication files or
the user's home directory as a source archive. The maintained source preparer
selects tracked runtime/data plus an explicit list of gate files; it excludes
ignored/untracked authentication/debug files and rejects symlinked gate inputs.
All three source archives uploaded for these tests were inspected member by member:
only regular source/data files and provenance records were present, with no
credential/artifact pattern matches. Original scientific inputs and
frozen source are mounted read-only. All mutable simulation files stay below
`/projects/F202500250CPCAA2/`. SSH uses host-key verification with agent and X11
forwarding disabled. The native candidate SIF is checked against its recorded
SHA-256 before execution, uses ordinary-user container execution, and does not
require fakeroot for simulations. Hashes establish provenance/integrity, not
malware safety or scientific accuracy. Container execution is not presented as
a sandbox for untrusted code.

The 27 October quota check reported approximately 9.3 GB attributed to the user
and 6.8 GB to the project group on `/projects`, with zero explicit quota/limit
columns and default quota settings. Those values do not establish an unlimited
project allocation; bounded short tests proceed with ample reported filesystem
space, while existing results are retained.
