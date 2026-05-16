"""Session digest — convert raw kiro-cli JSONL into structured YAML for analysis."""

import json
from datetime import UTC, datetime
from pathlib import Path

import yaml

from agent_kit.config import load_config


class _LiteralStr(str):
    """String subclass that YAML dumps as a block scalar."""


def _literal_representer(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


yaml.add_representer(_LiteralStr, _literal_representer)


def _block(text: str) -> str | _LiteralStr:
    """Return a LiteralStr (block scalar) if text is multi-line, plain str otherwise."""
    if "\n" not in text:
        return text
    return _LiteralStr("\n".join(line.rstrip() for line in text.split("\n")))


class DigestClient:
    """Processes kiro-cli session files into compact structured YAML."""

    def __init__(self, sessions_dir: Path, output_dir: Path, sqlite_path: Path | None = None):
        self._sessions_dir = sessions_dir
        self._output_dir = output_dir
        self._sqlite_path = sqlite_path
        self._config: dict | None = None

    # --- Public interface ---

    def digest_all(self, *, since: int | None = None) -> dict:
        """Process all sessions. Returns summary dict with processed/skipped/errors counts."""
        self._output_dir.mkdir(parents=True, exist_ok=True)
        processed, skipped, errors = 0, 0, 0

        # File-based sessions
        for json_path in sorted(self._sessions_dir.glob("*.json")):
            jsonl_path = json_path.with_suffix(".jsonl")
            if not jsonl_path.exists():
                continue

            meta = self._load_meta(json_path)
            if not meta:
                continue

            if not self._should_process(meta):
                skipped += 1
                continue

            if since and self._updated_at_ms(meta) <= since:
                skipped += 1
                continue

            output_path = self._output_path(meta)
            if self._is_fresh(jsonl_path, output_path):
                skipped += 1
                continue

            try:
                self._digest_session(meta, jsonl_path, output_path)
                processed += 1
            except Exception as e:
                errors += 1
                import sys

                print(f"  Error processing {json_path.stem}: {e}", file=sys.stderr)

        # SQLite sessions
        if self._sqlite_path and self._sqlite_path.exists():
            p, s, e = self._digest_sqlite(since=since)
            processed += p
            skipped += s
            errors += e

        return {"processed": processed, "skipped": skipped, "errors": errors}

    def digest_session(self, session_id: str) -> Path:
        """Process a specific session. Returns output path."""
        self._output_dir.mkdir(parents=True, exist_ok=True)
        json_path = self._sessions_dir / f"{session_id}.json"
        jsonl_path = self._sessions_dir / f"{session_id}.jsonl"

        if not json_path.exists():
            raise ValueError(f"session not found: {session_id}")
        if not jsonl_path.exists():
            raise ValueError(f"no conversation data for session: {session_id}")

        meta = self._load_meta(json_path)
        if not meta:
            raise ValueError(f"invalid session metadata: {session_id}")

        output_path = self._output_path(meta)
        self._digest_session(meta, jsonl_path, output_path)
        return output_path

    # --- Private implementation ---

    def _digest_session(self, meta: dict, jsonl_path: Path, output_path: Path) -> None:
        """Parse a session JSONL and write the digested YAML."""
        entries = self._read_jsonl(jsonl_path)
        turns = self._parse_turns(entries)

        if not turns:
            return

        result = {
            "session_id": meta.get("session_id", ""),
            "project": self._resolve_project(meta.get("cwd", "")),
            "started": self._format_iso(meta.get("created_at", "")),
            "ended": self._format_iso(meta.get("updated_at", "")),
            "turns": turns,
        }

        output_path.write_text(
            yaml.dump(
                result, default_flow_style=False, sort_keys=False, allow_unicode=True, width=9999
            )
        )

    def _parse_turns(self, entries: list[dict]) -> list[dict]:
        """Split JSONL entries into turns, grouped by Prompt boundaries."""
        turns = []
        current_turn: dict | None = None
        tool_results: dict[str, dict] = {}  # toolUseId → result data

        for entry in entries:
            kind = entry.get("kind")
            data = entry.get("data", {})

            if kind == "Prompt":
                if current_turn:
                    self._finalize_turn(current_turn, tool_results)
                    turns.append(current_turn)
                user_text = self._extract_text(data)
                current_turn = {
                    "prompt_id": data.get("message_id", ""),
                    "when": self._format_timestamp(data.get("meta", {}).get("timestamp")),
                    "user": _block(user_text),
                    "assistant": "",
                    "tools": [],
                    "_pending_tools": [],
                }
                tool_results = {}

            elif kind == "AssistantMessage" and current_turn is not None:
                content = data.get("content", [])
                text_parts = []
                for item in content:
                    if isinstance(item, dict):
                        if item.get("kind") == "text":
                            text = item.get("data", "")
                            if text.strip():
                                text_parts.append(text)
                        elif item.get("kind") == "toolUse":
                            tool_data = item.get("data", {})
                            current_turn["_pending_tools"].append(tool_data)

                if text_parts:
                    existing = current_turn["assistant"]
                    new_text = "\n".join(text_parts)
                    current_turn["assistant"] = f"{existing}\n{new_text}" if existing else new_text

            elif kind == "ToolResults" and current_turn is not None:
                for item in data.get("content", []):
                    if isinstance(item, dict) and "data" in item:
                        result_data = item["data"]
                        tool_use_id = result_data.get("toolUseId", "")
                        if tool_use_id:
                            tool_results[tool_use_id] = result_data

        if current_turn:
            self._finalize_turn(current_turn, tool_results)
            turns.append(current_turn)

        return turns

    def _finalize_turn(self, turn: dict, tool_results: dict[str, dict]) -> None:
        """Resolve pending tool calls against their results and clean up."""
        for tool_data in turn.pop("_pending_tools", []):
            tool_use_id = tool_data.get("toolUseId", "")
            name = tool_data.get("name", "")
            tool_input = tool_data.get("input", {})
            result = tool_results.get(tool_use_id)

            success = result.get("status") == "success" if result else False

            tool_entry: dict = {
                "id": tool_use_id,
                "name": name,
                "target": self._extract_target(name, tool_input),
                "success": success,
            }

            if not success and result:
                error = self._extract_error(result)
                if error:
                    tool_entry["error"] = error

            turn["tools"].append(tool_entry)

        # Trim assistant text and use block scalar for multi-line
        if turn["assistant"]:
            text = turn["assistant"].strip()[:2000]
            turn["assistant"] = _block(text)
        else:
            turn.pop("assistant")

        # Remove empty tools list
        if not turn["tools"]:
            turn.pop("tools")

    def _extract_target(self, tool_name: str, tool_input: dict) -> str:
        """Extract a short target summary from tool input."""
        extractors = {
            "read": lambda i: self._read_target(i),
            "write": lambda i: i.get("path", ""),
            "shell": lambda i: i.get("command", ""),
            "glob": lambda i: i.get("pattern", ""),
            "grep": lambda i: i.get("pattern", ""),
            "code": lambda i: (
                f"{i.get('operation', '')} {i.get('symbol_name', i.get('file_path', ''))}".strip()
            ),
            "web_search": lambda i: i.get("query", ""),
            "web_fetch": lambda i: i.get("url", ""),
            "fetch": lambda i: i.get("url", ""),
            "use_aws": lambda i: (
                f"{i.get('service_name', '')} {i.get('operation_name', '')}".strip()
            ),
            "subagent": lambda i: i.get("task", "")[:100],
            "introspect": lambda i: i.get("query", i.get("doc_path", "")),
        }

        extractor = extractors.get(tool_name)
        if extractor:
            target = extractor(tool_input) or ""
        else:
            # Fallback: first meaningful string value
            target = ""
            for v in tool_input.values():
                if isinstance(v, str) and v and not v.startswith("{"):
                    target = v[:200]
                    break

        return _block(target)

    def _read_target(self, tool_input: dict) -> str:
        """Extract path from read tool input."""
        ops = tool_input.get("operations", [])
        if ops and isinstance(ops[0], dict):
            return ops[0].get("path", "") or ", ".join(ops[0].get("image_paths", [])[:2])
        return ""

    def _extract_error(self, result: dict) -> str:
        """Extract error message from a failed tool result."""
        content = result.get("content", [])
        if not content:
            return ""

        for item in content:
            if not isinstance(item, dict):
                continue
            data = item.get("data", "")

            # Text error (validation failures, cancellations)
            if isinstance(data, str):
                return data[:500]

            # JSON error (shell with non-zero exit)
            if isinstance(data, dict):
                exit_status = data.get("exit_status", "")
                stderr = data.get("stderr", "")
                if exit_status and "exit status: 0" not in exit_status:
                    first_line = stderr.strip().split("\n")[0] if stderr else ""
                    msg = f"{exit_status} — {first_line}" if first_line else exit_status
                    return msg[:500]

        return ""

    def _should_process(self, meta: dict) -> bool:
        """Check if a session should be processed (not a subagent, has content)."""
        session_state = meta.get("session_state") or {}
        return bool(session_state.get("agent_name"))

    def _resolve_project(self, cwd: str) -> str:
        """Extract project name from session cwd."""
        if self._config is None:
            self._config = load_config()
        project_dir = Path(self._config.get("project_dir", "~/dev")).expanduser().resolve()
        cwd_path = Path(cwd).resolve() if cwd else Path.cwd()

        try:
            relative = cwd_path.relative_to(project_dir)
            if relative.parts:
                return relative.parts[0]
        except ValueError:
            pass
        return "general"

    def _output_path(self, meta: dict) -> Path:
        """Compute output file path from session metadata."""
        date = self._format_iso(meta.get("created_at", ""))[:10]
        project = self._resolve_project(meta.get("cwd", ""))
        session_id = meta.get("session_id", "unknown")
        return self._output_dir / f"{date}-{project}-{session_id}.yaml"

    def _is_fresh(self, source: Path, output: Path) -> bool:
        """Check if output is up-to-date with source."""
        if not output.exists():
            return False
        return output.stat().st_mtime >= source.stat().st_mtime

    def _updated_at_ms(self, meta: dict) -> int:
        """Extract updated_at as unix milliseconds from session metadata."""
        dt = self._parse_iso(meta.get("updated_at", ""))
        return int(dt.timestamp() * 1000) if dt else 0

    def _load_meta(self, json_path: Path) -> dict | None:
        """Load session metadata JSON."""
        try:
            return json.loads(json_path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def _read_jsonl(self, path: Path) -> list[dict]:
        """Read all entries from a JSONL file."""
        entries = []
        with path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return entries

    def _extract_text(self, data: dict) -> str:
        """Extract text content from a Prompt data dict."""
        content = data.get("content", [])
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("kind") == "text":
                    parts.append(item.get("data", ""))
            return "\n".join(parts).strip()
        if isinstance(content, str):
            return content.strip()
        return data.get("prompt", "")

    def _format_iso(self, iso_str: str) -> str:
        """Convert ISO 8601 to YYYY-MM-DD hh:mm:ss."""
        dt = self._parse_iso(iso_str)
        return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else ""

    def _parse_iso(self, iso_str: str) -> datetime | None:
        """Parse ISO 8601 string (with nanosecond tolerance) to datetime."""
        if not iso_str:
            return None
        try:
            if "." in iso_str:
                base, frac = iso_str.split(".", 1)
                tz_suffix = ""
                for tz in ("Z", "+", "-"):
                    if tz in frac:
                        idx = frac.index(tz)
                        tz_suffix = frac[idx:]
                        frac = frac[:idx]
                        break
                frac = frac[:6]
                iso_str = f"{base}.{frac}{tz_suffix}"
            iso_str = iso_str.replace("Z", "+00:00")
            return datetime.fromisoformat(iso_str)
        except (ValueError, TypeError):
            return None

    def _format_timestamp(self, ts: int | None) -> str:
        """Convert unix timestamp to YYYY-MM-DD hh:mm:ss."""
        if not ts:
            return ""
        return datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%d %H:%M:%S")

    # --- SQLite session support ---

    def _digest_sqlite(self, *, since: int | None = None) -> tuple[int, int, int]:
        """Process sessions from the SQLite database. Returns (processed, skipped, errors)."""
        import sqlite3

        processed, skipped, errors = 0, 0, 0
        conn = sqlite3.connect(self._sqlite_path)

        query = "SELECT key, conversation_id, value, created_at, updated_at FROM conversations_v2"
        params: list = []
        if since:
            query += " WHERE updated_at > ?"
            params.append(since)
        query += " ORDER BY updated_at ASC"

        for key, conversation_id, value, created_at, updated_at in conn.execute(query, params):
            try:
                data = json.loads(value)
            except json.JSONDecodeError:
                continue

            history = data.get("history", [])
            if not history:
                skipped += 1
                continue

            meta = {
                "session_id": conversation_id,
                "cwd": key,
                "created_at": self._ms_to_iso(created_at),
                "updated_at": self._ms_to_iso(updated_at),
            }

            output_path = self._output_path(meta)
            if output_path.exists():
                # Freshness: compare updated_at against output mtime
                output_mtime_ms = int(output_path.stat().st_mtime * 1000)
                if updated_at <= output_mtime_ms:
                    skipped += 1
                    continue

            try:
                turns = self._parse_sqlite_history(history)
                if not turns:
                    skipped += 1
                    continue

                result = {
                    "session_id": conversation_id,
                    "project": self._resolve_project(key),
                    "started": self._format_iso(meta["created_at"]),
                    "ended": self._format_iso(meta["updated_at"]),
                    "turns": turns,
                }

                output_path.write_text(
                    yaml.dump(
                        result,
                        default_flow_style=False,
                        sort_keys=False,
                        allow_unicode=True,
                        width=9999,
                    )
                )
                processed += 1
            except Exception as e:
                errors += 1
                import sys

                print(f"  Error processing {conversation_id}: {e}", file=sys.stderr)

        conn.close()
        return processed, skipped, errors

    def _parse_sqlite_history(self, history: list[dict]) -> list[dict]:
        """Parse SQLite history entries into turns."""
        turns = []
        current_turn: dict | None = None
        tool_results: dict[str, dict] = {}

        for entry in history:
            user = entry.get("user", {})
            assistant = entry.get("assistant", {})
            user_content = user.get("content", {})

            # User prompt — starts a new turn
            if isinstance(user_content, dict) and "Prompt" in user_content:
                if current_turn:
                    self._finalize_turn(current_turn, tool_results)
                    turns.append(current_turn)

                prompt_text = user_content["Prompt"].get("prompt", "")
                timestamp = user.get("timestamp", "")

                current_turn = {
                    "prompt_id": "",
                    "when": self._format_iso(timestamp) if timestamp else "",
                    "user": _block(prompt_text) if prompt_text else "",
                    "assistant": "",
                    "tools": [],
                    "_pending_tools": [],
                }
                tool_results = {}

            # Tool results from user side
            elif isinstance(user_content, dict) and "ToolUseResults" in user_content:
                for r in user_content["ToolUseResults"].get("tool_use_results", []):
                    tool_use_id = r.get("tool_use_id", "")
                    status = r.get("status", "")
                    tool_results[tool_use_id] = {
                        "status": "success" if status == "Success" else "error",
                        "content": r.get("content", []),
                    }

            # Assistant response
            if "Response" in assistant and current_turn is not None:
                resp = assistant["Response"]
                text = resp.get("content", "")
                if text and text.strip():
                    existing = current_turn["assistant"]
                    current_turn["assistant"] = f"{existing}\n{text}" if existing else text

            # Assistant tool use
            elif "ToolUse" in assistant and current_turn is not None:
                tu = assistant["ToolUse"]
                text = tu.get("content", "")
                if text and text.strip():
                    existing = current_turn["assistant"]
                    current_turn["assistant"] = f"{existing}\n{text}" if existing else text
                for tool in tu.get("tool_uses", []):
                    current_turn["_pending_tools"].append(
                        {
                            "toolUseId": tool.get("id", ""),
                            "name": self._map_tool_name(tool.get("name", "")),
                            "input": tool.get("args", {}),
                        }
                    )

        if current_turn:
            self._finalize_turn(current_turn, tool_results)
            turns.append(current_turn)

        return turns

    def _map_tool_name(self, name: str) -> str:
        """Map SQLite-era tool names to current names."""
        mapping = {
            "fs_read": "read",
            "fs_write": "write",
            "execute_bash": "shell",
            "fs_list": "glob",
            "search_files": "grep",
        }
        return mapping.get(name, name)

    def _ms_to_iso(self, ms: int) -> str:
        """Convert unix milliseconds to ISO 8601 string."""
        return datetime.fromtimestamp(ms / 1000, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
