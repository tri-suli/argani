#!/usr/bin/env python3
"""Move the legacy job folders of a registered repository to the project's task folder in the argani home.

Usage: python3 import_jobs.py [dir] [--slug <slug> ...] [--artifact-root <folder>] [--apply]

Before the board, a repository kept its jobs at <toplevel>/<artifactRoot>/<slug>/ (artifactRoot from
.claude/argani.json, default 'argani'), committed on the job branches. This script finds those folders
in the working tree (tracked and untracked, not ignored) and on every local and remote branch, and
copies them to <home>/projects/<name>/tasks/<slug>/. Without --apply it only prints the plan.

Per slug one source is used: the branch named like the job branch of the slug when the working tree
copy differs from it; else the working tree; else the branch named like the job branch; else the
branch whose last commit touching the folder is newest. Every candidate is reported, with whether
its content differs from the chosen source. Symbolic links and submodules are never followed or
copied; they are listed under `skipped`. Files read from a branch are the raw blobs: no LFS pointer
or CRLF filter is applied.

A destination that already holds exactly the chosen files is `already-imported` (nothing to do). A
destination with different or extra files is a `conflict` and is never written. With --apply and a
home that is a git repository of its own, the imported jobs are recorded there with one commit.

Prints the plan as JSON (project, artifactRoot, artifactRootSource, tasksDir, jobs, applied,
recorded). The repository is never modified and nothing in it is deleted. Each job has a status:
new (dry run), imported, already-imported, conflict, missing (requested slug not found) or failed
(a copy or a read failed; what was written for that slug is removed again, earlier imports stay).
Exit 1 with a message when the repository is not registered or any job is a conflict, missing or
failed.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import argani_config
import argani_home
import artifact_check
import factory_state
import git_cli

LEGACY_CONFIG = Path(".claude") / "argani.json"
INTENT_FILE = "intent.md"
FILE_MODES = ("100644", "100755")
BRANCH_KEYS = ("branchPattern", "branchTypes", "protectedBranches")
WORKTREE = "worktree"


class ImportFailure(Exception):
    """A read or a copy that failed; carries the message for the human."""


class Candidate:
    """One place a legacy job folder was found: the working tree or one branch."""

    def __init__(self, source, full_ref=None):
        self.source = source  # display name: 'worktree' or the short branch name
        self.full_ref = full_ref  # refs/heads/... or refs/remotes/...; None for the working tree
        self.branch_name = None if full_ref is None else strip_ref(full_ref)
        self.files = []  # relative paths that can be copied
        self.skipped = []  # relative paths never copied: symbolic links, submodules, non-regular entries
        self.contents = {}


def git_bytes(toplevel, *args):
    """Raw stdout of a git command, or None on any failure."""
    try:
        result = subprocess.run(["git", "-C", str(toplevel), *args], capture_output=True, check=True, timeout=30)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return result.stdout


def decode_path(raw):
    return raw.decode("utf-8", errors="surrogateescape")


def strip_ref(full_ref):
    """The branch name of a ref: refs/heads/x -> x, refs/remotes/<remote>/x -> x."""
    if full_ref.startswith("refs/heads/"):
        return full_ref[len("refs/heads/"):]
    return full_ref[len("refs/remotes/"):].split("/", 1)[-1]


def short_ref(full_ref):
    prefix = "refs/heads/" if full_ref.startswith("refs/heads/") else "refs/remotes/"
    return full_ref[len(prefix):]


def read_legacy_file(toplevel):
    """(validated overrides, warning) of the legacy .claude/argani.json; (None, None) when absent."""
    path = Path(toplevel) / LEGACY_CONFIG
    if not path.is_file():
        return None, None
    try:
        return argani_config.read_config_file(path), None
    except ValueError as error:
        return None, f"ignoring the legacy config, using defaults: {error}"


def job_branch_config(config, legacy_overrides):
    """The config whose branch keys build the job branch: the legacy file's when it sets them."""
    effective = dict(config)
    for key in BRANCH_KEYS:
        if legacy_overrides and key in legacy_overrides:
            effective[key] = legacy_overrides[key]
    return effective


