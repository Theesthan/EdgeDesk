"""File system tool.

Supports read, write, move, delete, and list operations using pathlib.
All paths are resolved to absolute paths. Path traversal ('..') is rejected
at both the schema level and here as a defence-in-depth measure.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool
from loguru import logger

from schemas.models import (
    FileMoveInput,
    FileMoveOutput,
    FileReadInput,
    FileReadOutput,
    FileWriteInput,
    ToolError,
)

_MAX_READ_BYTES: int = 10 * 1024 * 1024  # 10 MB safety cap


def _safe_path(raw: str) -> Path | None:
    """Resolve path and reject traversal attempts.

    Returns None (which callers convert to ToolError) if the path is unsafe.
    """
    if ".." in raw:
        return None
    return Path(raw).expanduser().resolve()


class FileTool(BaseTool):
    """Read, write, move, delete, or list files on the local filesystem."""

    name: str = "file_op"
    description: str = "Read, write, move, delete, or list local files."
    args_schema: type = FileReadInput  # schema dispatched by action field

    # ------------------------------------------------------------------ #
    # Individual actions
    # ------------------------------------------------------------------ #

    def _read(self, path_str: str, encoding: str = "utf-8") -> FileReadOutput | ToolError:
        p = _safe_path(path_str)
        if p is None:
            return ToolError(tool="file_read", message="Path traversal denied.", retryable=False)
        try:
            size = p.stat().st_size
            if size > _MAX_READ_BYTES:
                return ToolError(tool="file_read", message=f"File too large ({size} bytes > {_MAX_READ_BYTES}).", retryable=False)
            content = p.read_text(encoding=encoding)
            return FileReadOutput(content=content, encoding=encoding, size_bytes=size)
        except Exception as exc:
            logger.error("file_read '{}': {}", path_str, exc)
            return ToolError(tool="file_read", message=str(exc), retryable=False)

    def _write(self, path_str: str, content: str, encoding: str = "utf-8", overwrite: bool = True) -> ToolError | dict[str, Any]:
        p = _safe_path(path_str)
        if p is None:
            return ToolError(tool="file_write", message="Path traversal denied.", retryable=False)
        try:
            if p.exists() and not overwrite:
                return ToolError(tool="file_write", message=f"File exists and overwrite=False: {p}", retryable=False)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding=encoding)
            return {"path": str(p), "size_bytes": p.stat().st_size}
        except Exception as exc:
            logger.error("file_write '{}': {}", path_str, exc)
            return ToolError(tool="file_write", message=str(exc), retryable=False)

    def _move(self, src_str: str, dst_str: str) -> FileMoveOutput | ToolError:
        src = _safe_path(src_str)
        dst = _safe_path(dst_str)
        if src is None or dst is None:
            return ToolError(tool="file_move", message="Path traversal denied.", retryable=False)
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return FileMoveOutput(new_path=str(dst))
        except Exception as exc:
            logger.error("file_move '{}' → '{}': {}", src_str, dst_str, exc)
            return ToolError(tool="file_move", message=str(exc), retryable=False)

    def _delete(self, path_str: str) -> dict[str, Any] | ToolError:
        p = _safe_path(path_str)
        if p is None:
            return ToolError(tool="file_delete", message="Path traversal denied.", retryable=False)
        try:
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink(missing_ok=True)
            return {"deleted": str(p)}
        except Exception as exc:
            logger.error("file_delete '{}': {}", path_str, exc)
            return ToolError(tool="file_delete", message=str(exc), retryable=False)

    def _list(self, path_str: str) -> dict[str, Any] | ToolError:
        p = _safe_path(path_str)
        if p is None:
            return ToolError(tool="file_list", message="Path traversal denied.", retryable=False)
        try:
            entries = [
                {"name": e.name, "is_dir": e.is_dir(), "size_bytes": e.stat().st_size if e.is_file() else 0}
                for e in sorted(p.iterdir())
            ]
            return {"path": str(p), "entries": entries}
        except Exception as exc:
            logger.error("file_list '{}': {}", path_str, exc)
            return ToolError(tool="file_list", message=str(exc), retryable=False)

    # ------------------------------------------------------------------ #
    # LangChain interface
    # ------------------------------------------------------------------ #

    def _run(  # type: ignore[override]
        self,
        action: str,
        path: str = "",
        content: str = "",
        encoding: str = "utf-8",
        overwrite: bool = True,
        src: str = "",
        dst: str = "",
        **_kwargs: Any,
    ) -> Any:
        logger.debug("file_op action={} path={}", action, path or src)
        if action == "read":
            try:
                inp = FileReadInput(path=path)
            except Exception as exc:
                return ToolError(tool="file_read", message=f"Invalid input: {exc}", retryable=False)
            return self._read(inp.path, encoding)
        elif action == "write":
            try:
                inp = FileWriteInput(path=path, content=content, encoding=encoding, overwrite=overwrite)
            except Exception as exc:
                return ToolError(tool="file_write", message=f"Invalid input: {exc}", retryable=False)
            return self._write(inp.path, inp.content, inp.encoding, inp.overwrite)
        elif action == "move":
            try:
                inp = FileMoveInput(src=src, dst=dst)
            except Exception as exc:
                return ToolError(tool="file_move", message=f"Invalid input: {exc}", retryable=False)
            return self._move(inp.src, inp.dst)
        elif action == "delete":
            return self._delete(path)
        elif action == "list":
            return self._list(path)
        else:
            return ToolError(tool="file_op", message=f"Unknown action: {action!r}", retryable=False)

    async def _arun(self, **kwargs: Any) -> Any:  # type: ignore[override]
        return self._run(**kwargs)
