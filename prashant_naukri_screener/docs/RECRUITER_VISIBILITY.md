# Recruiter visibility: what actually surfaces a Naukri profile

You are about to build a resume and a Naukri profile for someone using this
toolkit. This file is the operating manual for the visibility half of that job:
which fields recruiters search, where they get cut off, and what the measured
demand data says is worth putting in them.

Everything here is carried over from the source project
(`D:/Practice_Playwright/naukri_profile`), where it was established against one
real account and 1,539 real scraped postings. Every number below carries its
source inline. Where the evidence is one unsourced comment rather than a
measurement, it says so — follow those as house convention, not as platform
fact.

**The honesty rule comes first, because it governs every other rule here.** A
keyword is worth adding only if the person can truthfully claim it. The source
project states this as its own constraint — *"Every keyword added below is one
this profile can honestly claim: each appears in
resume/Sagar_Jadhav_QA_Automation_Resume.txt"*
(`naukri_profile/changes.yaml:30-32`) — and it held to it in the one place it
cost something: `"Senior"` appears in 17.4% of target titles and was still
deliberately left out of the designation, because the resume and the employment
record both say plain Software Test Engineer
(`naukri_profile/changes.yaml:156-158`). A keyword you cannot defend in the room
is worse than a missing one: it is an interview you lose after being found.

**Nothing in this file knows Prashant's years of experience, current or expected
salary, notice period, seniority, certification dates or employers.** Those are
his to supply. Section 8 marks every step that needs them.

---

## 1. The short version

Ordered by leverage per unit of effort. A reader in a hurry can act off this
section alone.

- [ ] **1. Re-measure demand for his field before writing a single field.** The
      table in section 3 is QA/SDET-specific. Run the scan for a few days, then
      count terms over `data/jobs/results-*.json` (command in section 3). Costs
      one evening of elapsed time and decides everything below it.
- [ ] **2. Write the profile summary so the first ~285 characters stand alone** —
      role, stack and at least one number inside that prefix. Naukri collapses
      the rest behind "Read More", and that prefix is the entire snippet a
      recruiter reads in a result list (`naukri_profile/changes.yaml:62-63`;
      `naukri/apply.py:651-656`). In-house product names and domain acronyms go
      *after* the cut.
- [ ] **3. Treat the 250-character resume headline as a keyword field, not a
      slogan.** Hard cap at 250 (`naukri/selectors.py:207`), and the tool refuses
      to submit over it (`naukri/apply.py:726-729`). No adjectives.
- [ ] **4. Budget exactly 22 key skills, ordered by measured demand, highest
      first.** 22 is the observed ceiling on a free account; the 23rd add is
      accepted and silently never appears (`naukri_profile/changes.yaml:22-26`;
      `naukri/apply.py:298-312`). Adds are applied in list order, so if the cap
      bites it eats the last entry — put the weakest last.
- [ ] **5. Use only the exact spelling Naukri's own suggester offers.** Key
      skills are taxonomy entries, not free text: `"REST API"` is refused,
      `"Rest API Testing"` is accepted (`naukri_profile/changes.yaml:16-20`).
      Never accept the first row offered — typing `"Git"` surfaces `"Github"` at
      the top (`naukri/apply.py:364-366`).
- [ ] **6. Give every skill you want filtered its own IT-skills row, with a years
      figure that matches what the headline and summary claim.** The source
      profile's headline claimed 4 years of Python while the row said "Python — 2
      Years 1 Month" (`naukri_profile/changes.yaml:120-123`). **His years are his
      facts — derive each one from a datable event, do not round to fit a
      headline you already wrote.**
- [ ] **7. Write every skill you want interrogated into an experience bullet, a
      project write-up or the professional summary.** A skill that appears only
      in a skills list scores Moderate; narrative scores Strong
      (`naukri/interview/skills.py:96-99, :125-140`). The same asymmetry runs
      through the job scorer: the skills component reads 7 profile fields, the
      title component only 3 (`naukri/jobs/config.py:130-149`).
- [ ] **8. Make the designation carry the words that appear in target job titles
      — and only a title an employer would confirm.** 44.4% of postings carry
      "Automation" in the title, 30.9% "QA", 11.7% "SDET"
      (`naukri_profile/changes.yaml:150-153`). "(SDET)" was additive and honest
      there because the Career Profile already declared that job role. **Do not
      add "Senior" or "Lead" unless his employment record says so.**
- [ ] **9. Set the total-experience header explicitly.** Naukri does not derive
      it from the employment entries, so adding past roles buys no visibility
      until it is updated (`scripts/set_total_experience.py:1-5`). **Needs his
      real total.**
- [ ] **10. Never treat a clicked Save as a landed edit.** Naukri signals a
      rejected save by leaving the dialog open, not by erroring. Wait for the
      dialog's own input to disappear, then re-scrape with `--extract`
      (`naukri/apply.py:147-167`).
- [ ] **11. Refresh once a day, and take a performance reading before the rewrite
      and again a fortnight later.** More than one refresh a day buys nothing
      measurable (`naukri/refresh.py:50-55`), and judging edits needs the *action
      rate*, not the appearance count (`README.md:174-176`).

---

## 2. How Naukri actually surfaces a profile

### The cut is where the effort gets wasted