def group_by_slug(root, entries):
    """entries: (path, ok) pairs -> slug -> (copyable relative paths, skipped relative paths)."""
    grouped = {}
    for path, ok in entries:
        parts = path[len(root) + 1:].split("/", 1) if path.startswith(f"{root}/") else []
        if len(parts) == 2 and argani_config.SLUG_PATTERN.fullmatch(parts[0]):
            files, skipped = grouped.setdefault(parts[0], ([], []))
            (files if ok else skipped).append(parts[1])
    return {slug: (sorted(files), sorted(skipped)) for slug, (files, skipped) in grouped.items() if INTENT_FILE in files}


def worktree_candidates(toplevel, root):
    output = git_bytes(toplevel, "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", f"{root}/")
    entries = {}
    for raw in (output or b"").split(b"\0"):
        path = decode_path(raw)
        if not path:
            continue
        absolute = Path(toplevel) / path
        if absolute.is_symlink():
            entries[path] = False
        elif absolute.is_file():
            entries[path] = True
    return group_by_slug(root, entries.items())


def branch_candidates(toplevel, root, full_ref):
    output = git_bytes(toplevel, "ls-tree", "-r", "-z", full_ref, "--", f"{root}/")
    entries = []
    for raw in (output or b"").split(b"\0"):
        if raw:
            meta, _, path = decode_path(raw).partition("\t")
            entries.append((path, meta.split(" ", 1)[0] in FILE_MODES))
    return group_by_slug(root, entries)


def branch_refs(toplevel):
    """Full refnames of the local branches, then the remote branches (without refs/remotes/<remote>/HEAD)."""
    output = git_bytes(toplevel, "for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes")
    refs = (decode_path(output or b"")).splitlines()
    return [ref for ref in refs if not (ref.startswith("refs/remotes/") and ref.count("/") == 3 and ref.endswith("/HEAD"))]


def discover(toplevel, root):
    """slug -> candidates, the working tree first, then local, then remote branches."""
    found = {}
    sources = [(Candidate(WORKTREE), worktree_candidates(toplevel, root))]
    sources += [(Candidate(short_ref(ref), ref), branch_candidates(toplevel, root, ref)) for ref in branch_refs(toplevel)]
    for template, slugs in sources:
        for slug, (files, skipped) in slugs.items():
            candidate = Candidate(template.source, template.full_ref)
            candidate.files, candidate.skipped = files, skipped
            found.setdefault(slug, []).append(candidate)
    return found


def load_contents(toplevel, root, slug, candidate):
    for relative in candidate.files:
        path = f"{root}/{slug}/{relative}"
        try:
            if candidate.full_ref is None:
                candidate.contents[relative] = (Path(toplevel) / path).read_bytes()
            else:
                data = git_bytes(toplevel, "show", f"{candidate.full_ref}:{path}")
                if data is None:
                    raise ImportFailure(f"cannot read {relative} from {candidate.source}")
                candidate.contents[relative] = data
        except OSError as error:
            raise ImportFailure(f"cannot read {relative} from {candidate.source}: {error}") from error


def expected_job_branch(config, slug, candidate):
    """The job branch the candidate's intent names, or None when it cannot be computed."""
    text = artifact_check.normalize(candidate.contents[INTENT_FILE].decode("utf-8", errors="replace"))
    try:
        return argani_config.job_branch(config, slug, artifact_check.intent_type(text), artifact_check.intent_number(text))
    except ValueError:
        return None


def newest_candidate(toplevel, root, slug, branches):
    """The branch with the newest last commit on the folder; a ref whose time cannot be read is
    dropped from `branches` with a warning."""
    scored = []
    for candidate in list(branches):
        output = git_bytes(toplevel, "log", "-1", "--format=%ct", candidate.full_ref, "--", f"{root}/{slug}")
        try:
            scored.append((int((output or b"").strip()), candidate))
        except ValueError:
            print(f"argani: cannot read the commit time of {candidate.source} for {slug}; ignoring that branch",
                  file=sys.stderr)
            branches.remove(candidate)
    return max(scored, key=lambda pair: pair[0])[1] if scored else None  # max keeps the first of equals


