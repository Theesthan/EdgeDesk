"""Email reader tool via IMAP.

Reads emails from an IMAP mailbox using credentials from the environment.
Required env vars: IMAP_HOST, IMAP_USER, IMAP_PASS.
Optional: IMAP_PORT (default 993).

All network I/O is done synchronously on a thread-pool executor in _arun.
"""

from __future__ import annotations

import asyncio
import email
import imaplib
import os
from typing import Any

from langchain_core.tools import BaseTool
from loguru import logger

from schemas.models import EmailItem, EmailListInput, EmailListOutput, ToolError

_DEFAULT_IMAP_PORT: int = 993


def _fetch_emails(folder: str, limit: int) -> EmailListOutput | ToolError:
    """Connect to IMAP and fetch the most recent *limit* messages."""
    host = os.environ.get("IMAP_HOST", "")
    user = os.environ.get("IMAP_USER", "")
    password = os.environ.get("IMAP_PASS", "")
    port = int(os.environ.get("IMAP_PORT", _DEFAULT_IMAP_PORT))

    if not host or not user or not password:
        return ToolError(
            tool="email_reader",
            message="IMAP_HOST, IMAP_USER, IMAP_PASS env vars are required.",
            retryable=False,
        )

    try:
        with imaplib.IMAP4_SSL(host, port) as imap:
            imap.login(user, password)
            imap.select(folder, readonly=True)

            # Search all messages; UIDs are strings
            status, data = imap.search(None, "ALL")
            if status != "OK":
                return ToolError(tool="email_reader", message=f"IMAP search failed: {status}", retryable=True)

            uids = data[0].split()
            recent_uids = uids[-limit:] if len(uids) > limit else uids
            items: list[EmailItem] = []

            for uid in reversed(recent_uids):  # newest first
                fetch_status, msg_data = imap.fetch(uid, "(RFC822)")
                if fetch_status != "OK" or not msg_data or not msg_data[0]:
                    continue
                raw = msg_data[0][1]
                if not isinstance(raw, bytes):
                    continue
                msg = email.message_from_bytes(raw)

                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            payload = part.get_payload(decode=True)
                            if isinstance(payload, bytes):
                                body = payload.decode(errors="replace")
                                break
                else:
                    payload = msg.get_payload(decode=True)
                    if isinstance(payload, bytes):
                        body = payload.decode(errors="replace")

                items.append(
                    EmailItem(
                        uid=uid.decode(),
                        subject=msg.get("Subject", "(no subject)"),
                        sender=msg.get("From", ""),
                        date=msg.get("Date", ""),
                        body=body[:2000],  # truncate long bodies
                    )
                )

        return EmailListOutput(emails=items, total=len(uids))

    except imaplib.IMAP4.error as exc:
        logger.error("email_reader IMAP error: {}", exc)
        return ToolError(tool="email_reader", message=str(exc), retryable=True)
    except Exception as exc:
        logger.error("email_reader unexpected error: {}", exc)
        return ToolError(tool="email_reader", message=str(exc), retryable=False)


class EmailTool(BaseTool):
    """List recent emails from an IMAP mailbox (credentials from env)."""

    name: str = "email_reader"
    description: str = "List recent emails from IMAP inbox using env credentials."
    args_schema: type = EmailListInput

    def _run(self, **kwargs: Any) -> EmailListOutput | ToolError:
        try:
            inp = EmailListInput(**kwargs)
        except Exception as exc:
            return ToolError(tool="email_reader", message=f"Invalid input: {exc}", retryable=False)

        logger.debug("email_reader folder={} limit={}", inp.folder, inp.limit)
        return _fetch_emails(inp.folder, inp.limit)

    async def _arun(self, **kwargs: Any) -> EmailListOutput | ToolError:
        try:
            inp = EmailListInput(**kwargs)
        except Exception as exc:
            return ToolError(tool="email_reader", message=f"Invalid input: {exc}", retryable=False)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: _fetch_emails(inp.folder, inp.limit))
