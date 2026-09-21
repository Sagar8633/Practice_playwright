-- 010_verify_eligibility.sql
--
-- Two cached columns on businesses, required by 04-verification-workflow.md section 4.3.4.
--
-- Without them the campaign grid cannot explain a business that is VERIFIED but held back.
-- CONTACT_READY is a materialised answer to a seven-clause predicate; when a clause breaks the
-- business drops to VERIFIED and, with nothing recorded, every screen has to either re-run the
-- whole policy engine per row or print "verified" next to a business nobody may contact today.
-- refresh_contact_readiness() writes both columns on every evaluation, so the grid renders the
-- real reason with one indexed read.
--
-- Forward-only and idempotent at the file level: db.migrate() applies each numbered file once.

ALTER TABLE businesses ADD COLUMN contact_ready_block_code TEXT;
ALTER TABLE businesses ADD COLUMN contact_ready_checked_at TEXT;

-- The grid's "held back, and here is why" filter.
CREATE INDEX IF NOT EXISTS ix_businesses_ready_block
    ON businesses(contact_ready_block_code)
    WHERE contact_ready_block_code IS NOT NULL;

-- Two audit actions this pair of modules writes and 001's catalogue does not carry.
-- audit() refuses an action the catalogue does not declare, which is the point: a typo in an
-- action name would otherwise become a silently unqueryable audit row.
INSERT OR IGNORE INTO audit_actions (action, domain, severity, user_visible, pii_class, description)
VALUES
    ('CONTACT_READY_GRANTED', 'VERIFICATION', 'NOTICE', 1, 'NONE',
     'A business satisfied the contact-ready predicate and entered the outreach pool'),
    ('CONTACT_READY_REVOKED', 'VERIFICATION', 'NOTICE', 1, 'NONE',
     'A contact-ready clause broke and the business left the outreach pool');

-- ---------------------------------------------------------------------------
-- The T14 hole in trg_biz_verified_needs_human_checklist.
--
-- 001_schema.sql declares ('CONTACT_READY','VERIFIED','SYSTEM','T09'... 'T14') as a legal
-- transition - it is how a business leaves the outreach pool when a suppression lands, a
-- contact dies or a frequency window shuts - and then forbids it, because the trigger demands
-- a HUMAN actor on every path into VERIFIED. The two disagree, and the disagreement makes the
-- demotion unreachable: the only alternative is to send the business back to
-- NEEDS_VERIFICATION, which deletes a signature nobody withdrew and costs nine checks that
-- produce the same nine answers. That is the rubber stamp 04-verification-workflow.md section
-- 4.7 exists to prevent.
--
-- The rewrite below keeps the whole of the invariant and closes only that hole. The live
-- nine-check verification is still required on EVERY path into VERIFIED, including this one,
-- and no system actor can fabricate one: verifications.verified_by is a users foreign key and
-- the row CHECK demands nine passes, a why-note and a dwell above the floor. What is relaxed
-- is only the human-actor requirement on the single transition where the business is being put
-- back where its own still-live signature already placed it.
DROP TRIGGER IF EXISTS trg_biz_verified_needs_human_checklist;

CREATE TRIGGER trg_biz_verified_needs_human_checklist
BEFORE UPDATE OF status ON businesses
FOR EACH ROW
WHEN NEW.status = 'VERIFIED' AND OLD.status <> 'VERIFIED'
 AND (
        NEW.status_verification_id IS NULL
     OR NOT EXISTS (SELECT 1 FROM verifications v
                     WHERE v.id            = NEW.status_verification_id
                       AND v.business_id   = NEW.id
                       AND v.state         = 'SUBMITTED'
                       AND v.verdict       = 'VERIFIED'
                       AND v.superseded_at IS NULL
                       AND v.checks_passed = 9
                       AND v.checks_failed = 0)
     OR (OLD.status <> 'CONTACT_READY'
         AND (NEW.status_actor_kind <> 'HUMAN' OR NEW.status_actor_user_id IS NULL))
 )
BEGIN
    SELECT RAISE(ABORT,
      'VERIFIED requires a live human verification with all nine checks passed');
END;