def choose_source(toplevel, branch_config, root, slug, candidates):
    """(chosen candidate, reason), or (None, reason) when no candidate is usable."""
    worktree = next((c for c in candidates if c.full_ref is None), None)
    branches = [c for c in candidates if c.full_ref is not None]
    named = next((c for c in branches if c.branch_name == expected_job_branch(branch_config, slug, c)), None)
    if worktree and named and named.contents != worktree.contents:
        return named, f"the working tree copy differs from the job branch {named.source}, which holds the committed job"
    if worktree:
        return worktree, "the working tree copy"
    if named:
        return named, "the branch named like the job branch"
    newest = newest_candidate(toplevel, root, slug, branches)
    candidates[:] = [c for c in candidates if c in branches or c is worktree]
    if newest is None:
        return None, "no branch has a readable commit time"
    return newest, "the branch with the newest commit on the folder" if len(branches) > 1 else "the only branch"


def destination_status(destination, contents):
    """new when the destination holds no file, already-imported when it holds exactly the chosen
    files, else conflict."""
    existing = [p for p in destination.rglob("*") if p.is_file() or p.is_symlink()] if destination.is_dir() else []
    if not existing:
        return "new"
    same = (not any(p.is_symlink() for p in existing)
            and {p.relative_to(destination).as_posix() for p in existing} == set(contents)
            and all(p.read_bytes() == contents[p.relative_to(destination).as_posix()] for p in existing))
    return "already-imported" if same else "conflict"


def build_job(toplevel, branch_config, root, tasks, slug, candidates):
    destination = tasks / slug
    job = {"slug": slug, "status": "new", "imported": False, "source": None, "reason": None, "candidates": [],
           "files": [], "skipped": [], "destination": str(destination), "stage_after": None}
    try:
        for candidate in candidates:
            load_contents(toplevel, root, slug, candidate)
    except ImportFailure as error:
        return {**job, "status": "failed", "error": str(error), "candidates": [{"source": c.source} for c in candidates]}
    chosen, reason = choose_source(toplevel, branch_config, root, slug, candidates)
    job["candidates"] = [{"source": c.source, "differs": chosen is not None and c.contents != chosen.contents}
                         for c in candidates]
    if chosen is None:
        return {**job, "status": "failed", "error": reason}
    job.update(source=chosen.source, reason=reason, files=chosen.files, skipped=chosen.skipped)
    try:
        status = destination_status(destination, chosen.contents)
    except OSError as error:
        return {**job, "status": "failed", "error": f"cannot read {destination}: {error}"}
    job.update(status=status, imported=status == "already-imported")
    job["_contents"] = chosen.contents
    return job


def write_job_file(target, data):
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def remove_created(destination, written, directories_before):
    for target in written:
        target.unlink(missing_ok=True)
    folders = [p for p in destination.rglob("*") if p.is_dir()] + [destination]
    for folder in sorted(folders, key=lambda p: len(p.parts), reverse=True):
        if folder not in directories_before and not any(folder.iterdir()):
            folder.rmdir()


def copy_job(destination, contents):
    """Write every file under destination, then verify each against the bytes read from the source;
    remove what was written (and the folders created) on any failure."""
    destination = Path(destination)
    tasks_existed = destination.parent.exists()
    directories_before = {destination, *[p for p in destination.rglob("*") if p.is_dir()]} if destination.is_dir() else set()
    written = []
    try:
        destination.mkdir(parents=True, exist_ok=True)
        for relative, data in contents.items():
            target = destination / relative
            if not target.resolve().is_relative_to(destination.resolve()):
                raise ImportFailure(f"{relative} would be written outside {destination}")
            written.append(target)
            write_job_file(target, data)
        for relative, data in contents.items():
            if (destination / relative).read_bytes() != data:
                raise ImportFailure(f"{relative} differs from its source after the copy")
    except (OSError, ImportFailure) as error:
        remove_created(destination, written, directories_before)
        if not tasks_existed and destination.parent.is_dir() and not any(destination.parent.iterdir()):
            destination.parent.rmdir()
        raise ImportFailure(str(error)) from error


def apply_plan(jobs, config, start_dir):
    """Copy the new jobs. Returns the slugs imported in this run and the failure message, if any."""
    imported_now = []
    for job in jobs:
        if job["status"] == "new":
            try:
                copy_job(job["destination"], job["_contents"])
            except ImportFailure as error:
                kept = ", ".join(imported_now) or "nothing"
                job.update(status="failed", error=str(error))
                return imported_now, (f"Import of '{job['slug']}' failed and was rolled back: {error}. "
                                      f"Kept from this run: {kept}.")
            job.update(status="imported", imported=True)
            imported_now.append(job["slug"])
        if job["imported"]:
            try:
                job["stage_after"] = factory_state.build_state(job["slug"], start_dir, config)["stage"]
            except (ValueError, TypeError):
                job["stage_after"] = None
    return imported_now, None


