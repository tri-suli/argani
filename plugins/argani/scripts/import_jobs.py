#!/usr/bin/env python3
"""Move the legacy job folders of a registered project to the project's task folder in the argani home.

Usage: python3 import_jobs.py [dir] [--slug <slug> ...] [--artifact-root <folder>] [--apply]

Before the board, a project kept its jobs at <project root>/<artifactRoot>/<slug>/ (artifactRoot from
.claude/argani.json, default 'argani'). This script finds those folders in the working tree and
copies them to <home>/projects/<name>/tasks/<slug>/. Without --apply it only prints the plan.

Only the working tree is read: a job that lives only on a branch must be checked out first (with the
project's own tools), then imported. Symbolic links are never followed or copied; they are listed
under `skipped`.

A destination that already holds exactly the found files is `already-imported` (nothing to do). A
destination with different or extra files is a `conflict` and is never written.

Prints the plan as JSON (project, artifactRoot, artifactRootSource, tasksDir, jobs, applied). The
project is never modified and nothing in it is deleted. Each job has a status: new (dry run),
imported, already-imported, conflict, missing (requested slug not found) or failed (a copy or a read
failed; what was written for that slug is removed again, earlier imports stay).
Exit 1 with a message when the directory is not registered or any job is a conflict, missing or
failed.
"""
import argparse
import json
import os
import sys
from pathlib import Path

import argani_config
import factory_state

LEGACY_CONFIG = Path(".claude") / "argani.json"
DEFAULT_ARTIFACT_ROOT = "argani"  # the artifactRoot every legacy project had without its own setting
INTENT_FILE = "intent.md"
WORKING_TREE = "working tree"


class ImportFailure(Exception):
    """A read or a copy that failed; carries the message for the human."""


def read_legacy_file(project_root):
    """(validated overrides, warning) of the legacy .claude/argani.json; (None, None) when absent."""
    path = Path(project_root) / LEGACY_CONFIG
    if not path.is_file():
        return None, None
    try:
        return argani_config.read_legacy_file(path), None
    except ValueError as error:
        return None, f"ignoring the legacy config, using defaults: {error}"


def discover(project_root, root):
    """slug -> (copyable relative paths, skipped relative paths) of the job folders under
    <project_root>/<root>; a folder without intent.md is not a job. Symbolic links are skipped."""
    base = Path(project_root) / root
    found = {}
    if not base.is_dir() or base.is_symlink():
        return found
    for slug_dir in sorted(base.iterdir()):
        if not (slug_dir.is_dir() and not slug_dir.is_symlink() and argani_config.SLUG_PATTERN.fullmatch(slug_dir.name)):
            continue
        files, skipped = [], []
        for folder, subfolders, names in os.walk(slug_dir):
            for name in [*subfolders, *names]:
                path = Path(folder) / name
                relative = path.relative_to(slug_dir).as_posix()
                if path.is_symlink():
                    skipped.append(relative)
                elif path.is_file():
                    files.append(relative)
            subfolders[:] = [name for name in subfolders if not (Path(folder) / name).is_symlink()]
        if INTENT_FILE in files:
            found[slug_dir.name] = (sorted(files), sorted(skipped))
    return found


def read_contents(project_root, root, slug, files):
    contents = {}
    for relative in files:
        try:
            contents[relative] = (Path(project_root) / root / slug / relative).read_bytes()
        except OSError as error:
            raise ImportFailure(f"cannot read {relative}: {error}") from error
    return contents


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


def build_job(project_root, root, tasks, slug, files, skipped):
    destination = tasks / slug
    job = {"slug": slug, "status": "new", "imported": False, "source": WORKING_TREE, "files": files,
           "skipped": skipped, "destination": str(destination), "stage_after": None}
    try:
        contents = read_contents(project_root, root, slug, files)
        status = destination_status(destination, contents)
    except (ImportFailure, OSError) as error:
        return {**job, "status": "failed", "error": str(error)}
    job.update(status=status, imported=status == "already-imported")
    job["_contents"] = contents
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


def parse_arguments(argv):
    parser = argparse.ArgumentParser(prog="import_jobs.py", description=__doc__.splitlines()[0])
    parser.add_argument("directory", nargs="?", default=".")
    parser.add_argument("--slug", action="append", default=[])
    parser.add_argument("--artifact-root")
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv[1:])


def resolve_artifact_root(arguments, legacy_overrides):
    if arguments.artifact_root:
        return argani_config.LEGACY_COERCERS["artifactRoot"](arguments.artifact_root), "argument"
    if legacy_overrides and "artifactRoot" in legacy_overrides:
        return legacy_overrides["artifactRoot"], "legacy file"
    return DEFAULT_ARTIFACT_ROOT, "default"


def main(argv):
    arguments = parse_arguments(argv)
    try:
        config = argani_config.load_config(arguments.directory, strict=True)
    except ValueError as error:
        print(f"argani: invalid config: {error}", file=sys.stderr)
        return 1
    project_root = config["projectRoot"]
    if not config["project"] or not project_root:
        print("This directory is not registered; run /argani:init first, then /argani:import.", file=sys.stderr)
        return 1
    legacy_overrides, warning = read_legacy_file(project_root)
    if warning:
        print(f"argani: {warning}", file=sys.stderr)
    try:
        root, root_source = resolve_artifact_root(arguments, legacy_overrides)
    except ValueError as error:
        print(f"argani: invalid --artifact-root: {error}", file=sys.stderr)
        return 1
    tasks = argani_config.tasks_dir(config)
    found = discover(project_root, root)
    slugs = arguments.slug or sorted(found)
    jobs = []
    for slug in slugs:
        if slug in found:
            jobs.append(build_job(project_root, root, tasks, slug, *found[slug]))
        else:
            jobs.append({"slug": slug, "status": "missing", "imported": False, "source": None, "files": [],
                         "skipped": [], "destination": str(tasks / slug), "stage_after": None})
    imported_now, failure = apply_plan(jobs, config, arguments.directory) if arguments.apply else ([], None)
    for job in jobs:
        job.pop("_contents", None)
    print(json.dumps({"project": config["project"], "artifactRoot": root, "artifactRootSource": root_source,
                      "tasksDir": config["tasksDir"], "jobs": jobs, "applied": arguments.apply and failure is None},
                     indent=2))
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
