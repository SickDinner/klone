from pathlib import Path
import subprocess
import sys

root = Path.cwd()
schemas_path = root / "src" / "klone" / "schemas.py"
memory_path = root / "src" / "klone" / "memory.py"
test_path = root / "tests" / "test_memory_phase_2c1.py"

for path in (schemas_path, memory_path, test_path):
    if not path.exists():
        raise SystemExit(f"Required file not found: {path}")

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")

def patch_class(text: str, class_name: str) -> str:
    start = text.index(f"class {class_name}(BaseModel):")
    next_class = text.find("\n\nclass ", start + 1)
    if next_class == -1:
        next_class = len(text)
    block = text[start:next_class]
    if "provenance_summary:" in block:
        return text

    old = (
        "    metadata: dict[str, Any] | None = None\n"
        "    created_at: str\n"
        "    updated_at: str"
    )
    new = (
        '    metadata: dict[str, Any] | None = None\n'
        '    provenance_summary: "MemoryProvenanceSummaryRecord | None" = None\n'
        "    created_at: str\n"
        "    updated_at: str"
    )
    if old not in block:
        raise RuntimeError(f"Could not patch {class_name} block")

    block = block.replace(old, new, 1)
    return text[:start] + block + text[next_class:]

schemas = read(schemas_path)
schemas = patch_class(schemas, "MemoryEventRecord")
schemas = patch_class(schemas, "MemoryEpisodeRecord")
write(schemas_path, schemas)

memory = read(memory_path)

helper = '''
    def _attach_provenance_summary(
        self,
        *,
        room_id: str,
        owner_type: str,
        owner_id: str,
        payload: dict[str, Any],
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        hydrated = dict(payload)
        provenance = self.repository.list_memory_provenance(
            room_id=room_id,
            owner_type=owner_type,
            owner_id=owner_id,
            conn=conn,
        )
        hydrated["provenance_summary"] = self._build_provenance_summary(provenance)
        return hydrated
'''.strip("\n")

old_query_events = '''
    def query_events(
        self,
        *,
        room_id: str,
        limit: int,
        offset: int,
        status: str | None = None,
        event_type: str | None = None,
        ingest_run_id: int | None = None,
        include_corrected: bool = True,
    ) -> list[dict[str, Any]]:
        self._require_room(room_id)
        return [
            _decode_row_metadata(row)
            for row in self.repository.list_memory_events(
                room_id=room_id,
                limit=limit,
                offset=offset,
                status=status,
                event_type=event_type,
                ingest_run_id=ingest_run_id,
                include_corrected=include_corrected,
            )
        ]
'''.strip("\n")

new_query_events = '''
    def query_events(
        self,
        *,
        room_id: str,
        limit: int,
        offset: int,
        status: str | None = None,
        event_type: str | None = None,
        ingest_run_id: int | None = None,
        include_corrected: bool = True,
    ) -> list[dict[str, Any]]:
        self._require_room(room_id)
        rows = self.repository.list_memory_events(
            room_id=room_id,
            limit=limit,
            offset=offset,
            status=status,
            event_type=event_type,
            ingest_run_id=ingest_run_id,
            include_corrected=include_corrected,
        )
        return [
            self._attach_provenance_summary(
                room_id=room_id,
                owner_type="event",
                owner_id=str(row["id"]),
                payload=_decode_row_metadata(row),
            )
            for row in rows
        ]
'''.strip("\n")

old_query_episodes = '''
    def query_episodes(
        self,
        *,
        room_id: str,
        limit: int,
        offset: int,
        status: str | None = None,
        episode_type: str | None = None,
        ingest_run_id: int | None = None,
        include_corrected: bool = True,
    ) -> list[dict[str, Any]]:
        self._require_room(room_id)
        return [
            _decode_row_metadata(row)
            for row in self.repository.list_memory_episodes(
                room_id=room_id,
                limit=limit,
                offset=offset,
                status=status,
                episode_type=episode_type,
                ingest_run_id=ingest_run_id,
                include_corrected=include_corrected,
            )
        ]
'''.strip("\n")

