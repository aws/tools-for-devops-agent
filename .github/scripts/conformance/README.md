# Skill conformance corpus

`cases.json` holds the test cases for the skill rules of this repository. The rules are in `.github/scripts/validate_skill_publishing.py` and in the "Publishing Rules" section of `CONTRIBUTING.md`.

The file is a JSON array of case objects, sorted by `id`, with a 2-space indent and a final newline. Each case is one skill folder, `skills/<name>/`:

```json
{
  "id": "name-not-folder-name",
  "name": "demo",
  "files": {
    "SKILL.md": { "text": "---\nname: other\n..." },
    "images/pixel.png": { "base64": "iVBORw0KGgo..." }
  },
  "expect": "fail",
  "error": "name must equal the folder name"
}
```

- `id`: the case name. It is unique in the file.
- `name`: the skill folder name. Many cases use the same folder name.
- `files`: each path is relative to the skill folder. `text` is UTF-8 text, and `base64` is raw bytes.
- `expect`: `pass` or `fail`.
- `error`: for a `fail` case, the exact error message or a part of it.
- `stricter` (optional): the case fails because of a rule that is stricter than skills need to be published. For example, a two-part `metadata.version` or a YAML anchor.

## Rule for every validator

Every tool that validates or publishes the skills of this repository must give the `expect` result for every case. A tool can pass a case that has `"stricter": true`. A tool must not pass any other `fail` case.

`validate_skill_publishing.py` runs every case through its head-skill rules before it checks any skill. This self-check also requires the golden skill content hash and the digest below. When the self-check fails, the script exits with code 2 and checks no skill. To run only the self-check:

```bash
python3 .github/scripts/validate_skill_publishing.py --self-check-only
```

## Corpus digest

Corpus digest: `df26439cc6d8f5c7eb74250b6ab5ca512ca6f6902464c8affc30b3b82ac7ed2e`

The digest is the SHA-256 (hex) of the bytes of `cases.json`. The script has the same value in its `CONFORMANCE_SHA256` constant, and the self-check fails when the file has a different digest. Thus a change to `cases.json` must change `CONFORMANCE_SHA256` and this line in the same pull request. After you add or change a case, print the new digest:

```bash
sha256sum .github/scripts/conformance/cases.json
```

On macOS, use `shasum -a 256` instead of `sha256sum`.
