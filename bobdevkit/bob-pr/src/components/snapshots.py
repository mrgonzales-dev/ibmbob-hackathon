"""Shadow copies: snapshot real files, compute diffs, apply on approval.

The agent edits copies under .bob-pr/tmp/<pr_id>/ instead of real files.
difflib computes the real diff between original and copy, so the review page
shows what the agent actually changed. apply_pr installs the copies over the
real files atomically and refuses files the user touched after the snapshot.
"""

import difflib
import hashlib
import json
import os
import shutil

from components.pull_requests import (
    TERMINAL_STATUSES,
    latest_revision,
    utc_now,
)


def _shadow_dir(project_root, pull_request_id):
    """Return the shadow-copy directory for one PR."""
    return os.path.join(
        project_root, ".bob-pr", "tmp", str(pull_request_id)
    )


def _manifest_path(project_root, pull_request_id):
    """Return the manifest file path that stores per-file sha256 hashes."""
    return os.path.join(
        _shadow_dir(project_root, pull_request_id), "manifest.json"
    )


def _sha256_of_file(path):
    """Return the hex sha256 fingerprint of a file's contents."""
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _read_manifest(project_root, pull_request_id):
    """Load the snapshot manifest for a PR. Returns {} when absent."""
    try:
        with open(_manifest_path(project_root, pull_request_id)) as handle:
            return json.load(handle)
    except FileNotFoundError:
        return {}


def snapshot_pr(connection, pull_request_id, project_root):
    """Copy every planned file into the shadow dir and fingerprint originals.

    Writes .bob-pr/tmp/<id>/manifest.json mapping each path to its sha256.
    Files that do not exist yet get a null hash and count as new files.
    A shadow copy that already holds edits is kept, not clobbered — its
    manifest entry gets "kept_edits": True so the CLI can warn.
    Returns the manifest dict.
    """
    revision = latest_revision(connection, pull_request_id)
    file_paths = json.loads(revision[3]) if revision else []
    manifest = {}
    for relative_path in file_paths:
        real_path = os.path.join(project_root, relative_path)
        shadow_path = os.path.join(
            _shadow_dir(project_root, pull_request_id), relative_path
        )
        if os.path.exists(real_path):
            file_hash = _sha256_of_file(real_path)
            if os.path.exists(shadow_path) and (
                _sha256_of_file(shadow_path) != file_hash
            ):
                manifest[relative_path] = {
                    "sha256": file_hash,
                    "kept_edits": True,
                }
                continue
            os.makedirs(os.path.dirname(shadow_path), exist_ok=True)
            shutil.copy2(real_path, shadow_path)
        else:
            file_hash = None
        manifest[relative_path] = {"sha256": file_hash}
    os.makedirs(_shadow_dir(project_root, pull_request_id), exist_ok=True)
    with open(_manifest_path(project_root, pull_request_id), "w") as handle:
        json.dump(manifest, handle, indent=2)
    return manifest


def live_diffs(project_root, pull_request_id, file_paths):
    """Compute shadow-vs-original diffs at call time. No DB write.

    A planned file with no shadow copy yields an empty diff — a missing
    copy means 'not written yet', never a deletion.
    """
    diffs = {}
    for relative_path in file_paths:
        real_path = os.path.join(project_root, relative_path)
        shadow_path = os.path.join(
            _shadow_dir(project_root, pull_request_id), relative_path
        )
        if not os.path.exists(shadow_path):
            diffs[relative_path] = ""
            continue
        diffs[relative_path] = "".join(
            difflib.unified_diff(
                _readlines_or_empty(real_path),
                _readlines_or_empty(shadow_path),
                fromfile=relative_path,
                tofile=relative_path,
            )
        )
    return diffs


def compute_diffs(connection, pull_request_id, project_root):
    """Compute real unified diffs of shadow copies vs originals.

    Runs difflib.unified_diff per planned file, stores the result on the
    latest revision's diffs_json column, and returns {path: diff_text}.
    A file missing from either side diffs against empty content.
    """
    revision = latest_revision(connection, pull_request_id)
    if not revision:
        return {}
    file_paths = json.loads(revision[3])
    diffs = live_diffs(project_root, pull_request_id, file_paths)
    connection.execute(
        "UPDATE revisions SET diffs_json=? WHERE id=?",
        (json.dumps(diffs), revision[0]),
    )
    connection.commit()
    return diffs


def _readlines_or_empty(path):
    """Read a file as a line list; missing files give an empty list."""
    try:
        with open(path) as handle:
            return handle.readlines()
    except FileNotFoundError:
        return []


def cleanup_shadows(project_root, pull_request_id):
    """Remove .bob-pr/tmp/<id>/ entirely — shadow copies and manifest.

    Called after a full apply or a close so shadow copies never
    accumulate.
    """
    shutil.rmtree(
        _shadow_dir(project_root, pull_request_id), ignore_errors=True
    )


def apply_pr(connection, pull_request_id, project_root):
    """Install shadow copies over the real files, atomically.

    Drives off the latest revision's file list — the same list the reviewer
    approved — so the applied change always matches the reviewed diff.
    Returns None when the PR does not exist or is terminal (applied or
    closed) — a terminal PR is a record, not a work item.
    For each planned file: skip when the real file's sha256 differs from the
    snapshot manifest (the user edited it during review → 'stale'), or when
    no snapshot hash exists to verify against. A planned file with no shadow
    copy is reported as 'missing' — never silently skipped. Otherwise write
    the copy to <path>.bobtmp and os.replace it into place so the swap
    cannot leave a half-written file. Records an 'applied' event.

    Once every planned file lands, the shadow dir is removed. When files
    are stale or missing the dir stays so the agent can retry.

    Returns {"applied": [...], "stale": [...], "missing": [...]}, or
    None when refused.
    """
    row = connection.execute(
        "SELECT status FROM prs WHERE id=?", (pull_request_id,)
    ).fetchone()
    if row is None or row[0] in TERMINAL_STATUSES:
        return None
    compute_diffs(connection, pull_request_id, project_root)
    revision = latest_revision(connection, pull_request_id)
    file_paths = json.loads(revision[3]) if revision else []
    manifest = _read_manifest(project_root, pull_request_id)
    shadow_root = _shadow_dir(project_root, pull_request_id)
    applied, stale, missing = [], [], []
    for relative_path in file_paths:
        real_path = os.path.join(project_root, relative_path)
        shadow_path = os.path.join(shadow_root, relative_path)
        if not os.path.exists(shadow_path):
            missing.append(relative_path)
            continue
        recorded_hash = manifest.get(relative_path, {}).get("sha256")
        if os.path.exists(real_path) and (
            recorded_hash is None
            or _sha256_of_file(real_path) != recorded_hash
        ):
            stale.append(relative_path)
            continue
        os.makedirs(os.path.dirname(real_path), exist_ok=True)
        temp_path = real_path + ".bobtmp"
        shutil.copy2(shadow_path, temp_path)
        os.replace(temp_path, real_path)
        applied.append(relative_path)
    if applied and not stale and not missing:
        connection.execute(
            "UPDATE prs SET status='applied' WHERE id=?",
            (pull_request_id,),
        )
        cleanup_shadows(project_root, pull_request_id)
    connection.execute(
        "INSERT INTO events (pr_id, revision_id, kind, body, created_at) "
        "VALUES (?, ?, 'applied', ?, ?)",
        (
            pull_request_id,
            (latest_revision(connection, pull_request_id) or (None,))[0],
            f"applied={applied} stale={stale} missing={missing}",
            utc_now(),
        ),
    )
    connection.commit()
    return {"applied": applied, "stale": stale, "missing": missing}
