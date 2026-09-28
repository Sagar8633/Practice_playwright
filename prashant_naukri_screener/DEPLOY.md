# Moving this to another laptop

Five steps, two of which need a human at the keyboard. Budget fifteen minutes,
most of it waiting on a 150 MB browser download.

## On this machine — make the package

```powershell
powershell -ExecutionPolicy Bypass -File scripts\make_portable.ps1
```

Writes `prashant_naukri_screener_<date>.zip` (~0.4 MB) one level up. Copy it
across however you like — USB, email, Drive.

**Do not `git clone` instead.** Every file that makes this *his* setup is
gitignored: `jobs.yaml`, `changes.yaml`, `resume/resume.yaml`,
`scripts/profile_edits.yaml` and the built resume. That is the whole point of
the gitignore, and it means a clone gives you the tool with none of the person
in it. The zip carries them; a clone does not.

The zip deliberately leaves out `data/state.json`, which **is** the Naukri
login. Two machines holding one live session is not something to set up on
purpose, and it expires in a few weeks anyway. He signs in once at step 3.

## On the other laptop

**1. Unzip it anywhere.** `C:\naukri` is fine. Avoid OneDrive and Desktop
folders that sync — the browser writes into `data/` constantly and a syncing
folder will fight it.

**2. Run setup.**

```
setup.bat
```

Creates `.venv`, installs the dependencies, downloads Chromium, checks all four
personal config files arrived, runs the test suite, and prints the role packs.
If Python is missing it says so and stops. Needs Python 3.9+ with *Add Python to
PATH* ticked during install.

**3. Sign in. This one is his, not yours.**

```
.venv\Scripts\python.exe main.py --login
```

A plain Chromium window opens — no bookmarks, no extensions, not his usual
profile. **He must sign in inside that window.** A login in his normal Edge or
Chrome is invisible to this; the tool only sees cookies from the browser it
controls. Naukri will not recognise the machine, so expect a password and
probably an OTP. It captures the session by itself and closes. Fifteen-minute
window.

There is no password anywhere in this codebase and there is no way to supply
one. Naukri serves "Access Denied" to headless Chromium, so a real browser and
a real person are both required.

**4. Extract the profile.**

```
.venv\Scripts\python.exe main.py --extract
```

Writes `data/profile.json`. Nothing else runs without it — the job scanner
refuses to start rather than score against an empty profile.

**5. Schedule it.**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\schedule_hourly.ps1
```

Registers two tasks. Check with
`Get-ScheduledTask -TaskName 'Naukri*' | Format-Table TaskName,State`, remove
with the same script and `-Remove`.

---

## What the schedule actually does

| Task | When | What |
| --- | --- | --- |
| `NaukriHourlyScan` | 08:07, then every hour for 12h — 13 runs, last 20:07 | Searches, scores, writes the tracker page. **Sends nothing.** |
| `NaukriDailyRefresh` | 08:02, once | Bumps the profile's last-modified timestamp |

### Why the scan is hourly and the refresh is not

New postings appear through the working day and early applicants get read, so
scanning hourly is worth it. `--new-only` means each run reports only what no
earlier run has seen (tracked in `data/jobs/seen.json`), so you get twelve short
lists of genuinely new jobs rather than twelve copies of one list. Most runs
finding nothing is the correct result.

The refresh is the opposite case. `naukri/refresh.py` refuses a second bump the
same day, and its own docstring gives the reason: **the Naukri timestamp records
a date, not a time.** Runs two through thirteen change nothing a recruiter
search can see, while adding twelve more browser sessions and twelve more edit
requests against a live account. Scheduling it hourly would not error — it would
print *"Profile was already refreshed today; nothing to do"* twelve times.

If you want the profile edited more often than that, the lever is *what* the
profile says, not how often it is re-saved. That means the key skills and the
summary — and those should change when a demand measurement says to, not on a
timer. See `docs/RECRUITER_VISIBILITY.md`.

### The refresh already is the "small edit" trick

Worth knowing, because it is easy to reinvent: `refresh()` does not poke a magic
API. It opens the headline editor and **toggles a trailing full stop** on the
text, then saves. That is a real edit, which is what moves the timestamp. So the
"change a skill or a word in the summary to stay near the top" technique is
already implemented, already safe, and already capped at once a day.

---

## Things that will bite

**The laptop must be awake and signed in.** Both tasks run interactively because
a browser needs a desktop to draw into. Register-as-"whether user is logged on
or not" would fail every single run. A locked screen is fine; a sleeping laptop
is not.

For a machine that stays put and stays plugged in — a desk laptop left closed, a
spare PC, a mini-PC acting as the always-on box — add `-WakeToRun`:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\schedule_hourly.ps1 -WakeToRun
```

It is **off by default on purpose.** On a laptop that gets closed and carried
around, `-WakeToRun` wakes it in a bag thirteen times a day to open a browser
nobody is looking at: a hot laptop and a flat battery. It also cannot wake a
machine that is hibernated or powered off — nothing can.

---

## Can this run in GitHub Actions instead, so no laptop is needed?

No. Four separate things block it, and the third is the one that matters:

1. **Headless is blocked.** `main.py:292` — *"Akamai serves 'Access Denied' to
   headless Chromium."* Every Naukri command in this codebase passes
   `headless=False`. Actions runners are headless Linux containers. `xvfb` could
   supply a display and solve this half.
2. **The datacenter IP is the half `xvfb` cannot solve.** Actions runs on Azure
   IP ranges, and flagging datacenter traffic is most of what bot detection is
   for. Residential broadband is what the site expects.
3. **It would not remove the laptop anyway.** `data/state.json` IS the login.
   Running in Actions means storing it as a repo secret, and it expires every few
   weeks — refreshing it means running `--login` in a real browser on a real
   machine and re-uploading. The laptop stays required, just on an unpredictable
   schedule instead of a fixed one. That is worse, not better.
