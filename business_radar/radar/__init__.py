"""business_radar - research businesses city by city, then make a human decide before anything
is sent.

The pipeline, and the reason it is not shorter:

    RESEARCH -> REPORT -> VERIFY -> SELECT -> PERSONALIZE -> PREVIEW -> CONFIRM -> SEND

Four invariants hold the shape, and every module in this package is built so that breaking one
requires deleting code rather than forgetting to write some:

    1. No send path exists that does not pass through a human approval row. send() takes an
       approval_id and rejects a null one; the database refuses SENT without a live approval
       whose body hash and address match what is going out.
    2. outreach_messages.status reaches SENT only from APPROVED or QUEUED, and QUEUED only from
       APPROVED. Enforced by a transition table and three triggers.
    3. An opt-out blocks every channel for that business, permanently. suppressions rows cannot
       be deleted, and releasing one needs a manual database session plus a matching audit row
       the application has no code to create.
    4. Every claim in a generated message traces to a stored finding. OBSERVED facts may be
       stated, INFERRED must be hedged, UNKNOWN must never appear.

Import order for anything building on this: `paths` has no dependencies, `ids` and `models`
depend only on the standard library, `config` needs `paths`, `db` needs `paths`, and `audit`
needs `ids`, `models` and an open connection. Nothing here imports Flask or google-genai, so
this package can be imported by a test with no network and no key.
"""
from __future__ import annotations

__version__ = "0.1.0"
__all__ = ["__version__"]
