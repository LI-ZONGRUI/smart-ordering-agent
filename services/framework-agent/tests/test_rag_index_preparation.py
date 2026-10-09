"""Only synthetic contract tests in temporary directories, never genuine index preparation."""

from __future__ import annotations

import copy
import json
import socket
import stat
from pathlib import Path

import pytest

from evals.rag_benchmark import prepare_index as tool
from evals.rag_benchmark.schema import BASE, BenchmarkError, knowledge, load_index


@pytest.fixture(autouse=True)
def no_network_or_holdout(monkeypatch):
    original_text, original_bytes, original_open = Path.read_text, Path.read_bytes, Path.open

    def deny(path):
        if "holdout" in str(path).lower() and path.suffix in {".jsonl", ".json"}:
            raise AssertionError("Holdout content access forbidden")

    def text(path, *args, **kwargs):
        deny(path)
        return original_text(path, *args, **kwargs)

    def raw_bytes(path):
        deny(path)
        return original_bytes(path)

    def open_file(path, *args, **kwargs):
        deny(path)
        return original_open(path, *args, **kwargs)

    def connect(*args, **kwargs):
        raise AssertionError("network forbidden")

    monkeypatch.setattr(Path, "read_text", text)
    monkeypatch.setattr(Path, "read_bytes", raw_bytes)
    monkeypatch.setattr(Path, "open", open_file)
    monkeypatch.setattr(socket.socket, "connect", connect)


@pytest.fixture
def rows():
    hashes = tool.production_hashes()
    # Deterministic unit-test placeholders. Never installed in the real .local directory.
    return [
        dict(
            copy.deepcopy(s),
            contentHash=hashes[k],
            embedding=[(i + 1) / 100] + [0.0] * 511,
            embeddingModel=tool.MODEL,
            embeddingDimension=512,
            _id=f"unit-test-{i}",
            createTime=1,
            updateTime=2,
        )
        for i, (k, s) in enumerate(knowledge().items())
    ]


@pytest.fixture
def local(tmp_path, monkeypatch):
    directory = tmp_path / ".local"
    directory.mkdir()
    monkeypatch.setattr(tool, "LOCAL", directory)
    return directory


def write_raw(local, rows, *, jsonl=False):
    path = local / "knowledge-chunks-export.json"
    text = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) if jsonl else json.dumps(rows)
    path.write_text(text)
    return path


def prepare(local, rows):
    path = write_raw(local, rows)
    return tool.prepare(path, source_space="unit-test-only", confirm_source=True)


def test_source_audit_exact_snapshots_without_holdout():
    result = tool.audit_source()
    assert result["knowledgeCount"] == 21
    assert result["typeCounts"] == {"description": 6, "taste": 7, "ingredients": 8}
    assert result["sourceVersion"] == 1
    assert result["vectorsInspected"] is False
    assert (
        result["sourceSha256"] == "f341c287c97056b4766fd514532de31fc8a2b5cd0a3e76641283192fcd04f0a6"
    )


def test_prepare_whitelist_and_real_runner_loader(local, rows):
    result = prepare(local, rows)
    assert result["runnerLoadPassed"] is True
    loaded = load_index(local / "knowledge-index.json", local / "knowledge-index-manifest.json")
    assert len(loaded) == 21
    assert all(set(r) == set(tool.INDEX_FIELDS) for r in loaded)
    assert all("_id" not in r and "createTime" not in r for r in loaded)
    assert all(
        r["embedding"] == original["embedding"] for r, original in zip(loaded, rows, strict=True)
    )
    assert stat.S_IMODE(local.stat().st_mode) == 0o700
    assert all(stat.S_IMODE(p.stat().st_mode) == 0o600 for p in local.iterdir())
    assert result["sha256"] == tool.digest(local / "knowledge-index.json")