> **The profile summary is stored to ~1000 characters and displayed to ~285.**
> Everything past character 285 is collapsed behind "Read More" and is read only
> by a recruiter who has *already* decided to open the profile. Those two numbers
> are different budgets, and treating the 1000 as the real one is the single most
> common way to waste a rewrite.
>
> Source: `naukri_profile/changes.yaml:62-63` ("truncates this behind a
> \"Read More\" at 285 characters, measured from this profile's own scrape");
> `naukri/apply.py:651-656`, which prints the split as `VISIBLE:` / `hidden :`
> during a dry run; `naukri/selectors.py:207` for the 1000.
>
> **Confidence caveat:** 285 rests on one account's scrape, and two of the three
> places that state it hedge ("~285", "around 285"). Treat it as a budget, not a
> platform constant — and use the dry-run preview rather than counting by hand.

The same trap exists on the resume side, in a different form: only the first
**4,200 characters** of the generated `.txt` reach any model prompt, and the cut
is silent (`naukri/interview/profile.py:152, :174-177`). On the source project's
own resume that meant 2,867 characters dropped — all 8 project write-ups, both
certifications and the education line never reached a prompt (measured by calling
`brief(profile.load())` during the audit).

### Field limits and caps

| Field | Cap | Enforced where | What happens past it |
| --- | --- | --- | --- |
| `resume_headline` | **250 chars** (hard) | `naukri/selectors.py:207`; refused before typing at `naukri/apply.py:726-729` | Naukri "silently truncates or blocks the save" (`selectors.py:206`); the tool refuses first |
| `profile_summary` | **1000 chars** stored | `naukri/selectors.py:207` | Same silent truncate/block |
| `profile_summary` | **~285 chars** visible | `naukri/apply.py:654-656` prints the split | Collapsed behind "Read More" — invisible in result lists |
| Key skills | **22 chips** (free account) | observed: `naukri_profile/changes.yaml:22-26`; guarded at `naukri/apply.py:298-312` | The 23rd is accepted by the suggester and **no chip appears**. Naukri reports success |
| Certifications | **1 row per run** | `naukri/apply.py:539-542` | A 3-row batch writes one and reports success unless guarded |
| Year dropdowns | options back to **1940** | `naukri/selectors.py:225`; `naukri/apply.py:425` | Text matching on these is unsafe; they are `droope` pickers, not free text |
| Uploaded resume file | **2 MB** | `naukri/resume_file.py:53-55` (fires before the browser opens) | Upload refused; the stale attached file stays live |

### Filter fields vs free text

- **Taxonomy fields** (key skills): the suggester decides the vocabulary. Type
  your preferred wording and you get nothing. `"REST API"` was refused and the
  run logged the six spellings Naukri *does* offer — Rest API Testing, Rest API
  Automation, Rest API Design, Rest API Services, Rest API Javascript, Rest API
  Development (`naukri_profile/changes.yaml:16-20`).
- **Exact match only.** The applier requires a case-insensitive exact match on
  the suggestion (`naukri/apply.py:364-366, :392`). Taking the top row quietly
  claims a skill nobody asked for *and* burns one of 22 capped slots.
- **Chips are created by clicking, not by Enter.** And anything left in the input
  box is committed as a junk chip on Save, so clear it first
  (`naukri/selectors.py:345-347`; `naukri/apply.py:313-314`).
- **Numeric filter fields.** IT-skills rows carry a years value, and the repo
  treats that as a recruiter filter surface: *"recruiters filter IT skills by
  years, so a row claiming 2y of Python excludes the profile from every 'Python
  4+ years' search no matter what the headline says"*
  (`naukri/selectors.py:245-247`). *That filter is asserted in three files and
  measured in none* — but a profile that contradicts itself on years is
  indefensible either way, so keep them consistent.
- **The total-experience header is its own control**, not a sum of the employment
  entries (`scripts/set_total_experience.py:1-5, :23-28`). After adding past
  employment, set it, "or the additions buy you no visibility at all"
  (`scripts/README.md:49-52`).
- **Career Profile job role** is a separate declaration and is the honest home
  for a title you will not put in the designation
  (`naukri_profile/changes.yaml:155-156`). That it is independently searchable is
  asserted (`scripts/career_profile.py:1-6`), not shown.

### Editing safely

| Trap | Rule | Source |
| --- | --- | --- |
| A rejected save looks identical to a successful one | Wait for the dialog's input to go hidden (12,000 ms), then re-`--extract` | `naukri/apply.py:147-156, :164-167` |
| "Add employment" is an identical-looking blank form whose Save creates a **duplicate job** | Edit the designation only through the pencil anchored to `span.truncate.emp-desg`, and gate it on the current value with `expect` | `naukri/selectors.py:321-329`; `naukri/apply.py:598-603` |
| "Add details" on an existing IT skill adds a **second row** with different years | Open the row's own pencil | `naukri/selectors.py:273-276`; `naukri/apply.py:511` |
| An empty Certifications section has no edit pencil at all | Reach it through the "Add" anchor beside the label; a `following::a` walk leaves the card and opens Career Profile instead (which is what happened on the first attempt) | `naukri/selectors.py:294-298` |
| The "Quick links" sidebar repeats every section name, so `following::` walks grab the wrong card's icon | Anchor every lookup to the section's visible heading and its **siblings**, never to document order | `naukri/selectors.py:127-133`; `naukri/extract.py:63-67` |
| Lazy widgets and collapsed blocks return the wrong string | Scroll the whole page, expand every "Read More", read visible text nodes only — an edit pencil is literally the string `editOneTheme`, which is how `resume_headline` once came back as `"editOneTheme"` | `naukri/extract.py:170-177, :136-139, :31-35` |

