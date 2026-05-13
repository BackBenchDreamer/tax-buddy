# Archive

This directory contains repository materials that were intentionally retained for historical reference but moved out of the active project root during production cleanup.

## Contents

### `docs/`
Historical design, implementation, deployment, and integration documents that describe point-in-time project milestones or one-time delivery events. These files were archived because they are not the current operational source of truth for the repository.

### `tests/`
One-off validation and milestone test scripts that are not part of the maintained pytest test suite. These files were archived to reduce confusion about which tests are canonical while preserving them for traceability and manual reference.

## Why these files were archived

The cleanup was based on `PRODUCTION_CLEANUP_AUDIT.md` recommendations to:
- reduce top-level repository clutter
- separate active documentation from historical reporting
- distinguish maintained tests from manual or milestone-specific scripts
- preserve useful history without keeping stale files in primary development paths

## What remains active

The active sources of truth remain in the main repository locations, including:
- `README.md`
- `ARCHITECTURE.md`
- `backend/tests/`
- application source code under `backend/app/`, `backend/ml/`, and `frontend/`

Archive contents should generally not be updated unless there is a specific historical or compliance reason to do so.