def test_jsonl_and_reversed_rows_map_by_identity(local, rows):
    raw = write_raw(local, list(reversed(rows)), jsonl=True)
    result = tool.prepare(raw, source_space="unit-test-only", confirm_source=True)
    assert result["runnerLoadPassed"] is True
    loaded = json.loads((local / "knowledge-index.json").read_text())
    original = {r["knowledgeId"]: r["embedding"] for r in rows}
    assert all(r["embedding"] == original[r["knowledgeId"]] for r in loaded)
    manifest = json.loads((local / "knowledge-index-manifest.json").read_text())
    assert manifest["knowledgeIds"] == list(knowledge())
    assert manifest["provenance"]["sourceExportFormat"] == "jsonl"


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("missing", "INDEX_RECORD_COUNT_INVALID"),
        ("extra", "INDEX_RECORD_COUNT_INVALID"),
        ("duplicate", "INDEX_DUPLICATE_KNOWLEDGE_ID"),
        ("unknown_id", "INDEX_KNOWLEDGE_ID_INVALID"),
        ("text", "INDEX_SOURCE_RECORD_DRIFT"),
        ("dish", "INDEX_SOURCE_RECORD_DRIFT"),
        ("category", "INDEX_SOURCE_RECORD_DRIFT"),
        ("version", "INDEX_SOURCE_RECORD_DRIFT"),
        ("verified", "INDEX_SOURCE_RECORD_DRIFT"),
        ("content_hash", "INDEX_CONTENT_HASH_MISMATCH"),
        ("old_model", "INDEX_EMBEDDING_METADATA_INVALID"),
        ("dimension_metadata", "INDEX_EMBEDDING_METADATA_INVALID"),
        ("dimension_vector", "INDEX_VECTOR_DIMENSION_INVALID"),
        ("non_array", "INDEX_VECTOR_DIMENSION_INVALID"),
        ("nan", "INDEX_VECTOR_VALUES_INVALID"),
        ("infinity", "INDEX_VECTOR_VALUES_INVALID"),
        ("boolean", "INDEX_VECTOR_VALUES_INVALID"),
        ("null", "INDEX_VECTOR_VALUES_INVALID"),
        ("big_integer", "INDEX_VECTOR_VALUES_INVALID"),
        ("zero", "INDEX_ZERO_VECTOR"),
        ("private_field", "INDEX_EXPORT_FIELDS_INVALID"),
    ],
)
def test_bad_export_never_repairs_or_generates_outputs(local, rows, mutation, code):
    if mutation == "missing":
        rows.pop()
    elif mutation == "extra":
        rows.append(copy.deepcopy(rows[0]))
    elif mutation == "duplicate":
        rows[1] = copy.deepcopy(rows[0])
    elif mutation == "unknown_id":
        rows[0]["knowledgeId"] = "unknown"
    elif mutation == "text":
        rows[0]["text"] += "unsupported extra wording"
    elif mutation == "dish":
        rows[0]["dishId"] = "dish-unknown"
    elif mutation == "category":
        rows[0]["type"] = "health"
    elif mutation == "version":
        rows[0]["sourceVersion"] = 2
    elif mutation == "verified":
        rows[0]["verified"] = False
    elif mutation == "content_hash":
        rows[0]["contentHash"] = "0" * 64
    elif mutation == "old_model":
        rows[0]["embeddingModel"] = "unverified-model"
    elif mutation == "dimension_metadata":
        rows[0]["embeddingDimension"] = 256
    elif mutation == "dimension_vector":
        rows[0]["embedding"] = [1.0] * 256
    elif mutation == "non_array":
        rows[0]["embedding"] = "not-array"
    elif mutation == "nan":
        rows[0]["embedding"][0] = float("nan")
    elif mutation == "infinity":
        rows[0]["embedding"][0] = float("inf")
    elif mutation == "boolean":
        rows[0]["embedding"][0] = True
    elif mutation == "null":
        rows[0]["embedding"][0] = None
    elif mutation == "big_integer":
        rows[0]["embedding"][0] = 10**1000
    elif mutation == "zero":
        rows[0]["embedding"] = [0.0] * 512
    else:
        rows[0]["customerData"] = "not-allowed"
    with pytest.raises(BenchmarkError, match=code):
        tool.validate_records(rows)
    assert not (local / "knowledge-index.json").exists()
    assert not (local / "knowledge-index-manifest.json").exists()


def test_source_confirmation_required(local, rows):
    raw = write_raw(local, rows)
    with pytest.raises(BenchmarkError, match="SOURCE_CONFIRMATION"):
        tool.prepare(raw, source_space="unit-test-only", confirm_source=False)
    assert not (local / "knowledge-index.json").exists()