### The refresh and measurement loop

- **Refresh once a day, as a real but invisible edit.** `refresh.py` toggles a
  trailing full stop on the headline — "a real change, invisible in practice"
  (`naukri/refresh.py:29-32`). Expect the headline length to oscillate by one
  character; that is the fingerprint of the refresh, not drift.
- **Stop after the day's first refresh.** The last-modified timestamp appears to
  be date-granular, so the second and third runs "change nothing a recruiter
  search can see" (`naukri/refresh.py:50-55`); the limit is enforced in code
  because `jobs_scan_and_prep.bat` calls refresh three times. The source
  project's `data/refresh_log.json` shows 2-5 runs on each of 16 separate days
  before the limit existed — exactly that waste.
- *Why refresh at all* is an assertion: "recruiter search ranks heavily on when a
  profile was last modified" (`naukri/refresh.py:3-10`) is repeated in two files
  and measured in none. It costs one command a day, so do it — but do not claim
  it as a measured gain.
- **Judge content edits on the action rate, not on appearances.** "Appearances
  rising on a flat action rate means the profile is being found on weaker matches
  — the action rate is the number to watch" (`README.md:174-176`;
  `naukri/perf.py:13-15, :99`).
- **Take a reading before a rewrite and about a fortnight after**
  (`README.md:176-177`). Reading it back the same day tells you nothing: the
  source project's `data/performance.json` holds exactly two rows, 21 minutes
  apart, both 1,677 appearances / 87 actions / 5.19%. **The source rewrite has no
  measured outcome yet.** Anyone claiming this approach moved a number is
  claiming more than the data says.

---

## 3. The demand table

This is the centrepiece, and the only part of this playbook that is measured
market data rather than someone's opinion about resumes.

**Sample:** 1,539 unique postings scraped between **2026-08-21 and 2026-09-11**
(`naukri_profile/changes.yaml:28-29`). Independently reproduced during the audit
of this playbook: 20 files under `naukri_profile/data/jobs/results-*.json`, 1,594
rows, 1,539 unique by `job_id` (764 Naukri + 775 LinkedIn) — exact match.

> **These figures are QA/SDET-market specific and are already stale by the time
> you read this.** They describe what QA automation recruiters typed in a
> three-week window in 2026. If Prashant is in any other field, every number
> below is decoration. Re-measure (command at the end of this section).

### Three denominators, not one

Do not merge these into a single ranking. The source file's blanket definition
(`changes.yaml:34-35`) does not describe how each figure was actually computed:

| Metric | Denominator | Which figures use it |
| --- | --- | --- |
| Title share | all **1,539** titles | the target-title table below |
| Exact recruiter skill tag | only the **745** postings that carry a tags array | Automation Testing 324, Software Testing 194 |
| Title + tags + JD text | JD text exists on only **764** postings | SQL, BDD, Jira, Postman, GitHub Actions, Grafana, ISTQB |

So Automation Testing's 324 is 21.1% of all postings but **43.5% of postings that
carry tags at all** (computed over the reproduced corpus). Quoting one percentage
for it is misleading in both directions.

### Keyword demand, ranked

