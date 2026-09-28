# Prashant — status

A replica of Sagar's `naukri_profile` toolkit, set up for **Prashant Chhotu
Chaudhari**: Assistant Manager – Quality Assurance (Customer Quality & Supplier
Quality), Astemo India, Jalgaon. Tier-1 automotive braking, 15+ years.

Nothing of Sagar's personal data was copied in — his salary, notice period,
per-skill years and resume are all quoted to recruiters in the account holder's
name. Only the code and the field-agnostic `answer_rules` came across.

---

## Live on the Naukri profile (applied 2026-09-22, each verified by re-extract)

| Field | Change |
| --- | --- |
| Headline | Rewritten, 231/250. Fixed a doubled pipe and missing spaces, dropped "Expert in", added PFMEA, APQP, SPC |
| Summary | Replaced, 941/1000. The FY25 warranty numbers now sit **inside** the ~285 chars shown before "Read More" |
| Designation | `Assistant Manager customer quality` → `Assistant Manager - Quality Assurance (Customer Quality & Supplier Quality)` |
| Key skills | 13 → 19. Four sentence-shaped entries removed, ten searchable ones added |
| Resume file | New 2-page ATS resume uploaded, replacing `Resume_Prashant Chaudhari.03.pdf` |
| Baseline | `--perf`: 488 appearances, 11 actions, **2.25% action rate** |

**"Customer Quality" and "Supplier Quality" were not standalone key skills
before this.** They are the two phrases he is sourced by. That is probably the
single biggest change on the profile.

### The key-skill cap here is 19, not 22

Naukri accepted `Quality Core Tools` and `Layout Inspection`, reported success,
and the chips never appeared. No error. `apply.py` caught it only because it
re-reads the chips after saving — always read that WARNING output. The 22 in
Sagar's `changes.yaml` is a fact about *his* account, not the platform.

`Corrective And Preventive Action` was refused outright: Naukri's taxonomy only
offers "Corrective and Preventive Action Management". Key skills are a
controlled vocabulary, not free text.

---

## Open items — his facts, not guessable

1. **Employment dates manufacture a 3-month gap.** Naukri has the current role
   starting **May 2022**; the previous role ends **Feb 2022**. His resume *and
   the job-profile text inside that same Naukri entry* both say **February
   2022**. The profile is advertising three months of unemployment that never
   happened. One field in the employment dialog. Highest-value fix remaining.
2. **IATF 16949 Internal Auditor.** His headline claims it; his resume and his
   Naukri certifications section do not mention it. Kept in the headline because
   it is his own pre-existing claim — see the reasoning in `changes.yaml`. NOT
   propagated to the resume or certifications, because that would be a new
   assertion rather than a preserved one. Confirm and it goes in both; deny and
   it comes out today.
3. **Broken LinkedIn link.** Accomplishments holds
   `linkedin.com/public-profile/settings?trk=…` — the settings page of whoever
   is logged in, not a public profile. Needs his real `linkedin.com/in/<handle>`.
4. **Notice period conflict.** Profile says **2 Months**; he said **30 days**.
   Left at 2 months — it is a contractual term, not a preference, and the
   `answer_rules` behave correctly under either.
5. **Career profile.** Expected salary reads ₹9,50,000 against his stated 10
   LPA; role category reads "QA / QC Executive", below Assistant Manager. Both
   are recruiter filters. `scripts/career_profile.py`, once its two
   `TODO(extract)` values are filled.
6. **PPAP years.** `jobs.yaml` gives it 4.5, derived from the current role. His
   resume evidences PPAP in *both* roles, which reads like 10+. Understating it
   costs him roles that filter on it.

---

## Job scanning — not started

`role: manufacturing-quality` is active: a fifth role pack, 138 skills, written
for this field with `extends: none`, because `_common.yaml` is entirely software
vocabulary and inheriting it would make the interview matrix count Kubernetes
against a PPAP job description.

Applications are **off** (`answer_questionnaires: false`, `max_auto_applies: 5`,
`auto_apply_min_score: 78`). Next:

```
python main.py --jobs                  # dry run, sends nothing. Do this for days.
python main.py --jobs-export --top 30  # ranked spreadsheet to work by hand
```

**The demand table in `docs/RECRUITER_VISIBILITY.md` is QA/SDET data and does
not transfer to this field.** The method does. After a week or two of scans,
count terms over `data/jobs/results-*.json` with the script in section 3 of that
document to get *his* ranked list, then revisit the key skills against it.

Only after that: `--jobs-probe`, then `answer_questionnaires: true`, then
`--jobs --yes --limit 3`.

---

## Things worth knowing about this codebase

- **`tight_terms` is dead.** `roles.py:143` loads it, `skills.py:45` assigns it
  to `_TIGHT`, and nothing ever reads it. Documented in `docs/ROLES.md` and
  populated in `_common.yaml`, but inert. Alias safety rests entirely on the
  aliases themselves.
- **The login takes no password, by design.** `--login` opens a headed browser
  and a human signs in. Naukri blocks headless Chromium and needs OTP/captcha.
  The sign-in must happen *inside the Playwright window* — a login in your own
  Edge or Chrome is invisible to it.
- **One test was changed** —
  `tests/test_answers.py::test_the_traps_still_win_over_the_catch_all`. It
  asserted "can you join immediately?" → `"No"`, which was true of the source
  account's notice period, not a general invariant. It now asserts what the
  docstring always said: questions false for anyone return `"No"`; questions
  grounded in a personal fact return anything but `"Yes"`. 104 tests pass.

Read `docs/SAFETY.md` before turning on anything that submits.