4. **Every personal file would have to move to GitHub.** `resume.yaml` carries a
   phone number and email, `jobs.yaml` carries a salary, `state.json` is a live
   session. This project's `.gitignore` exists precisely to keep those off a
   remote. Running in CI means deliberately reversing that decision.

There is also account risk: driving a job board from cloud infrastructure is a
good way to have the account restricted.

**What actually gives laptop-independence** is an always-on machine on a home
connection — an old laptop or a mini-PC, plugged in, auto-login on, running this
same `schedule_hourly.ps1 -WakeToRun`. The site sees an ordinary residential IP
and nothing else changes. RDP in every few weeks to re-run `--login`. A cloud
Windows VM works mechanically but brings back problem 2 and costs money.

The only parts of this repo that *could* honestly run in CI are the test suite
and `resume/build_resume.py`, neither of which touches a browser. Not worth a
workflow.

### What about Render, Railway, Fly.io, Heroku?

Same answer, and it is worth understanding *why* it is the same answer so the
next platform on the list does not cost another evening.

Problems 1, 2 and 3 above are not facts about GitHub — they are facts about
**every** container PaaS: a datacenter IP, no desktop session, and no durable
place to keep a login that has to be refreshed by a human in a real browser.
Moving between them changes nothing.

Render adds one of its own: **Cron Jobs run in ephemeral containers with no
persistent disk.** `data/state.json` is written at login and read on every run;
on Render it would not survive between runs. Persistent disks exist there but
cannot be attached to cron jobs, so you would end up paying for an always-on
web service impersonating a scheduler. Render's regions are also Oregon,
Frankfurt and Singapore — so the site would see an Indian job-seeker's account
being driven from a foreign datacenter, which reads as fraud rather than just
automation. And Chromium wants roughly 1 GB of RAM against a 512 MB free tier.

### Ranked, for when this comes up again

| Option | Works? | Cost | Notes |
| --- | --- | --- | --- |
| Mini-PC or old laptop at home | **Yes** | ₹10-15k once | Residential IP, real desktop, zero workarounds |
| Windows VM, Azure Central India / AWS Mumbai | Probably | ₹1,500-2,500/mo | Persistent disk, real desktop, RDP for `--login`. Still a datacenter IP, so it may get flagged |
| Render / Railway / Fly / Heroku / Actions | **No** | - | Datacenter IP, no desktop, no durable session |

The mini-PC is cheaper than the VM inside four months, sits on exactly the kind
of connection the site expects, and needs no workarounds - it runs
`schedule_hourly.ps1 -WakeToRun` unmodified.

### If it must be virtual: the spec

The VM is the ONLY virtual option that can work, and it works because it is a
real Windows desktop rather than a container. The five steps at the top of this
file run on it unchanged - no `xvfb`, no Docker image, no rewriting anything.

| | Requirement | Why |
| --- | --- | --- |
| OS | **Windows** Server 2022 or Win 11 | The toolkit is `.bat` + Task Scheduler + a browser that needs a desktop |
| RAM | **4 GB minimum** | Windows ~2 GB, Chromium ~1.5 GB. 2 GB thrashes |
| Disk | 30 GB+ | Windows ~20 GB, Chromium ~500 MB, plus `data/` growth |
| Region | **India** - Mumbai / Pune / Delhi | A foreign datacenter driving an Indian job-seeker account reads as fraud |
| Access | RDP | For setup, and for the periodic `--login` |

Cheapest route is a Windows VPS from an Indian provider (E2E Networks, Utho,
MilesWeb and similar) - roughly Rs 1,000-2,000/month for 4 GB at the time of
writing; check current pricing. Azure Central India and AWS Mumbai are
equivalent and dearer, and the one thing they add is scheduled auto-shutdown,
so running 07:45-20:30 instead of 24/7 costs about 55%.

**This is what makes it genuinely laptop-free:** RDP clients exist for Android
and iOS. The every-few-weeks `--login` - the requirement that rules out Actions
and Render - is two minutes on a phone. After first setup, no laptop is involved
at any point.

**Caveat, unchanged:** it is still a datacenter IP and the site may flag it. An
Indian datacenter is much better than Oregon or Frankfurt, but it is not home
broadband. You will know within a day or two: the symptom is "Access Denied", or
a login that will not stick.

**Battery flags are load-bearing and already set.** Task Scheduler defaults to
*not starting on battery* and *killing a task that goes onto battery*. On the
source machine that silently cost two of three runs a day, with no error and no
log line. `schedule_hourly.ps1` overrides both — do not "tidy" them away.

**A visible browser window opens on every run.** Thirteen times a day. That is
not a bug, and there is no headless mode to switch to. If it is disruptive,
lower `-DurationHours`.

**Sessions expire every few weeks.** The symptom is
`Saved session has expired`. Fix: `main.py --login` again.

**Nothing here applies to anything.** `answer_questionnaires: false`,
`max_auto_applies: 5`, and the scan batch is `--jobs-export`, which only writes
a spreadsheet. Turning on applications is a separate, deliberate decision —
`docs/SAFETY.md` first, then `--jobs-probe`, then a `--limit 3` run he reads
afterwards.

## Verifying it works

```powershell
Start-ScheduledTask -TaskName 'NaukriHourlyScan'
Get-ScheduledTaskInfo -TaskName 'NaukriHourlyScan'   # LastTaskResult 0 = ok
```

`LastTaskResult 267011` means it has not run yet. `2` from the scan itself means
no new jobs in the last 24 hours, which is normal. `0x8007042B` means it was
killed mid-run — almost always the battery settings.

Then open `data/jobs/openings-<date>.html`.