new_query_episodes = '''
    def query_episodes(
        self,
        *,
        room_id: str,
        limit: int,
        offset: int,
        status: str | None = None,
        episode_type: str | None = None,
        ingest_run_id: int | None = None,
        include_corrected: bool = True,
    ) -> list[dict[str, Any]]:
        self._require_room(room_id)
        rows = self.repository.list_memory_episodes(
            room_id=room_id,
            limit=limit,
            offset=offset,
            status=status,
            episode_type=episode_type,
            ingest_run_id=ingest_run_id,
            include_corrected=include_corrected,
        )
        return [
            self._attach_provenance_summary(
                room_id=room_id,
                owner_type="episode",
                owner_id=row["id"],
                payload=_decode_row_metadata(row),
            )
            for row in rows
        ]
'''.strip("\n")

if "def _attach_provenance_summary(" not in memory:
    if old_query_events not in memory:
        raise RuntimeError("Could not locate clean query_events block in memory.py")
    memory = memory.replace(old_query_events, helper + "\n\n" + old_query_events, 1)

if old_query_events not in memory:
    raise RuntimeError("query_events block did not match expected clean source")
memory = memory.replace(old_query_events, new_query_events, 1)

if old_query_episodes not in memory:
    raise RuntimeError("query_episodes block did not match expected clean source")
memory = memory.replace(old_query_episodes, new_query_episodes, 1)

write(memory_path, memory)

test_text = read(test_path)

if "def test_query_results_expose_provenance_summary(self) -> None:" not in test_text:
    new_test = '''
    def test_query_results_expose_provenance_summary(self) -> None:
        result = self._ingest_dataset(
            label="Query Provenance Summary",
            classification_level="personal",
            folder_name="query_provenance_summary",
            files={"note.txt": "alpha"},
        )

        room_id = "restricted-room"
        run_id = result["run"]["id"]
        episode_id = system_ingest_episode_id(room_id=room_id, ingest_run_id=run_id)

        event_rows = memory_events(
            room_id=room_id,
            repository=self.repository,
            limit=50,
            offset=0,
            status=None,
            event_type=None,
            ingest_run_id=run_id,
            include_corrected=True,
        )
        self.assertTrue(event_rows)
        started_event = next(row for row in event_rows if row.event_type == "ingest_started")
        self.assertIsNotNone(started_event.provenance_summary)
        self.assertGreater(started_event.provenance_summary.total_count, 0)
        self.assertGreater(started_event.provenance_summary.source_lineage_count, 0)

        episode_rows = memory_episodes(
            room_id=room_id,
            repository=self.repository,
            limit=50,
            offset=0,
            status=None,
            episode_type=None,
            ingest_run_id=run_id,
            include_corrected=True,
        )
        self.assertTrue(episode_rows)
        episode_row = next(row for row in episode_rows if row.id == episode_id)
        self.assertIsNotNone(episode_row.provenance_summary)
        self.assertGreater(episode_row.provenance_summary.total_count, 0)
        self.assertGreater(episode_row.provenance_summary.source_lineage_count, 0)
    '''.strip("\n")

    needle = "    def test_room_isolation_for_queries_and_traversal(self) -> None:"
    if needle not in test_text:
        raise RuntimeError("Could not locate insertion point in tests/test_memory_phase_2c1.py")
    test_text = test_text.replace(needle, new_test + "\n\n" + needle, 1)
    write(test_path, test_text)

def run(cmd):
    print(">", " ".join(cmd))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise SystemExit(result.returncode)

python_exe = root / ".venv" / "Scripts" / "python.exe"
python_cmd = str(python_exe) if python_exe.exists() else sys.executable

print("\n=== DIFF ===")
run(["git", "diff", "--", "src/klone/schemas.py", "src/klone/memory.py", "tests/test_memory_phase_2c1.py"])

print("\n=== RUN TESTS ===")
run([python_cmd, "-m", "unittest", "tests.test_memory_phase_2c1", "-v"])

print("\n=== REPO STATE ===")
run(["git", "status", "--short"])

run(["git", "add", "src/klone/schemas.py", "src/klone/memory.py", "tests/test_memory_phase_2c1.py"])
run(["git", "commit", "-m", "feat(memory): expose provenance summary on query results"])
run(["git", "push"])

print("\nPatch applied, tested, committed, and pushed.")
