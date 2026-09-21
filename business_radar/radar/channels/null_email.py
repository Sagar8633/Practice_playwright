"""The transport that cannot contact anybody, and is what runs unless a human said otherwise.

Every other safety mechanism in this system is a check that can, in principle, be passed. This
one is the absence of a socket. It is the default in config.example.yaml, the default when the
config key is missing, the default when the key is misspelled, and the default in every test.

The .eml files it writes open in any mail client and grep like text, which is what makes the
whole send path - draft, policy, approval, transmit, record, counters, status transition -
something Sagar can exercise end to end in an afternoon with nothing leaving the laptop. It
returns ACCEPTED rather than some special "not really sent" outcome, on purpose: a null
transport that short-circuits the recording path proves nothing. `provider = 'null'` is written
on the row instead, so "did this actually leave the machine" is a query and never an inference.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import ClassVar

from radar.channels.mime import build_mime, parse_date
from radar.channels.types import OutboundEmail, TransportResult

log = logging.getLogger("radar.channels.null_email")


class NullEmailTransport:
    name: ClassVar[str] = "null"
    is_live: ClassVar[bool] = False
    supports_delivery_receipts: ClassVar[bool] = False

    def __init__(self, outbox_dir: Path) -> None:
        self._dir = Path(outbox_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def send(self, msg: OutboundEmail, *, idempotency_key: str) -> TransportResult:
        try:
            raw = build_mime(msg).as_bytes()
        except Exception as exc:                     # noqa: BLE001 - never raise from a send
            log.exception("could not build the MIME message for %s", msg.message_id)
            return TransportResult(
                outcome="FAILED", provider=self.name, provider_message_id=None,
                failure_code="MIME_BUILD_FAILED", failure_detail=str(exc)[:500],
            )

        when = parse_date(msg.date) if msg.date else None
        day = when.strftime("%Y-%m-%d") if when else "undated"
        target = self._dir / day / f"{msg.message_id}.eml"
        target.parent.mkdir(parents=True, exist_ok=True)

        tmp = target.with_suffix(".eml.tmp")
        try:
            tmp.write_bytes(raw)
            os.replace(tmp, target)                  # atomic write, never a half file
        except OSError as exc:
            log.error("could not write %s: %s", target, exc)
            return TransportResult(
                outcome="FAILED", provider=self.name, provider_message_id=None,
                failure_code="OUTBOX_UNWRITABLE", failure_detail=str(exc)[:500], retryable=True,
            )

        log.info("null transport wrote %s (%d bytes) for %s", target, len(raw), msg.message_id)
        return TransportResult(
            outcome="ACCEPTED", provider=self.name,
            provider_message_id=f"null:{msg.message_id}", status_code=200,
            raw={"path": str(target), "bytes": len(raw), "idempotency_key": idempotency_key},
        )

    def preflight(self) -> list[str]:
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return [f"outbox directory {self._dir} could not be created: {exc}"]
        if not os.access(self._dir, os.W_OK):
            return [f"outbox directory {self._dir} is not writable"]
        return []

    @property
    def outbox_dir(self) -> Path:
        return self._dir