def record_in_home(config, imported_now, jobs):
    """Commit the imported destinations in the argani home when it is a git repository of its own."""
    home = Path(config["home"])
    if not imported_now or not argani_home.is_own_repository(home):
        return False
    destinations = [job["destination"] for job in jobs if job["slug"] in imported_now]
    message = f"argani: import {config['project']}/{', '.join(imported_now)}"
    try:
        for command in (["add", "--", *destinations], ["commit", "-q", "-m", message, "--", *destinations]):
            subprocess.run(["git", "-C", str(home), *command], capture_output=True, check=True, timeout=30)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print(f"argani: could not record the import in {home}: {error}", file=sys.stderr)
        return False
    return True


def parse_arguments(argv):
    parser = argparse.ArgumentParser(prog="import_jobs.py", description=__doc__.splitlines()[0])
    parser.add_argument("directory", nargs="?", default=".")
    parser.add_argument("--slug", action="append", default=[])
    parser.add_argument("--artifact-root")
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv[1:])


def resolve_artifact_root(arguments, legacy_overrides):
    if arguments.artifact_root:
        return argani_config.COERCERS["artifactRoot"](arguments.artifact_root), "argument"
    if legacy_overrides and "artifactRoot" in legacy_overrides:
        return legacy_overrides["artifactRoot"], "legacy file"
    return argani_config.DEFAULTS["artifactRoot"], "default"


def main(argv):
    arguments = parse_arguments(argv)
    try:
        config = argani_config.load_config(arguments.directory, strict=True)
    except ValueError as error:
        print(f"argani: invalid config: {error}", file=sys.stderr)
        return 1
    toplevel = git_cli.toplevel(arguments.directory)
    if not config["project"] or not toplevel:
        print("This repository is not registered; run /argani:init first, then /argani:import.", file=sys.stderr)
        return 1
    legacy_overrides, warning = read_legacy_file(toplevel)
    if warning:
        print(f"argani: {warning}", file=sys.stderr)
    try:
        root, root_source = resolve_artifact_root(arguments, legacy_overrides)
    except ValueError as error:
        print(f"argani: invalid --artifact-root: {error}", file=sys.stderr)
        return 1
    branch_config = job_branch_config(config, legacy_overrides)
    tasks = argani_config.tasks_dir(config)
    found = discover(toplevel, root)
    slugs = arguments.slug or sorted(found)
    jobs = []
    for slug in slugs:
        if slug in found:
            jobs.append(build_job(toplevel, branch_config, root, tasks, slug, found[slug]))
        else:
            jobs.append({"slug": slug, "status": "missing", "imported": False, "source": None, "reason": None,
                         "candidates": [], "files": [], "skipped": [], "destination": str(tasks / slug),
                         "stage_after": None})
    imported_now, failure = apply_plan(jobs, config, arguments.directory) if arguments.apply else ([], None)
    recorded = record_in_home(config, imported_now, jobs) if arguments.apply else False
    for job in jobs:
        job.pop("_contents", None)
    print(json.dumps({"project": config["project"], "artifactRoot": root, "artifactRootSource": root_source,
                      "tasksDir": config["tasksDir"], "jobs": jobs, "applied": arguments.apply and failure is None,
                      "recorded": recorded}, indent=2))
    if failure:
        print(failure, file=sys.stderr)
    for job in jobs:
        if job["status"] == "missing":
            print(f"No legacy job found for: {job['slug']}", file=sys.stderr)
        elif job["status"] == "conflict":
            print(f"{job['slug']}: {job['destination']} holds different or extra files; not imported. "
                  "Delete or rename it by hand to import this job.", file=sys.stderr)
        elif job["status"] == "failed" and job.get("error") and not failure:
            print(f"{job['slug']}: {job['error']}", file=sys.stderr)
    return 1 if any(job["status"] in ("conflict", "missing", "failed") for job in jobs) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
