"""Offline-only preparation of a user-supplied knowledge_chunks export. No model or DB clients."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import stat
import subprocess
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.rag_benchmark.schema import (
    BASE,
    MANIFEST,
    MANIFEST_SHA256,
    ROOT,
    BenchmarkError,
    digest,
    knowledge,
    load_index,
)

LOCAL = BASE / ".local"
MODEL = "qwen3.7-text-embedding-flash"
DIMENSION = 512
SOURCE_FIELDS = (
    "knowledgeId",
    "scope",
    "dishId",
    "type",
    "title",
    "text",
    "sourceType",
    "sourceFields",
    "sourceVersion",
    "verified",
)
INDEX_FIELDS = SOURCE_FIELDS + ("contentHash", "embedding", "embeddingModel", "embeddingDimension")
DATABASE_ONLY = {"_id", "createTime", "updateTime"}
MAX_BYTES = 8 * 1024 * 1024


def fail(code: str) -> None:
    raise BenchmarkError(code)


def strict_json(text: str) -> Any:
    def bad_constant(value):
        fail("INDEX_NONFINITE_JSON")

    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                fail("INDEX_DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    return json.loads(text, parse_constant=bad_constant, object_pairs_hook=unique_keys)


def local_path(path: Path, *, existing: bool = True) -> Path:
    if LOCAL.is_symlink():
        fail("INDEX_LOCAL_PATH_INVALID")
    target = path.resolve()
    if not target.is_relative_to(LOCAL.resolve()):
        fail("INDEX_LOCAL_PATH_INVALID")
    if existing and not target.is_file():
        fail("INDEX_LOCAL_FILE_MISSING")
    if existing and target.stat().st_size > MAX_BYTES:
        fail("INDEX_INPUT_TOO_LARGE")
    return target


def read_export(path: Path) -> tuple[list[dict[str, Any]], str]:
    raw = local_path(path).read_text(encoding="utf-8-sig")
    try:
        rows = strict_json(raw)
    except json.JSONDecodeError:
        rows = [strict_json(line) for line in raw.splitlines() if line.strip()]
        format_name = "jsonl"
    else:
        format_name = "json-array"
    if not isinstance(rows, list):
        fail("INDEX_EXPORT_FORMAT_INVALID")
    return rows, format_name


def production_hashes() -> dict[str, str]:
    # The helper imports only local pure source/hash functions; no execution of the indexer.
    child = subprocess.run(
        ["node", str(BASE / "index_source_hashes.cjs")],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if child.returncode != 0:
        fail("INDEX_SOURCE_AUDIT_FAILED")
    result = strict_json(child.stdout)
    if (
        not isinstance(result, dict)
        or set(result) != set(knowledge())
        or any(
            not isinstance(v, str) or re.fullmatch(r"[a-f0-9]{64}", v) is None
            for v in result.values()
        )
    ):
        fail("INDEX_SOURCE_AUDIT_FAILED")
    return result


def audit_source() -> dict[str, Any]:
    """Compare source/deployment/benchmark bytes, without opening either dataset split."""
    if digest(MANIFEST) != MANIFEST_SHA256:
        fail("INDEX_BENCHMARK_MANIFEST_CHANGED")
    manifest = strict_json(MANIFEST.read_text())
    source_path = ROOT / "docs/rag/knowledge-source.json"
    deployment = ROOT / "uniCloud-aliyun/cloudfunctions/rag/resources/knowledge-source.json"
    frozen = BASE / "fixtures/knowledge.json"
    checksum = digest(frozen)
    if any(digest(p) != checksum for p in (source_path, deployment)) or (
        checksum != manifest["sourceSha256"]
        or checksum != manifest["sha256"]["fixtures/knowledge.json"]
        or digest(BASE / "fixtures/dishes.json") != manifest["sha256"]["fixtures/dishes.json"]
    ):
        fail("INDEX_KNOWLEDGE_SNAPSHOT_DRIFT")
    source = knowledge()
    dishes = strict_json((BASE / "fixtures/dishes.json").read_text())
    dish_ids = {d["_id"] for d in dishes}
    counts = dict(Counter(s["type"] for s in source.values()))
    if counts != {"description": 6, "taste": 7, "ingredients": 8} or any(
        s["type"] not in counts
        or s["scope"] not in {"dish", "restaurant"}
        or (s["dishId"] not in dish_ids if s["scope"] == "dish" else s["dishId"] is not None)
        or type(s["sourceVersion"]) is not int
        or s["sourceVersion"] != 1
        for s in source.values()
    ):
        fail("INDEX_SOURCE_METADATA_INVALID")
    production_hashes()  # Also verifies the production resource manifest via loadSources().
    return {
        "errCode": 0,
        "knowledgeCount": len(source),
        "typeCounts": counts,
        "sourceVersion": 1,
        "sourceSha256": checksum,
        "embeddingModel": MODEL,
        "embeddingDimension": DIMENSION,
        "vectorsInspected": False,
    }


def validate_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source = knowledge()
    hashes = production_hashes()
    if len(rows) != 21:
        fail("INDEX_RECORD_COUNT_INVALID")
    by_id = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) - set(INDEX_FIELDS) - DATABASE_ONLY:
            fail("INDEX_EXPORT_FIELDS_INVALID")
        kid = row.get("knowledgeId")
        if not isinstance(kid, str) or kid not in source:
            fail("INDEX_KNOWLEDGE_ID_INVALID")
        if kid in by_id:
            fail("INDEX_DUPLICATE_KNOWLEDGE_ID")
        if any(row.get(k) != source[kid][k] for k in SOURCE_FIELDS) or (
            type(row.get("sourceVersion")) is not int or row.get("verified") is not True
        ):
            fail("INDEX_SOURCE_RECORD_DRIFT")
        if row.get("contentHash") != hashes[kid]:
            fail("INDEX_CONTENT_HASH_MISMATCH")
        if row.get("embeddingModel") != MODEL or (
            type(row.get("embeddingDimension")) is not int or row["embeddingDimension"] != DIMENSION
        ):
            fail("INDEX_EMBEDDING_METADATA_INVALID")
        vector = row.get("embedding")
        if not isinstance(vector, list) or len(vector) != DIMENSION:
            fail("INDEX_VECTOR_DIMENSION_INVALID")
        try:
            finite = all(type(x) in {int, float} and math.isfinite(x) for x in vector)
        except OverflowError:
            finite = False
        if not finite:
            fail("INDEX_VECTOR_VALUES_INVALID")
        if not any(vector):
            fail("INDEX_ZERO_VECTOR")
        # Preserve the supplied knowledge/vector pair; never repair or regenerate.
        by_id[kid] = {k: row[k] for k in INDEX_FIELDS}
    if set(by_id) != set(source):
        fail("INDEX_KNOWLEDGE_IDS_INCOMPLETE")
    return [by_id[kid] for kid in source]  # Map by identity, not input array position.


def private_directory() -> None:
    if LOCAL.is_symlink():
        fail("INDEX_LOCAL_PATH_INVALID")
    LOCAL.mkdir(mode=0o700, parents=True, exist_ok=True)
    LOCAL.chmod(0o700)


def temporary_file(data: bytes) -> Path:
    fd, name = tempfile.mkstemp(prefix=".index-", dir=LOCAL)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(data)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise
    return Path(name)  # mkstemp uses 0600; no transient public vector file.


def prepare(raw_path: Path, *, source_space: str, confirm_source: bool) -> dict[str, Any]:
    if not confirm_source:
        fail("INDEX_SOURCE_CONFIRMATION_REQUIRED")
    if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", source_space) is None:
        fail("INDEX_SOURCE_SPACE_INVALID")
    audit_source()
    raw_path = local_path(raw_path)
    rows, export_format = read_export(raw_path)
    normalized = validate_records(rows)
    data_path, manifest_path = (
        LOCAL / "knowledge-index.json",
        LOCAL / "knowledge-index-manifest.json",
    )
    if data_path.exists() or manifest_path.exists():
        fail("INDEX_OUTPUT_ALREADY_EXISTS")
    private_directory()
    raw_path.chmod(0o600)
    staged = []
    installed = []
    try:
        data = (
            json.dumps(normalized, ensure_ascii=False, indent=2, allow_nan=False).encode() + b"\n"
        )
        temp_data = temporary_file(data)
        staged.append(temp_data)
        manifest = {
            "origin": "unicloud-knowledge_chunks-export",
            "sha256": digest(temp_data),
            "sourceSha256": digest(BASE / "fixtures/knowledge.json"),
            "embeddingModel": MODEL,
            "embeddingDimension": DIMENSION,
            "recordCount": len(normalized),
            "knowledgeIds": [r["knowledgeId"] for r in normalized],
            "sourceVersion": 1,
            "provenance": {
                "collection": "knowledge_chunks",
                "sourceSpace": source_space,
                "sourceExportFile": raw_path.relative_to(LOCAL.resolve()).as_posix(),
                "sourceExportSha256": digest(raw_path),
                "sourceExportFormat": export_format,
                "preparedAt": datetime.now(UTC).isoformat(),
                "sourceAttestation": "user-confirmed-console-export-not-provider-proof",
            },
        }
        temp_manifest = temporary_file(json.dumps(manifest, indent=2).encode() + b"\n")
        staged.append(temp_manifest)
        # Use the actual existing runner loader before publishing either output.
        load_index(temp_data, temp_manifest)
        for temp, target in ((temp_data, data_path), (temp_manifest, manifest_path)):
            os.link(temp, target)  # Exclusive install: never overwrite a previous index.
            installed.append(target)
        result = check()
    except BaseException:
        for path in installed:
            path.unlink(missing_ok=True)
        raise
    finally:
        for path in staged:
            path.unlink(missing_ok=True)
    return result


def check() -> dict[str, Any]:
    audit_source()
    data_path = local_path(LOCAL / "knowledge-index.json")
    manifest_path = local_path(LOCAL / "knowledge-index-manifest.json")
    manifest = strict_json(manifest_path.read_text())
    rows = validate_records(load_index(data_path, manifest_path))
    if (
        not isinstance(manifest, dict)
        or manifest.get("recordCount") != len(rows)
        or (
            manifest.get("knowledgeIds") != [r["knowledgeId"] for r in rows]
            or type(manifest.get("sourceVersion")) is not int
            or manifest["sourceVersion"] != 1
        )
    ):
        fail("INDEX_MANIFEST_METADATA_INVALID")
    if set(manifest) != {
        "origin",
        "sha256",
        "sourceSha256",
        "embeddingModel",
        "embeddingDimension",
        "recordCount",
        "knowledgeIds",
        "sourceVersion",
        "provenance",
    }:
        fail("INDEX_MANIFEST_METADATA_INVALID")
    provenance = manifest.get("provenance")
    if (
        not isinstance(provenance, dict)
        or set(provenance)
        != {
            "collection",
            "sourceSpace",
            "sourceExportFile",
            "sourceExportSha256",
            "sourceExportFormat",
            "preparedAt",
            "sourceAttestation",
        }
        or provenance.get("collection") != "knowledge_chunks"
        or (
            provenance.get("sourceAttestation")
            != "user-confirmed-console-export-not-provider-proof"
            or not isinstance(provenance.get("sourceSpace"), str)
            or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", provenance["sourceSpace"]) is None
            or not isinstance(provenance.get("sourceExportFile"), str)
        )
    ):
        fail("INDEX_PROVENANCE_INVALID")
    try:
        prepared_at = datetime.fromisoformat(provenance["preparedAt"])
        if prepared_at.tzinfo is None:
            fail("INDEX_PROVENANCE_INVALID")
    except (TypeError, ValueError):
        fail("INDEX_PROVENANCE_INVALID")
    raw = local_path(LOCAL / provenance["sourceExportFile"])
    if digest(raw) != provenance.get("sourceExportSha256"):
        fail("INDEX_RAW_EXPORT_HASH_MISMATCH")
    raw_rows, export_format = read_export(raw)
    if validate_records(raw_rows) != rows or export_format != provenance.get("sourceExportFormat"):
        fail("INDEX_RAW_EXPORT_CORRESPONDENCE_INVALID")
    if stat.S_IMODE(LOCAL.stat().st_mode) & 0o077 or any(
        stat.S_IMODE(p.stat().st_mode) & 0o077 for p in (raw, data_path, manifest_path)
    ):
        fail("INDEX_FILE_PERMISSIONS_INVALID")
    return {
        "errCode": 0,
        "recordCount": len(rows),
        "embeddingModel": MODEL,
        "embeddingDimension": DIMENSION,
        "sourceVersion": 1,
        "sha256": digest(data_path),
        "sourceSha256": manifest["sourceSha256"],
        "rawExportSha256": digest(raw),
        "runnerLoadPassed": True,
        "sourceAuthenticity": "user-attested-not-remotely-verified",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    sub.add_parser("audit-source")
    sub.add_parser("check")
    command = sub.add_parser("prepare")
    command.add_argument("--input", type=Path, required=True)
    command.add_argument("--source-space", required=True)
    command.add_argument("--confirm-source", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.operation == "audit-source":
            result = audit_source()
        elif args.operation == "check":
            result = check()
        else:
            result = prepare(
                args.input, source_space=args.source_space, confirm_source=args.confirm_source
            )
    except BenchmarkError as error:
        # All own error messages are fixed codes. Upstream loader messages contain no input values.
        own = str(error)
        code = own if re.fullmatch(r"INDEX_[A-Z_]+", own) else "INDEX_RUNNER_CONTRACT_INVALID"
        print(json.dumps({"errCode": code}))
        return 2
    except (OSError, ValueError, TypeError, OverflowError, subprocess.SubprocessError):
        print(json.dumps({"errCode": "INDEX_LOCAL_PREPARATION_FAILED"}))
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
