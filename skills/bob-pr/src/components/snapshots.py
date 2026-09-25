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

from components.pull_requests import latest_revision, utc_now


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
            os.makedirs(os.path.dirname(shadow_path), exist_ok=True)
            shutil.copy2(real_path, shadow_path)
            file_hash = _sha256_of_file(real_path)
        else:
            file_hash = None
        manifest[relative_path] = {"sha256": file_hash}
    os.makedirs(_shadow_dir(project_root, pull_request_id), exist_ok=True)
    with open(_manifest_path(project_root, pull_request_id), "w") as handle:
        json.dump(manifest, handle, indent=2)
    return manifest


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
    diffs = {}
    for relative_path in file_paths:
        real_path = os.path.join(project_root, relative_path)
        shadow_path = os.path.join(
            _shadow_dir(project_root, pull_request_id), relative_path
        )
        original_lines = _readlines_or_empty(real_path)
        edited_lines = _readlines_or_empty(shadow_path)
        diff_text = "".join(
            difflib.unified_diff(
                original_lines,
                edited_lines,
                fromfile=relative_path,
                tofile=relative_path,
            )
        )
        diffs[relative_path] = diff_text
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


def apply_pr(connection, pull_request_id, project_root):
    """Install shadow copies over the real files, atomically.

    Drives off the latest revision's file list — the same list the reviewer
    approved — so the applied change always matches the reviewed diff.
    For each planned file: skip when the real file's sha256 differs from the
    snapshot manifest (the user edited it during review → 'stale'), or when
    no snapshot hash exists to verify against. Otherwise write the copy to
    <path>.bobtmp and os.replace it into place so the swap cannot leave a
    half-written file. Records an 'applied' event.

    Returns {"applied": [...], "stale": [...]}.
    """
    revision = latest_revision(connection, pull_request_id)
    file_paths = json.loads(revision[3]) if revision else []
    manifest = _read_manifest(project_root, pull_request_id)
    shadow_root = _shadow_dir(project_root, pull_request_id)
    applied, stale = [], []
    for relative_path in file_paths:
        real_path = os.path.join(project_root, relative_path)
        shadow_path = os.path.join(shadow_root, relative_path)
        if not os.path.exists(shadow_path):
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
    if applied and not stale:
        connection.execute(
            "UPDATE prs SET status='applied' WHERE id=?",
            (pull_request_id,),
        )
    connection.execute(
        "INSERT INTO events (pr_id, revision_id, kind, body, created_at) "
        "VALUES (?, ?, 'applied', ?, ?)",
        (
            pull_request_id,
            (latest_revision(connection, pull_request_id) or (None,))[0],
            f"applied={applied} stale={stale}",
            utc_now(),
        ),
    )
    connection.commit()
    return {"applied": applied, "stale": stale}
