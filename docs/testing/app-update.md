# Manual test: release pipeline and App update (#34, #35, #36)

These are the checks the automated suite can't do: a real tag push through CI, and a frozen binary
that updates itself. Everything runs against a **throwaway GitHub repo**. The real repo never gets
test tags, so its Releases page, its "latest" Release and setuptools-scm versions stay untouched.

The app reads the Release source from the `FRITZ_UPDATE_REPO` environment variable
(`<owner>/<repo>`). When it is unset or empty, the app uses the real repo.

Placeholders below: `TEST_REPO=Jonny1797/fritz-update-test`, branch `ralph/issue-32-33-34-35-36`.

> The binaries use your **real** config, database and keyring entry. That is fine (same schema as
> the branch), but back up the database first if you want to be safe.

## 0. Set up the test repo

1. Create an empty **public** repo `TEST_REPO` on GitHub. It must be public, because the app calls
   the API without a token, and that returns 404 for private repos.
2. In its settings, allow Actions with read/write permissions (the workflow sets
   `contents: write`, but org/repo policy can still block it).
3. Locally, make a test branch and add the remote:

   ```bash
   git switch -c update-test ralph/issue-32-33-34-35-36
   git remote add updatetest git@github.com:Jonny1797/fritz-update-test.git
   ```

4. The release job needs a CHANGELOG section per tag (`scripts/changelog_section.sh` fails
   otherwise). Add one for `0.9.8` on the test branch only:

   ```markdown
   ## [0.9.8] - 2026-11-16

   - Update test, first release.
   ```

   Commit it and push the branch: `git push updatetest update-test:master`.

**Tag without creating local tags.** Push `<commit>:refs/tags/<tag>` so no test tag ends up in
your local repo, where it would change the setuptools-scm version and could later be pushed to
`origin`/`github` with `--tags`:

```bash
git push updatetest HEAD:refs/tags/0.9.8
```

## 1. Release pipeline (#34)

After the `0.9.8` push, in the test repo's Actions:

- [ ] Both build jobs log `Version 0.9.8 matches tag 0.9.8`.
- [ ] Release `0.9.8` lists `fritz-callhistory-linux-x86_64`,
      `fritz-callhistory-windows-x86_64.exe` and `SHA256SUMS`.
- [ ] The checksums verify:

  ```bash
  mkdir -p ~/update-test && cd ~/update-test
  gh release download 0.9.8 -R Jonny1797/fritz-update-test
  sha256sum -c SHA256SUMS      # both files: OK
  ```

**Mismatch must fail.** On a separate branch that `0.9.9` will *not* build on, force a wrong
version and tag it:

```bash
git switch -c update-test-mismatch update-test
# .github/workflows/release.yml, build job: add
#     env:
#       SETUPTOOLS_SCM_PRETEND_VERSION: "0.0.1"
git commit -am "test: force version mismatch"
git push updatetest HEAD:refs/tags/0.9.97
git switch update-test
```

- [ ] Both build jobs fail at "Check built version matches the tag"
      (`Built version 0.0.1 does not match tag 0.9.97`).
- [ ] There is no Release `0.9.97`. Delete the tag: `git push updatetest :refs/tags/0.9.97`.

**Optional: Forgejo mirror.** On a throwaway Forgejo repo with Actions and a runner, push the test
branch with `GITHUB_REPO: Jonny1797/fritz-update-test` in `.forgejo/workflows/release.yml`, then
push the same tag there as well.

- [ ] The Forgejo Release `0.9.8` mirrors all three files, including `SHA256SUMS`.

(Otherwise, check this with the first real release that ships the feature.)

## 2. Update check (#35), Linux

Start the `0.9.8` binary against the test repo:

```bash
cd ~/update-test && chmod +x fritz-callhistory-linux-x86_64
FRITZ_UPDATE_REPO=Jonny1797/fritz-update-test ./fritz-callhistory-linux-x86_64
```

- [ ] Hilfe → Über… shows version `0.9.8`.
- [ ] Hilfe → Nach Updates suchen… → "Fritz!Box Anrufhistorie ist aktuell (0.9.8)."

Publish `0.9.9`: add a `## [0.9.9]` CHANGELOG section on `update-test`, commit, push the branch,
then `git push updatetest HEAD:refs/tags/0.9.9`. Wait for the Release.

- [ ] The check now shows "Version 0.9.9 ist verfügbar (installiert: 0.9.8)" with the release notes
      under "Details", and the buttons Jetzt aktualisieren / Später.
- [ ] **Fallback:** copy the binary into a read-only folder (`chmod a-w <dir>`) and check from there.
      You should get the reason "Der Ordner der App ist nicht beschreibbar." and "Release-Seite
      öffnen", which opens the test repo's Release page.
- [ ] **Real GitHub:** start the binary *without* `FRITZ_UPDATE_REPO`. The check offers the real
      latest Release (e.g. `1.0.1`); "Jetzt aktualisieren" then refuses with "…keine
      SHA256SUMS-Datei…" because older Releases don't have one. The binary is unchanged.
- [ ] No network request happens at start (e.g. no GitHub connection in `ss -tp` before the first
      click).

## 3. Self-update (#36), Linux

Again with `FRITZ_UPDATE_REPO` set, starting from the `0.9.8` binary:

- [ ] **Cancel:** Jetzt aktualisieren → click Abbrechen during the download → status bar "Update
      abgebrochen.". `ls` shows no `.new`, and `sha256sum` of the binary still matches `0.9.8`.
- [ ] **Quit during download:** start the update, then quit right away (tray → Beenden). The app
      exits within a few seconds (not ~10 s). At the latest after the next start there is no `.new`.
- [ ] **Install, restart later:** let it finish → "Version 0.9.9 wurde installiert…" → Später.
      `ls` shows the binary plus `.old`. Checking again shows "Version 0.9.9 ist bereits installiert
      – Neustart ausstehend.", without downloading again.
- [ ] **Restart now:** choose Jetzt neu starten. The app closes and starts again by itself;
      Über… shows `0.9.9`, and `.old` is gone shortly after the start.
- [ ] The swapped binary is still executable (`ls -l`).
- [ ] **Optional, checksum mismatch:** replace the Release's `SHA256SUMS` with a wrong one
      (`gh release upload 0.9.9 SHA256SUMS --clobber -R …` with an edited file), restore `0.9.8`
      and update. You should get "Die Prüfsumme der Datei stimmt nicht…", the binary unchanged and
      no `.new`.

## 4. Self-update (#36), Windows (if available)

Same as sections 2–3 with `fritz-callhistory-windows-x86_64.exe` (SmartScreen may warn about the
unsigned binary):

```powershell
$env:FRITZ_UPDATE_REPO = "Jonny1797/fritz-update-test"
.\fritz-callhistory-windows-x86_64.exe
```

- [ ] Install + Jetzt neu starten → the new process starts and shows `0.9.9`.
- [ ] `fritz-callhistory-windows-x86_64.exe.old` disappears within ~10 s of the new start (the
      old process holds it locked briefly; the cleanup retries).

## 5. Clean up

```bash
gh repo delete Jonny1797/fritz-update-test      # needs the delete_repo scope
git switch ralph/issue-32-33-34-35-36
git branch -D update-test update-test-mismatch
git remote remove updatetest
git tag -l '0.9.*'                              # must print nothing
rm -rf ~/update-test
```

Delete the throwaway Forgejo repo too, if you made one. Then tick the matching acceptance criteria
in #34/#35/#36 (or on PR #38).
