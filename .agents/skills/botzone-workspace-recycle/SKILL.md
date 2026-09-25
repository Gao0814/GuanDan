---
name: botzone-workspace-recycle
description: Recycle an already audited allowlist of artifacts from the fixed Botzone workspace. Use only for the separate cleanup task between live runs; do not use for live execution, unknown evidence, or broad directory cleanup.
---

# Botzone Workspace Recycle

Remove only the audited files named by the task prompt from `D:\VsCodeProject\BotzoneWorkspace` through recoverable Windows Recycle Bin operations. The prompt must supply the exact allowlist, expected sizes/hashes, preserved directories, and final inventory.

This skill never targets the owner's separate `D:\VsCodeProject\GuanDanManualWorkspace`. Personal quick-test rollover is governed by the dedicated launcher and the `AGENTS.md` exception; do not mix its files into this allowlist.

## Preconditions

- Read the applicable `AGENTS.md`, `docs/CLEAN_HANDOFF.md`, and current status document.
- Inspect Git status and record HEAD. Do not touch an unexplained dirty tree.
- Confirm `D:\VsCodeProject` has exactly the expected top-level `Botzone*` directory set.
- Verify the workspace root, preserved directories, and every target are normal non-link objects.
- Verify the recursive inventory exactly matches the prompt, including each target's size and full SHA-256.
- Confirm there is no safely attributable running project connector without printing its command line or secrets.

If any precondition or inventory item differs, perform zero cleanup. Report the mismatch; do not delete unknown items, infer replacement hashes, or request authorization already granted by `AGENTS.md`.

## Recycle

- Use a Windows Recycle Bin API such as `Microsoft.VisualBasic.FileIO.FileSystem::DeleteFile(..., SendToRecycleBin)`.
- Process each validated absolute file path individually in the given order.
- Do not use permanent deletion, recursive deletion, wildcards, directory removal, cross-shell path composition, or empty the Recycle Bin.
- Preserve the workspace root and the directories specified by the task.
- If one recycle operation fails, stop immediately and report completed and remaining targets. Do not switch to another deletion mechanism.

## Verify and report

Confirm target paths are absent, preserved directories are normal and empty as expected, the top-level `Botzone*` set did not drift, no connector or live action ran, and Git HEAD/status are unchanged. Report the exact low-sensitivity target inventory and whether any permanent deletion occurred. End the cleanup task without preflight, seed assignment, table creation, or live execution.
