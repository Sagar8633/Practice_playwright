-- 030_messages.sql - what the message engine needs on top of 001.
--
-- Additive only. Every column here exists because radar/messages.py or radar/policy.py has to
-- answer a question six months later that 001's columns cannot:
--
--   template_version           which skeleton wrote this, so a message can be reproduced
--   claim_map                  the sentence -> finding_ids binding the policy engine re-checks
--   raw_generation             the model's own account of the call: source, temperature, why
--   unsubscribe_token          the 32 hex characters that turn an inbound mail into one hop
--   policy_checked_body_hash   what the checker actually read, so an edit cannot inherit a PASS
--
-- The last one is the load-bearing addition. Without it, editing a draft after a PASS and
-- approving it would send text no rule ever saw; the approve path compares this column against
-- sha256(subject + RS + body) and refuses when they differ.
--
-- Forward-only. Never edit an applied migration.

ALTER TABLE outreach_drafts ADD COLUMN template_version TEXT;
ALTER TABLE outreach_drafts ADD COLUMN claim_map TEXT NOT NULL DEFAULT '[]';
ALTER TABLE outreach_drafts ADD COLUMN raw_generation TEXT;
ALTER TABLE outreach_drafts ADD COLUMN unsubscribe_token TEXT;
ALTER TABLE outreach_drafts ADD COLUMN policy_checked_body_hash TEXT;

-- One token, one draft. The uniqueness is what makes an inbound unsubscribe unambiguous:
-- a token resolves to exactly one draft, hence one message, one business and one address.
CREATE UNIQUE INDEX IF NOT EXISTS ux_drafts_unsub
    ON outreach_drafts(unsubscribe_token) WHERE unsubscribe_token IS NOT NULL;