def test_external_or_symlink_escape_rejected(local, rows, tmp_path):
    external = tmp_path / "external.json"
    external.write_text(json.dumps(rows))
    for path in (external, local / "symlink.json"):
        if path != external:
            path.symlink_to(external)
        with pytest.raises(BenchmarkError, match="LOCAL_PATH_INVALID"):
            tool.prepare(path, source_space="unit-test-only", confirm_source=True)


def test_existing_output_not_overwritten(local, rows):
    path = local / "knowledge-index.json"
    path.write_text("historical-local-snapshot")
    with pytest.raises(BenchmarkError, match="OUTPUT_ALREADY_EXISTS"):
        prepare(local, rows)
    assert path.read_text() == "historical-local-snapshot"


def test_partial_file_install_rolled_back(local, rows, monkeypatch):
    original = tool.os.link

    def fail_second(source, target):
        if target.name == "knowledge-index-manifest.json":
            raise OSError("private-path-not-to-return")
        return original(source, target)

    monkeypatch.setattr(tool.os, "link", fail_second)
    with pytest.raises(OSError):
        prepare(local, rows)
    assert {p.name for p in local.iterdir()} == {"knowledge-chunks-export.json"}


@pytest.mark.parametrize(
    "mutation", ["count", "ids", "version", "index_hash", "snapshot_hash", "raw_hash"]
)
def test_manifest_corruption_rejected(local, rows, mutation):
    prepare(local, rows)
    path = local / "knowledge-index-manifest.json"
    manifest = json.loads(path.read_text())
    if mutation == "count":
        manifest["recordCount"] = 20
    elif mutation == "ids":
        manifest["knowledgeIds"] = manifest["knowledgeIds"][::-1]
    elif mutation == "version":
        manifest["sourceVersion"] = 2
    elif mutation == "index_hash":
        manifest["sha256"] = "0" * 64
    elif mutation == "snapshot_hash":
        manifest["sourceSha256"] = "0" * 64
    else:
        manifest["provenance"]["sourceExportSha256"] = "0" * 64
    path.write_text(json.dumps(manifest))
    with pytest.raises(BenchmarkError):
        tool.check()


def test_public_permissions_detected(local, rows):
    prepare(local, rows)
    (local / "knowledge-index.json").chmod(0o644)
    with pytest.raises(BenchmarkError, match="FILE_PERMISSIONS_INVALID"):
        tool.check()


def test_raw_export_corruption_detected(local, rows):
    prepare(local, rows)
    (local / "knowledge-chunks-export.json").write_text("[]")
    with pytest.raises(BenchmarkError, match="RAW_EXPORT_HASH_MISMATCH"):
        tool.check()


@pytest.mark.parametrize("raw", ['[{"knowledgeId":"a","knowledgeId":"b"}]', "[NaN]", "[Infinity]"])
def test_invalid_json_rejected(local, raw):
    path = local / "knowledge-chunks-export.json"
    path.write_text(raw)
    with pytest.raises(BenchmarkError):
        tool.read_export(path)


def test_no_real_export_means_no_manifest(local, capsys):
    assert tool.main(["check"]) == 2
    assert "INDEX_LOCAL_FILE_MISSING" in capsys.readouterr().out
    assert not list(local.iterdir())


def test_error_does_not_print_raw_input_or_secrets(local, capsys):
    path = local / "knowledge-chunks-export.json"
    path.write_text("private-raw-marker")
    assert (
        tool.main(
            [
                "prepare",
                "--input",
                str(path),
                "--source-space",
                "unit-test-only",
                "--confirm-source",
            ]
        )
        == 2
    )
    output = capsys.readouterr().out
    assert "private-raw-marker" not in output
    assert str(local) not in output


def test_fixture_byte_copy_stays_frozen():
    # No dataset is opened, including the new RAG Holdout.
    assert (
        tool.digest(BASE / "fixtures/knowledge.json")
        == "f341c287c97056b4766fd514532de31fc8a2b5cd0a3e76641283192fcd04f0a6"
    )


def test_manifest_time_is_preparation_time_not_claimed_cloud_time(local, rows):
    prepare(local, rows)
    path = local / "knowledge-index-manifest.json"
    manifest = json.loads(path.read_text())
    assert "exportedAt" not in manifest["provenance"]
    assert "preparedAt" in manifest["provenance"]
    manifest["provenance"]["preparedAt"] = "unknown"
    path.write_text(json.dumps(manifest))
    with pytest.raises(BenchmarkError, match="PROVENANCE_INVALID"):
        tool.check()
