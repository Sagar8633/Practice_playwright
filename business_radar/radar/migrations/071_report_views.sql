-- ===========================================================================
-- 030_report_views.sql - v_report_business, the report's spine
-- ===========================================================================
-- 03-html-report.md section 3.3.2 owns this view. It is the only object this
-- document creates, and it exists so that "qualified" has exactly one
-- definition in the system. Twelve KPI cards, five city figures, two
-- comparison tables and the business grid all aggregate over this view; if
-- each of them carried its own CASE expression for "qualified", the header
-- would eventually disagree with the city card that is meant to break it down.
--
-- The grain is one row per (campaign, business), not one row per business:
-- campaign membership lives in campaign_businesses, and discovered_at is the
-- per-campaign first_seen_at rather than the global first_discovered_at.
--
-- The view never filters on cb.state. An EXCLUDED membership row is still a
-- business this campaign found, and "Businesses found" counts it.
-- ===========================================================================

DROP VIEW IF EXISTS v_report_business;

CREATE VIEW v_report_business AS
WITH contact AS (
    SELECT c.business_id,
           COUNT(*)                                             AS n_contacts,
           MAX(CASE WHEN c.kind = 'EMAIL'    THEN 1 ELSE 0 END) AS has_email,
           MAX(CASE WHEN c.kind = 'PHONE'    THEN 1 ELSE 0 END) AS has_phone,
           MAX(CASE WHEN c.kind = 'WHATSAPP' THEN 1 ELSE 0 END) AS has_whatsapp
      FROM business_contacts c
     WHERE c.is_active = 1 AND c.human_verified = 1
     GROUP BY c.business_id
),
contact_any AS (
    SELECT c.business_id, COUNT(*) AS n_contacts_any
      FROM business_contacts c
     WHERE c.is_active = 1
     GROUP BY c.business_id
),
verif AS (
    SELECT v.business_id, MAX(v.verified_at) AS verified_at
      FROM verifications v
     WHERE v.verdict = 'VERIFIED' AND v.superseded_at IS NULL
     GROUP BY v.business_id
),
research AS (
    SELECT r.business_id,
           MAX(CASE WHEN r.status = 'COMPLETE' THEN 1 ELSE 0 END) AS research_complete,
           MAX(r.finished_at)                                     AS researched_at,
           MAX(r.depth)                                           AS research_depth
      FROM research_runs r
     GROUP BY r.business_id
),
sent AS (
    SELECT m.business_id,
           COUNT(*)       AS n_sent,
           MIN(m.sent_at) AS first_sent_at,
           MAX(m.sent_at) AS last_sent_at
      FROM outreach_messages m
     WHERE m.status IN ('SENT','DELIVERED','BOUNCED')
     GROUP BY m.business_id
),
last_msg AS (
    SELECT m.business_id,
           m.status  AS last_message_status,
           m.channel AS last_channel
      FROM outreach_messages m
      JOIN (SELECT business_id,
                   MAX(COALESCE(sent_at, queued_at, created_at)) AS t
              FROM outreach_messages
             GROUP BY business_id) x
        ON x.business_id = m.business_id
       AND COALESCE(m.sent_at, m.queued_at, m.created_at) = x.t
),
resp AS (
    SELECT r.business_id,
           COUNT(*)            AS n_responses,
           MAX(r.received_at)  AS last_response_at,
           MAX(CASE WHEN COALESCE(r.human_classification, r.classification)
                         IN ('INTERESTED','VERY_INTERESTED','DEMO_REQUESTED',
                             'MEETING_REQUESTED','PRICE_REQUESTED')
                    THEN 1 ELSE 0 END) AS is_interested
      FROM responses r
     GROUP BY r.business_id
),
modules AS (
    SELECT om.business_id, COUNT(*) AS n_modules
      FROM opportunity_modules om
     WHERE om.is_current = 1
     GROUP BY om.business_id
),
suppressed AS (
    SELECT DISTINCT b.id AS business_id
      FROM businesses b
      LEFT JOIN business_contacts c ON c.business_id = b.id
      JOIN suppressions s
        ON s.released_at IS NULL
       AND ( (s.scope = 'BUSINESS' AND s.value_norm = b.id)
          OR (s.scope = 'EMAIL'    AND c.kind = 'EMAIL'    AND s.value_norm = c.value_norm)
          OR (s.scope = 'PHONE'    AND c.kind = 'PHONE'    AND s.value_norm = c.value_norm)
          OR (s.scope = 'WHATSAPP' AND c.kind = 'WHATSAPP' AND s.value_norm = c.value_norm)
          OR (s.scope = 'DOMAIN'   AND s.value_norm = c.domain) )
)
SELECT
    b.id                          AS business_id,
    cb.campaign_id,
    b.name,
    b.city,
    b.city_slug,
    b.industry,
    b.category,
    b.size_band,
    b.status,
    b.website,
    b.website_domain,
    b.website_status,
    b.listing_url,
    cb.state                        AS membership_state,
    cb.first_seen_at                AS discovered_at,
    substr(cb.first_seen_at, 1, 10) AS discovered_on,

    o.score                       AS opportunity_score,
    o.band                        AS opportunity_band,
    o.confidence                  AS research_confidence,
    o.confidence_pct              AS research_confidence_pct,
    o.digital_maturity,
    o.operational_complexity,
    o.potential_problem,
    o.potential_solution,
    o.expected_benefit,
    o.est_value_inr,
    COALESCE(md.n_modules, 0)     AS n_modules,

    COALESCE(rs.research_complete, 0) AS research_complete,
    rs.researched_at,
    rs.research_depth,

    COALESCE(ct.n_contacts, 0)     AS n_contacts,
    COALESCE(ca.n_contacts_any, 0) AS n_contacts_any,
    COALESCE(ct.has_email, 0)      AS has_email,
    COALESCE(ct.has_phone, 0)      AS has_phone,
    COALESCE(ct.has_whatsapp, 0)   AS has_whatsapp,

    vf.verified_at,
    CASE WHEN vf.verified_at IS NOT NULL THEN 1 ELSE 0 END AS is_verified,

    COALESCE(sn.n_sent, 0)        AS n_sent,
    sn.first_sent_at,
    sn.last_sent_at,
    lm.last_message_status,
    lm.last_channel,

    COALESCE(rp.n_responses, 0)   AS n_responses,
    rp.last_response_at,
    COALESCE(rp.is_interested, 0) AS is_interested,

    CASE WHEN sp.business_id IS NOT NULL THEN 1 ELSE 0 END AS is_suppressed,

    -- "Qualified" has exactly one definition in this system, and it lives here.
    CASE WHEN COALESCE(rs.research_complete, 0) = 1
          AND o.score IS NOT NULL
          AND o.score >= COALESCE(cm.min_opportunity_score, 0)
          AND b.status NOT IN ('SKIPPED','REJECTED')
         THEN 1 ELSE 0 END        AS is_qualified,

    CASE WHEN b.status = 'CONTACT_READY' THEN 1 ELSE 0 END AS is_ready_for_outreach
FROM campaign_businesses cb
JOIN      businesses   b  ON b.id  = cb.business_id
JOIN      campaigns    cm ON cm.id = cb.campaign_id
LEFT JOIN opportunities o ON o.business_id = b.id AND o.is_current = 1
LEFT JOIN contact      ct ON ct.business_id = b.id
LEFT JOIN contact_any  ca ON ca.business_id = b.id
LEFT JOIN verif        vf ON vf.business_id = b.id
LEFT JOIN research     rs ON rs.business_id = b.id
LEFT JOIN sent         sn ON sn.business_id = b.id
LEFT JOIN last_msg     lm ON lm.business_id = b.id
LEFT JOIN resp         rp ON rp.business_id = b.id
LEFT JOIN modules      md ON md.business_id = b.id
LEFT JOIN suppressed   sp ON sp.business_id = b.id;