| Term | Count | Share | Metric | Verdict on the source profile |
| --- | --- | --- | --- | --- |
| Automation Testing | **324** | 21.1% of 1,539 / 43.5% of tagged | exact tag | added — the single most common recruiter tag in the sample |
| Software Testing | **195** (recounts 194) | ~12.7% | exact tag | added |
| SDET | **180** | **11.7%** | title | added, and put in the designation |
| SQL | **147** | 9.6% | title+tags+JD | added (the file's figure correctly excludes MySQL/NoSQL/PostgreSQL; a loose substring gives 156) |
| BDD (counted with Cucumber) | **134** (recounts 132) | 8.7% | union | added (BDD alone is 103) |
| Jira | **86** | 5.6% | title+tags+JD | added |
| Manual Testing | **85** | 5.5% | title+tags+JD | on the profile; named as droppable |
| Postman | **84** | 5.5% | title+tags+JD | added |
| GitHub Actions | **74** | 4.8% | title+tags+JD | added |
| Test Strategy | **33** | 2.1% | title+tags+JD | on the profile; named as droppable |
| Functional Testing | **28** (recounts 29-30) | 1.8% | title+tags | wanted, **hit the 22 cap, never landed** |
| Regression Testing | **24** | 1.6% | title+tags | wanted, **hit the 22 cap, never landed** |
| Defect Management | **24** | 1.6% | title+tags+JD | **removed** |
| ISTQB | **23** | 1.5% | title+tags+JD | measured during the audit; see section 7 |
| Grafana | **8** | 0.5% | title+tags+JD | **removed — the weakest of the 16 pre-rewrite key skills** |
| "Computer Vision" | **2** | 0.13% | title+tags+JD | removed from the headline |
| VMS / ITMS / FRS / Video Analytics / ICCC | **0 each** | 0% | title+tags+JD | removed from the visible summary prefix |

Sources: `naukri_profile/changes.yaml:44-48, :101-113`. Every count above was
re-derived from `data/jobs/results-*.json` during the audit; Grafana 8, Defect
Management 24, Jira 86, Postman 84, GitHub Actions 74, SQL 147, Test Strategy 33,
Manual Testing 85 and the five zero-demand acronyms reproduced **exactly**.
Software Testing came back 194 not 195, Functional Testing 29-30 not 28, and
BDD∪Cucumber 132 not 134 — one- and two-posting discrepancies, immaterial.

### Target-title tokens (denominator: all 1,539 titles)

| Token | Count | Share |
| --- | --- | --- |
| Automation | 682-683 | **44.4%** |
| QA | 475 | **30.9%** |
| Senior (incl. Sr / Sr.) | 268 | **17.4%** |
| SDET | 180 | **11.7%** |

Source `naukri_profile/changes.yaml:150-153`. One correction from the audit: the
17.4% figure only reproduces if `Sr`/`Sr.` are counted as Senior. The literal
word "Senior" is **211 postings = 13.7%**. It changes nothing operationally,
because Senior was excluded from the designation on honesty grounds regardless —
but the number is looser than the file states.

The old designation contained **none** of these four tokens
(`changes.yaml:152-153`). That is the cheapest single fix on this list.

### Re-measuring for a different field

There is **no built-in demand-report command** — the source figures were counted
by hand over the scan output. The scan itself is what produces the corpus:

```
python main.py --jobs                    # dry run, sends nothing
                                         # writes data/jobs/results-<date>.json
python main.py --jobs-export --top 30    # also writes results-<date>.json
```

Run the scan for a week or two first; one day is a sample of 60-odd postings, not
a market. Then count over whatever has accumulated:

```python
# demand.py - run from the project root: python demand.py "automation testing" sql jira
import json, re, sys, glob

TERMS = sys.argv[1:]
rows, seen = [], set()
for path in sorted(glob.glob("data/jobs/results-*.json")):
    blob = json.loads(open(path, encoding="utf-8").read())
    for board in ("naukri", "linkedin"):
        for job in blob.get(board) or []:
            key = job.get("job_id") or job.get("url")
            if key in seen:
                continue
            seen.add(key)
            rows.append(job)

print(f"{len(rows)} unique postings")
for term in TERMS:
    pat = re.compile(rf"\b{re.escape(term.lower())}\b")
    title = sum(1 for j in rows if pat.search((j.get("title") or "").lower()))
    tag = sum(1 for j in rows
              if term.lower() in [s.lower() for s in (j.get("skills") or [])])
    mixed = sum(1 for j in rows if pat.search(" ".join([
        j.get("title") or "", " ".join(j.get("skills") or []),
        j.get("description") or ""]).lower()))
    print(f"{term:<24} title {title:>4}  exact-tag {tag:>4}  "
          f"title+tags+JD {mixed:>4} ({mixed / max(len(rows), 1):.1%})")
```

Report all three columns, not one. Run against the source project's corpus
restricted to 2026-08-21..2026-09-11, this script reproduces 1,539 unique
postings, Automation Testing 324 exact tags, SQL 147 (9.6%), Jira 86 (5.6%),
Postman 84 (5.5%), GitHub Actions 74 (4.8%) and Grafana 8 (0.5%) — verified
during the audit of this playbook, which is why it is printed here rather than
described.

---

## 4. Where a skill must be written, and why

The toolkit grades every skill into a tier, and **where you wrote it decides the
tier**. This is the rule that dictates resume structure.

| Tier | How it is earned | Consequence |
| --- | --- | --- |
| **Strong** | the skill appears in the resume's *narrative* — experience bullets, project write-ups, or the professional summary — **or** carries 3+ stated years | full weight; interview prep generates experience-level questions on it |
| **Moderate** | found only in a skills list, the Naukri key-skills or IT-skills tables, or elsewhere in the resume file | "a claim you have made, not one you have described" |
| **Gap** | not found at all | top of the study list |

Source: `naukri/interview/skills.py:96-99, :125-140`.

**Narrative sections** are matched by heading: `PROFESSIONAL SUMMARY,
PROFESSIONAL EXPERIENCE, KEY PROJECTS, WORK EXPERIENCE, EXPERIENCE, PROJECTS,
SUMMARY` (`naukri/interview/profile.py:30-33`). **List sections:** `TECHNICAL
SKILLS, SKILLS, TOOLS, TECHNOLOGIES` (`:34`). A heading matching neither tuple is
scored as neither — on the source resume, `CERTIFICATIONS & CONTINUOUS LEARNING`
and `EDUCATION` both fall in that third bucket (verified by re-running
`_split_sections` on the real file).

### What this means for resume structure

1. **PROFESSIONAL SUMMARY is Strong-evidence real estate.** A skill named only
   there scores Strong, exactly like a bullet — the cheapest promotion available,
   with no invented bullet. Conversely, an adjective-only summary wastes it.
2. **A skills list can never do better than Moderate**, however well grouped. So
   the skills list is for recruiter keyword-scanning; the bullets are for tier.
3. **Name the specific tool in a bullet if you want to be questioned on it.**
   Tiers are computed per canonical lexicon row with all aliases folded together
   (`naukri/interview/skills.py:18-19, :101, :110-117`), so a Strong on "AI /
   LLM" can be earned entirely by the alias `llm` while the literal `langchain`
   appears nowhere in the narrative (measured on the source profile).
4. **Do not manufacture Strong with a years number.** `skill_years >= 3` in
   `jobs.yaml` flips the tier with no supporting sentence anywhere
   (`naukri/interview/skills.py:125`; re-run on an empty profile: 3.0 →
   `('strong', '3 years stated')`). The prep then generates experience-level
   questions for something he never wrote down. **Prashant's `skill_years` are
   his facts; this project ships `skill_years: {}` (`jobs.yaml:171`) on purpose,
   and an empty value queues the question for him instead of answering it.**
5. **A "currently studying" line makes an aspiration Moderate, not a Gap** — and
   its study weight drops from 1.0 to 0.6 (`naukri/interview/skills.py:133,
   :137, :207`), so the thing he most needs to revise sinks in his own revision
   list.
6. **Order sections by what you want read.** Only the first 4,200 characters
   reach a prompt (`naukri/interview/profile.py:152`), and on the source resume
   the cut landed on the `KEY PROJECTS` heading itself.

---

## 5. Resume format rules

### What the generated `.docx` does, and why

Everything is **single-column body paragraphs** — no tables, text boxes,
multi-column layouts, headers/footers, images or icon fonts. The builder's stated
reason: "ATS parsers read a Word file as a linear stream of paragraphs. Anything
that breaks that stream ... either scrambles the reading order or is dropped
outright" (`resume/build_resume.py:8-14`).

| Choice | Value | Source |
| --- | --- | --- |
| Section rules | paragraph bottom border (`w:pBdr`), not table edges | `resume/build_resume.py:109-119` |
| Bullets | literal `"•  "` run, 0.18in hanging indent — **not** Word list numbering ("often stripped") | `:134-140` |
| Dates | inline in the org line, joined with a pipe — never a right-hand column or tab grid | `:15-16, :198-199` |
| Project lines | `Label: description`, label **first** and bold — "an earlier version lost this: they parsed *after* their own descriptions" | `:216`, docstring `:11-12` |
| Body font | Calibri 10pt, `#1A1A1A`, line spacing 1.05 | `:94-100` |
| Margins | 0.5in top/bottom, 0.6in left/right | `:103-106` |
| Headings | ALL CAPS, bold, 11pt, `#1F3A5F`, with a bottom rule | `:122-130` |
| Required keys | top level: `name, title, summary, experience`; per job: `title, org, dates, bullets` (`loc` is the only optional key) | `:57-69`; `resume/resume.example.yaml:51` |

> **Honest caveat, stated because it changes how much weight these deserve:** the
> repo contains **no ATS parser, no `.docx` parse test and no fixture**
> demonstrating any of the parser claims above. `tests/` holds only
> `test_answers.py`, `test_apply_config.py`, `test_interview.py`,
> `test_roles.py`, and nothing in it mentions `docx` or `ATS` (verified). The one
> cited data point — the lost project labels — survives only as a docstring
> anecdote. **Follow these as house convention; do not cite them as proof, and do
> not let them override a formatting change a real recruiter asks for.** Calibri,
> the margins, the line spacing and the heading colour are density and rendering
> choices, not ATS requirements.

### What genuinely breaks it

These are parsed by code in this repo, so they are mechanics rather than
convention:

| Break | What happens | Source |
| --- | --- | --- |
| **An ALL-CAPS line inside a section body** — an all-caps employer, job title, or an acronym-only line | It passes the heading test and opens its own section. The bullets under it stop being narrative and lose Strong. Re-run confirmed: an all-caps org line swallows the bullet that follows it | `naukri/interview/profile.py:55-61` |
| **The same heading twice** (e.g. splitting experience into "relevant" and "other") | The second occurrence **overwrites** the first; the earlier body is gone with no warning | `naukri/interview/profile.py:62-67` |
| **A renamed heading** (`CORE COMPETENCIES`, say) | Matches neither tuple, so nothing under it can reach Strong. "Renaming a heading here quietly downgrades your own evidence" | `resume/build_resume.py:245-248` |
| **A compound heading** (`SKILLS SUMMARY`) | Counted in *both* buckets, silently promoting a comma-separated list to Strong | `naukri/interview/profile.py:111-114` |
| **A second `*Resume*.txt` in `resume/`** | The loader takes the **alphabetically first** match, not the newest — `Old_Resume.txt` wins, and `resume/*.txt` is gitignored so nothing looks wrong | `naukri/interview/profile.py:43-45` |

Heading detection is five tests, all of which must pass: non-empty, under 60
characters, equal to its own `.upper()`, containing a run of 3+ capitals, and not
starting with `-` (`naukri/interview/profile.py:55-61`). Bullets, project lines
and certification lines are prefixed with `- ` automatically; the lines emitted
**bare** are the job title, the org line, the skill-group lines, the summary and
the education line — so those five are where the all-caps hazard lives.

Two scope notes so you do not chase ghosts: the builder emits its six headings
from hardcoded strings, so you cannot cause a duplicate, compound or renamed
heading *from `resume.yaml`*. All-caps body lines you can (an all-caps org or job
title). The worked source resume already trips the rule once harmlessly: because
the name line is ALL CAPS, it opens a spurious section, and the keyword-dense
positioning line beneath it is verifiably **not** part of the narrative.

### What Naukri's own parser overwrites on upload

Five fields are treated as at risk: `resume_headline`, `profile_summary`,
`key_skills`, `it_skills`, `current_designation`
(`naukri/resume_file.py:30-32`). The module's stated reason: "Naukri re-runs its
resume parser on upload, and the parser can overwrite fields that were set by
hand ... so a silent rollback of a careful edit shows up as output rather than as
a mystery three weeks later" (`:3-7`).

**Operating procedure:** upload deliberately, read the clobber diff, re-apply
`changes.yaml` for anything undone (`naukri/resume_file.py:155-156`).

Three things to know about that diff before trusting it:

- *"No parser damage"* compares **five fields only**, only against the **last
  saved extract**, and its comparison **forgives truncation** — one side
  prefixing the other counts as unchanged (`:57, :92-95, :105-121, :159`). A
  rewrite that merely shortens a field reports as clean.
- The prefix leniency exists for a good reason: a summary captured while still
  collapsed behind "Read More" would otherwise report as rewritten on every
  upload and bury real damage in noise (`:105-121`). Do not read a
  prefix-ending-in-`...` difference as parser damage.
- **"on every upload" is not established anywhere.** `:30` says the parser is
  "known to rewrite" these, unattributed, and the repo contains no captured
  clobber report showing a rewrite ever fired. Follow the procedure; do not
  repeat the claim as fact.

Two file-level gotchas:

- **2 MB ceiling**, refused before the browser opens (`:53-55`).
- **Re-export the PDF after every build.** `default_resume()` picks purely by
  modification time — the docstring says "preferring PDF" and the code has no
  format preference at all (`:36-42`) — and `build_resume.py` never writes a PDF
  (`:237-238, :284-285`). A fresh build makes the `.docx` newer, so the next
  upload silently changes which format Naukri's parser sees. Nothing checks.

Finally: `resume.yaml` and every generated output are gitignored, because a
resume is personal data (`resume/build_resume.py:3-4`;
`resume/resume.example.yaml:6-8`; `.gitignore:35-44`). Only the template is
tracked. Keep it that way.

---

## 6. What the scoring model rewards

This is the job-matching scorer, not Naukri's ranking. It decides which postings
the agent surfaces and applies to, so it is worth knowing which resume surfaces
feed which component.

| Component | Range | Formula | Source |
| --- | --- | --- | --- |
| Skills | 0-45 | `round(45 * (0.65 * ratio + 0.35 * depth), 1)`, `depth = min(matched / 8, 1.0)`; flat **18.0** if the posting lists no tags | `naukri/jobs/score.py:100-104, :81-82` |
| Title | 0-25 | `20 * (job-title tokens present in your target set / job-title tokens)`, **+5** if the *job's* title carries a seniority word | `:112-122` |
| Experience | 0-15 | inside band 15; under-qualified `15 - 6.0/year`; over-qualified `15 - 2.5/year`; unknown 9.0 | `:126-136` |
| Location | 0-10 | `remote` substring 10; preferred-location substring 10; blank 5; anything else **2** | `:139-148` |
| Freshness | 0-5 | ≤2 days 5.0; ≤7 days 3.0; ≤30 days 1.0; older 0; unknown 2.5 | `:151-161` |

### What that implies for the resume and profile

1. **The two components read different fields.** The skills component searches
   `profile_evidence` — 7 fields: headline, summary, designation, career profile,
   **employment, projects**, IT skills (`naukri/jobs/config.py:141-149`). The
   title component's target set is `profile_text` — only 3: headline, summary,
   designation (`:130-133`). On the source profile that is 224 tokens versus 52.
   So: **tools go in employment and project write-ups; role words go in the
   headline trio.**
2. **Breadth beats depth past 8 tags.** On a 10-tag posting each of the first 8
   matches is worth 4.89 points and the 9th and 10th only 2.92 — a 40% drop
   (computed from `:100-104`). Nothing penalises more than 8; the marginal value
   just falls.
3. **Acronyms fold symmetrically.** `_norm` applies the pack's synonyms to the
   job text *and* to your profile text, so "SDET" in the headline folds to
   "software development engineer in test" on both sides. A job titled bare
   "SDET" scores a perfect 20.0 title points against the source config; "Senior
   SDET" scores 25.0 (verified by running `_title_score`).
4. **5 of the 25 title points are unreachable from your resume.** The seniority
   bonus fires on words in the *job's* title (`:33, :120-121`), so your
   profile-controlled ceiling is 20.
5. **Aim at or below his band, never above.** Being short of the stated minimum
   costs 6.0/year; being over the top costs 2.5/year — a 2.4x asymmetry
   (`:134-136`). And the stated total experience is the **only profile-derived
   hard reject**: when a posting's minimum exceeds his years by more than 2.0,
   the score is forced to 0 before any component runs (`:70-73`;
   `jobs.yaml:66`). **His years — do not guess them to widen the funnel.**
6. **Mention a skill once.** Both matchers are presence-only; repetition earns
   nothing (`naukri/interview/skills.py:72-77`; `naukri/jobs/score.py:97`).
   Keyword stuffing is invisible to this model.
7. **Budget against the 30-point non-resume floor.** Experience + location +
   freshness cap at 30, leaving 70 from skills + title. This project's scaffold
   sets `auto_apply_min_score: 78` and `review_min_score: 55`
   (`jobs.yaml:60-61`) — stricter than the source project's 72. Arithmetic on a
   10-tag posting with perfect experience/location/freshness: with a full
   20-point title, 6 of 10 tags reaches 79.4 and 5 reaches 74.5; **with a 0-point
   title, a fully-matched 10-tag posting maxes at 75.0 and cannot auto-apply at
   78 at all.** Title coverage is worth roughly four matched skill tags.
8. **`must_have_any` and the pack's title seeds are matched against the *job's*
   title, tags and description** (`:66, :112-115`) — they are a posting filter
   fixed by the pack. Nothing written in a resume can "pass the gate" or add a
   gate token. Do not let anyone sell you resume advice on that premise.

---

## 7. What was tried and refused

Skip this section and you will repeat it.

### Keywords that turned out to be dead

| Term | Measured demand | What it cost |
| --- | --- | --- |
| VMS, ITMS, FRS, Video Analytics, ICCC | **0 of 1,539 each** | They occupied the *only visible characters* of the summary — the prefix a recruiter reads in a result list (`naukri_profile/changes.yaml:64-66`) |
| "AI & Computer Vision Products" | full phrase 0; "Computer Vision" 2 postings (0.13%) | headline characters (`changes.yaml:44-45`) |
| Grafana | 8 (0.5%) — genuinely the weakest of 16 key skills | one of 22 capped slots (`changes.yaml:101`) |
| Defect Management | 24 (1.6%) | one slot; removed as "already covered by the employment text" — though the employment text says "end-to-end defect lifecycle in ClickUp/GitHub", not the chip phrase, so an exact-phrase search no longer hits a chip |

In-house product names and client names are not worthless — they give context to
a recruiter who has already opened the profile. They belong **after** the ~285
cut, "where they still give a recruiter who opens the profile the context without
costing the snippet anything" (`changes.yaml:71-72`).

### Taxonomy refusals

- `"REST API"` → refused. Naukri offered: Rest API Testing, Rest API Automation,
  Rest API Design, Rest API Services, Rest API Javascript, Rest API Development
  (`changes.yaml:16-20`). Use the offered spelling.
- Typing `"Git"` surfaces `"Github"` at the top of the suggester
  (`naukri/apply.py:364-366`). Accepting the first row claims a skill nobody
  asked for.
- Pressing Enter does **not** create a chip; only clicking a suggestion does. And
  leftover text in the input becomes a junk chip on Save
  (`naukri/selectors.py:345-347`).

### Field caps that silently swallowed entries

- **Regression Testing (24 postings) and Functional Testing (28) were reported as
  added on 2026-09-12 and never appeared.** The account was already at 22 chips.
  Naukri's suggester accepted both and reported success
  (`changes.yaml:22-26`). The post-add chip verification at
  `naukri/apply.py:298-312` exists *because of* that run. Note the code only
  infers the cause ("most likely Naukri's key-skill cap (%d chips) is reached"),
  so 22 is an observed ceiling, not a documented platform limit.
- **The documented trade, if two slots are needed:** drop Test Strategy (2.1%)
  and Manual Testing (5.5%) (`changes.yaml:25-26`). Manual Testing is the safer
  drop on the source profile because the word appears nowhere in that resume
  (0 grep hits) — and a keyword you cannot evidence is one you should not claim.
- **Certifications write one row per run** (`naukri/apply.py:539-542`). A
  three-row batch writes one and, unguarded, reports success.
- **`--extract` on an unscrolled page misses sections entirely** and returns
  collapsed text for the two blocks worth the most analysis
  (`naukri/extract.py:136-139, :170-177`).

### Claims that did not survive measurement

- **ISTQB.** `changes.yaml:172-175` calls it "one of the few certifications
  recruiters actually filter QA candidates on". Measured for the first time
  during the audit: **23 of 1,539 postings (1.5%)** mention ISTQB; any `certif*`
  mention appears in 56 (3.6%); and across the 10 scored JDs in the
  interview-prep sample, *zero* mention a certification
  (`naukri_profile/docs/interview-prep-gaps.md:207`). 1.5% is Defect-Management
  tier. So: **do not spend a key-skill slot on a certification, and do not repeat
  the filtering claim.** Listing it in the Certifications section is separately
  free — it costs none of the 22 slots — but needs **a real completion month and
  year, which is his to supply**; the fields are dropdown pickers, not free text
  (`naukri/selectors.py:310-313`), and the source file left the entry commented
  out with `MM`/`YYYY` placeholders rather than guessing.
- **"Stakeholder communication" as a skills gap.** The interview matrix
  top-billed it as absent from the resume (High importance, 5 of 10 JDs) while
  the resume plainly evidenced it — "team of 8", "code review", "mentored junior
  QA engineers", "acceptance criteria ... with ML teams". The cause is lexical:
  the four trigger tokens (`stakeholder`, `cross-functional`, `cross functional`,
  `client communication`) genuinely return 0 grep hits
  (`naukri_profile/docs/interview-prep-gaps.md:136-145`). **Close a naming gap
  like this in prose, not by adding a skill.** The pill will recur daily; it is
  not a reason to edit a profile.
- **The "JD Coverage" badge on the interview-prep page.** 62 of 271 checkable
  citations — **22.9%**, across 51 of 100 questions — cite a JD that does not
  contain the skill, and reused questions score on a different, incompatible rule
  (fresh questions average 2.95/10, relinked ones 8.08/10)
  (`docs/interview-prep-gaps.md:59-68`). Do not use it as demand evidence.
- **`tight_terms` protects nothing.** Every pack declares it and the matcher
  loads it, but it is never used in any matching decision — 18-33 inert entries
  per pack (`naukri/interview/skills.py:44-45, :52-58`).
- **`jobs.yaml skill_years` silently overrides the IT-skills table.** The profile
  table is read first, then the hand-written numbers overwrite it, and the
  answer's provenance string still says "IT-skills table: <skill>" whatever the
  source (`naukri/jobs/answers.py:116-131, :368-370`; proved by
  `tests/test_answers.py:118-123`). On the source project five entries
  contradicted the live table, so a questionnaire answered "2 years Python" and
  attributed it to a table that said 4. **If you fill `skill_years` for Prashant,
  keep it identical to his IT-skills rows, or the stale number wins and gets
  quoted to a recruiter in his name.**

### Two contradictions inside the source repo — do not resolve them by guessing

- **Which field carries the most weight is unknown.** `changes.yaml:88` calls key
  skills "the field Naukri weights most heavily for keyword matching";
  `README.md:121` calls the resume headline "the single highest-leverage field".
  Both are unsourced assertions by the same author. Fill both properly and claim
  neither ranking.
- **"Earlier key skills weigh more in matching"** is asserted in three files and
  measured in none. Order the `add` list by demand anyway — not because position
  is known to carry weight, but because adds are applied in order and the cap
  eats the tail (`changes.yaml:91-93`).

---

## 8. Applying this to a new person

An ordered procedure, ending where the resume is built and uploaded. Steps marked
**HIS FACTS** cannot be guessed, inferred from the source project, or filled with
a placeholder that later reads as a claim.

1. **Get the raw material.** His current resume, his employment record (titles as
   the employer would confirm them, with start/end months), his projects with
   dates and any public links, his certifications with completion months.
   **HIS FACTS — all of it.**
2. **Decide the role pack** (`python main.py --roles` lists the four). Set
   `role:` in `jobs.yaml`. If his field is not QA automation, trim the lexicon
   categories he does not work in — the packs themselves instruct this
   (`roles/developer.yaml:7-9`; `roles/cybersecurity.yaml:5-7`).
3. **Re-measure demand.** Run `python main.py --jobs` (dry run) daily for a week
   or two, then count terms over `data/jobs/results-*.json` with the script in
   section 3. **The QA table in section 3 does not transfer.** Produce his own
   ranked list before writing a single field.
4. **Write `resume/resume.yaml`.** Required: `name, title, summary, experience`,
   and per job `title, org, dates, bullets` (`loc` optional). Keep his payroll
   title in the experience block, where a background check will look for it, and
   use `title` as the positioning line (`resume/resume.example.yaml:21-23`).
   **HIS FACTS: every date, every number in a bullet, every year count.** No
   all-caps org or job titles (section 5).
5. **Place keywords by tier, not by volume.** Anything he wants asked about goes
   into a bullet, a project description or the summary — that is Strong. The
   skills list is a keyword surface only (section 4). Every keyword must be one
   he can defend; that is the constraint, not a style preference.
6. **Build it:** `python resume/build_resume.py`. It refuses loudly rather than
   emitting a plausible-looking resume with no jobs on it
   (`resume/build_resume.py:57-69`). Then **export the PDF by hand** and check it
   is newer than the `.docx` (section 5).
7. **Sanity-check the parse before trusting any tier.** Confirm the `.txt` splits
   as expected — headings classified, no stray ALL-CAPS section, one
   `*Resume*.txt` in `resume/` — and remember only the first 4,200 characters
   reach a prompt, so order sections accordingly.
8. **`python main.py --login`** — a real browser opens; he signs in himself.
9. **`python main.py --extract`** — scrapes his live profile into `data/`. This is
   the baseline. Write nothing to the profile before this exists.
10. **`python main.py --perf --note "baseline before rewrite"`** — take the
    reading *now*, because the comparison is worthless if you take the first one
    after the edits (`README.md:176-177`).
11. **Write `changes.yaml` against the extracted profile**, in this order of
    leverage: designation → headline (≤250) → summary (front-load the ~285) → key
    skills (≤22, ordered by *his* demand table, exact suggester spellings) → IT
    skills (one row per filterable skill). **HIS FACTS: the designation must be a
    title his employer would confirm; every IT-skills years figure must derive
    from a datable event, and each derivation should be written next to it so it
    can be checked rather than trusted (`changes.yaml:125-136`).** Do not add
    "Senior" or "Lead" on the strength of the 17.4% title share.
12. **Dry-run it:** `python main.py --apply`. Read the `VISIBLE:` / `hidden :`
    split for the summary — that is the review step (`naukri/apply.py:651-656`).
    Fix the prefix, not the total length.
13. **Apply it:** `python main.py --apply --yes`. Then **`python main.py
    --extract` again** and diff. A save that was rejected leaves the dialog open
    and the old text live; a skill at the 22-chip cap reports success and adds
    nothing. Prove each edit landed.
14. **Set the total-experience header**
    (`python scripts/set_total_experience.py`) after any employment additions, or
    they buy no visibility (`scripts/README.md:49-52`). **HIS FACTS.**
15. **Add certifications one row per run**, only with real completion dates.
    **HIS FACTS — leave the entry out rather than approximate a date.**
16. **Upload the resume:** `python main.py --upload-resume`. Read the clobber
    diff, re-apply any of the five at-risk fields the parser undid, and remember
    the diff's reassurance is narrower than its wording (section 5).
17. **Then stop editing and start measuring.** One `--refresh` a day, no more.
    Re-run `--perf` about a fortnight after the rewrite and compare the **action
    rate**, not the appearance count. Until that second reading exists, this
    whole playbook is a well-grounded hypothesis about his profile, not a result.

---

*Provenance: every rule here survived an adversarial grounding audit of the
source project, in which line citations were re-opened, behavioural claims were
re-run, and the 1,539-posting demand corpus was recomputed from
`naukri_profile/data/jobs/results-*.json`. Rules the audit could not ground were
dropped rather than softened; rules resting on a single unsourced comment are
labelled as such in the text above. If you extend this file, keep that standard:
state the source inline, or state that there isn't one.*
