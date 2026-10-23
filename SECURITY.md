# Security

Do not post tokens, loginData.json, full game logs, player profiles or private
screenshots in public issues. Report a vulnerability with GitHub's private
vulnerability reporting when available; otherwise contact the repository owner
privately before publishing details.

Release packages are assembled from an explicit source allowlist. Packaging
rejects private filenames and recognizable GitHub/JWT credentials. Python wheels
are pinned with SHA-256 hashes; StarBreaker is pinned and verified before execution.
`release_integrity.json` lists the bundled files and their hashes. The ZIP has a
separate SHA-256 checksum on its GitHub release. These checks detect accidental
changes; they are not an independent code-signing certificate.

The app is an unsigned community alpha. Download releases from this repository.
Extraction and schema parsing never execute extracted game code or access game
process memory. Unknown game builds or unavailable account data must produce an
unavailable state rather than invented reputation numbers.
