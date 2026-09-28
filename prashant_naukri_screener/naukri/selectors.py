"""Every Naukri DOM selector lives here.

Naukri reships its profile page markup fairly often, so each field lists
several candidate selectors - the first one that resolves wins. When a field
stops extracting, fix it here and nowhere else.

Class names churn, but the visible section *headings* ("Resume headline",
"Key skills") are stable because recruiters and users read them. That is why
extraction falls back to heading-based scraping, which survives most redesigns.
"""
from __future__ import annotations

LOGIN_URL = "https://www.naukri.com/nlogin/login"
PROFILE_URL = "https://www.naukri.com/mnjuser/profile"
HOME_URL = "https://www.naukri.com/"

# URL fragments that only appear once a session is authenticated.
LOGGED_IN_URL_MARKERS = ("mnjuser/profile", "mnjuser/homepage", "mnjuser/recommendedjobs")

# Presence of any of these on the page means we are logged in.
LOGGED_IN_MARKERS = [
    ".view-profile-wrapper",
    ".nI-gNb-drawer__bars",
    "[data-ga-track*='My Naukri']",
    ".mn-hdr",
]

# Fields scraped from the profile page. Each entry maps to a list of candidate
# CSS selectors, tried in order.
#
# Verified against the live DOM on 2026-08-21. The page is assembled from
# "widget" cards: each section is a `#lazy*` root holding a `.widgetHead` (the
# title plus its edit/add affordances) and a `.widgetCont` (the content). These
# selectors point at the content and never the head, because the head carries
# icon-font ligature text - "editOneTheme", "locationOt" - that would otherwise
# be extracted as if it were profile data.
FIELDS: dict[str, list[str]] = {
    "name": [
        ".txt-wrapper .fullname",
        "span.fullname",
    ],
    "current_designation": [
        ".txt-wrapper .desg",
        ".subhdn .desg",
    ],
    # Header details are labelled only by their icon, so each one is addressed
    # through the icon beside it rather than by position in the list.
    "location": [
        ".detail-item:has(em.icon.loc) .txt",
    ],
    "experience": [
        ".detail-item:has(em.icon.exp) .txt",
    ],
    "current_salary": [
        ".detail-item:has(em.icon:text-is('walletOneTheme')) .txt",
    ],
    "notice_period": [
        ".detail-item:has(em.icon:text-is('calenderOneTheme')) .txt",
    ],
    "resume_headline": [
        "#lazyResumeHead .widgetCont",
    ],
    "profile_summary": [
        "#lazyProfileSummary .widgetCont",
    ],
    "career_profile": [
        "#lazyDesiredProfile .widgetCont",
    ],
    "personal_details": [
        "#lazyPersonalDetail .widgetCont",
    ],
    "accomplishments": [
        "#lazyAccomplishment .widgetCont",
    ],
    "resume_file": [
        "#lazyAttachCV .cvPreview",
        ".attachCV .cvPreview",
    ],
    "profile_completeness": [
        ".profile-strength .value",
        "[class*='completeness'] [class*='value']",
    ],
}

# Fields where we want every match, not just the first.
LIST_FIELDS: dict[str, list[str]] = {
    "key_skills": [
        "#lazyKeySkills .widgetCont .chip",
    ],
    "it_skills": [
        "#lazyITSkills .widgetCont li.collection",
    ],
    "employment": [
        "#lazyEmployment .row.emp-list",
    ],
    "education": [
        "#lazyEducation .row.edu-list",
    ],
    "projects": [
        "#lazyProject .row.project-list",
    ],
}

# Table header rows that match a list selector but carry no data.
LIST_NOISE = ("Skills Version Last used Experience",)

# Visible titles used by the widget fallback, keyed by output field name. Class
# names churn; the words recruiters read do not.
HEADING_FALLBACKS: dict[str, list[str]] = {
    "resume_headline": ["Resume headline"],
    "profile_summary": ["Profile summary"],
    "key_skills": ["Key skills"],
    "it_skills": ["IT skills"],
    "employment": ["Employment"],
    "education": ["Education"],
    "projects": ["Projects"],
    "accomplishments": ["Accomplishments"],
    "certifications": ["Certifications", "Certification"],
    "languages": ["Languages known", "Languages"],
    "career_profile": ["Career profile", "Desired job details"],
    "personal_details": ["Personal details"],
}

# Edit dialogs, keyed by the field they edit.
# `trigger` opens the dialog, `input` is the field to type into, `save` commits.
#
# Triggers are anchored to the section's visible heading and take the edit icon
# that is its *sibling*. The obvious `//*[text()='Key skills']/following::span`
# form looks equivalent but is not: the "Quick links" sidebar repeats every
# section name, so `following::` walks out of the nav and grabs whichever card's
# edit icon comes next in the document. Sibling-scoping excludes the nav,
# because nav links have no edit icon beside them.
#
# Verified against the live DOM on 2026-08-20.


def _edit_trigger(heading: str) -> str:
    return f"xpath=//*[normalize-space(text())='{heading}']/following-sibling::span[contains(@class,'edit')][1]"


def _add_trigger(heading: str) -> str:
    """The "Add" affordance beside a heading, for sections with no content yet.

    An empty section has no edit pencil at all, so `_edit_trigger` can never
    open it - Certifications on a profile that has never listed one is exactly
    this case.
    """
    return (f"xpath=//*[normalize-space(text())='{heading}']"
            f"/following-sibling::*[contains(@class,'add') or normalize-space(text())='Add'][1]")


# The shell every profile edit dialog is rendered into. Confirmed 2026-09-12 via
# `--inspect`: the IT-skills dialog's container is
# "lightbox profileEditDrawer itSkillsEdit model_open flipOpen". Scoping a Save
# lookup to this beats a bare button:has-text('Save'), which also matches the
# global nav's own buttons.
EDIT_DRAWER = ".profileEditDrawer"


# Save buttons, appended to every editor's own list as a fallback.
#
# Why this list is long: the three-candidate version (#saveX, .btn-dark-ot,
# has-text Save) failed outright on 2026-09-06, 09-07 and 09-12 - "Could not
# find resume headline save button" - while the dialog was demonstrably open,
# because the input had already been read and filled. Naukri ships more than
# one dialog shell and the newer one carries neither the id nor btn-dark-ot.
# Losing the save is the worst failure mode here: the edit is typed, the field
# is left dirty, and the run reports failure having already changed the page.
GENERIC_SAVE = [
    f"{EDIT_DRAWER} button:has-text('Save'):visible",
    f"{EDIT_DRAWER} button[type='submit']:visible",
    "button.btn-dark-ot:visible",
    "button.btn-dark-ob:visible",
    "[role='dialog'] button:has-text('Save'):visible",
    "form button[type='submit']:visible",
    "button[type='submit']:visible",
    "button:has-text('Save'):visible",
    "input[type='submit']:visible",
]


def _editor(trigger: list[str], input_: list[str], save: list[str]) -> dict:
    """Build an editor entry, giving every one the generic save fallbacks."""
    return {"trigger": trigger, "input": input_, "save": save + GENERIC_SAVE}


EDITORS: dict[str, dict[str, list[str]]] = {
    "resume_headline": _editor(
        [_edit_trigger("Resume headline"), "#lazyResumeHead .edit.icon"],
        ["#resumeHeadlineTxt", "textarea[name='resumeHeadline']"],
        # Note: btn-dark-ot, not btn-dark-ob. Only one Save is visible at a time.
        ["#saveHeadline"],
    ),
    "profile_summary": _editor(
        [_edit_trigger("Profile summary"), "#lazyProfileSummary .edit.icon"],
        ["#profileSummaryTxt", "textarea[name='profileSummary']"],
        ["#saveSummary"],
    ),
    "key_skills": _editor(
        [_edit_trigger("Key skills"), "#lazyKeySkills .edit.icon"],
        ["#keySkillSugg", "input[name='suggestor']"],
        ["#saveKeySkills"],
    ),
}

# Naukri's own limits - exceeding them silently truncates or blocks the save.
MAX_LENGTHS = {"resume_headline": 250, "profile_summary": 1000}


# --------------------------------------------------------- droope dropdowns
#
# Naukri's own dropdown widget, used for every year/month/notice-period field.
# It is not a <select>: the visible control is `#<base>For`, and the options are
# anchors inside `#ul_<base>`, each carrying a stable `data-id` of the form
# `<base>_<value>`. Confirmed 2026-09-12 from the IT-skills dialog markup:
#
#   <div class="ddwn singleSelect" id="expYearDroope">
#     <input class="srchTxt" id="expYearDroopeFor" placeholder="Years">
#     <div class="drop" id="dp_expYearDroope">
#       <div class="nScroll" id="ul_expYearDroope"><ul>
#         <li class="pickVal"><a data-id="expYearDroope_4"> 4 Years </a></li>
#
# Selecting by data-id rather than by visible text is what makes this reliable -
# "4 Years" and "4 Year" differ by one character across fields, and the year
# lists run back to 1940, so a text match can hit the wrong decade.


def droope_input(base: str) -> str:
    return f"#{base}For"


def droope_option(base: str, value) -> str:
    return f"#ul_{base} a[data-id='{base}_{value}']"


def droope_option_by_text(base: str, text: str) -> str:
    return f"#ul_{base} li.pickVal a:text-is('{text}')"


# ------------------------------------------------------------- IT skills
#
# One row per skill: a suggester for the name, a free-text version, then three
# droopes. Confirmed 2026-09-12. Save is #saveITSkills.
#
# This section matters more than its size suggests: recruiters filter IT skills
# by *years*, so a row claiming 2y of Python excludes the profile from every
# "Python 4+ years" search no matter what the headline says.
IT_SKILLS = {
    "trigger": [
        "xpath=//*[normalize-space(text())='IT skills']/following-sibling::span[contains(@class,'add')][1]",
        _edit_trigger("IT skills"),
        "#lazyITSkills .add.icon",
        "#lazyITSkills .edit.icon",
    ],
    "name": ["#itSkillSugg"],
    "suggestions": "#sugDrp_itSkillSugg li.sugTouple",
    "version": ["#version"],
    "last_used": "lastUsedDroope",
    "years": "expYearDroope",
    "months": "expMonthDroope",
    "save": ["#saveITSkills"] + GENERIC_SAVE,
}

# Rows already on the profile, as rendered in the section (not the dialog):
#
#   <li class="collection" data-prefillid="23fb...">
#     <span class="col s3 ">Python</span>
#     <span class="col s2 ">3.12</span>
#     <span class="col s3">2025</span>
#     <span class="col s3">2 Years 1 Month </span>
#     <span class="col icon edit right-align" data-prefillid="23fb...">editOneTheme</span>
#
# A skill already listed must be opened through *its own* pencil. Going through
# "Add details" instead would not update the existing row, it would add a second
# one - leaving the profile claiming Python twice, with two different year
# counts, which is worse for a recruiter reading it than the wrong number alone.
IT_SKILL_ROW = "#lazyITSkills li.collection"


def it_skill_row_edit(name: str) -> str:
    return (f"xpath=//*[@id='lazyITSkills']//li[contains(@class,'collection')]"
            f"[span[contains(@class,'col')][normalize-space(text())='{name}']]"
            f"//span[contains(@class,'edit')]")

# Droope option labels are singular at 1 and plural elsewhere ("1 Year",
# "4 Years", "1 Month", "5 Months"), which is why the text fallback needs to
# know the unit rather than just the number.
DROOPE_YEAR_LABEL = lambda n: f"{n} Year" if n == 1 else f"{n} Years"      # noqa: E731
DROOPE_MONTH_LABEL = lambda n: f"{n} Month" if n == 1 else f"{n} Months"   # noqa: E731


# --------------------------------------------------------- certifications
#
# Lives inside Accomplishments, and on a profile that has never listed one there
# is no edit pencil - only an "Add" anchor beside the "Certification" label, in
# an unclassed container. The trigger therefore scopes through the label's
# parent; a `following::a` walk leaves the card entirely and opens Career
# profile instead, which is exactly what happened on the first attempt.
#
# Confirmed 2026-09-12. #certName is free text, not a suggester.
CERTIFICATIONS = {
    "trigger": [
        "xpath=//*[normalize-space(text())='Certification']/parent::*//a[contains(@class,'add')]",
        "xpath=//*[normalize-space(text())='Certification']/following-sibling::a[contains(@class,'add')][1]",
        _edit_trigger("Certification"),
    ],
    "name": ["#certName"],
    "cert_id": ["#certifications-comp-id_0"],
    "url": ["#certifications-url_0"],
    "from_month": "certifications-fromDate-month-0",
    "from_year": "certifications-fromDate-year-0",
    "to_month": "certifications-toDate-month-0",
    "to_year": "certifications-toDate-year-0",
    "never_expires": ["#doesNotExpire"],
    "save": ["#saveCertificationsBtn"] + GENERIC_SAVE,
}


# ------------------------------------------------------------- designation
#
# The current job title, edited through the Employment card - NOT through
# "Add employment", which opens an identical-looking blank form whose Save
# creates a second, duplicate employment entry. The trigger is therefore
# anchored to the designation text itself (`span.emp-desg`) and takes the edit
# pencil that is its sibling, so it cannot resolve to the Add link or to a
# previous employer's card.
#
# Confirmed 2026-09-12: span.truncate.emp-desg, sibling span.edit.icon,
# dialog input #designationSugg, save #submitEmployment.
def designation_trigger(current: str) -> list[str]:
    return [
        f"xpath=//span[contains(@class,'emp-desg')][normalize-space(text())='{current}']"
        f"/following-sibling::span[contains(@class,'edit')][1]",
        f"xpath=//*[normalize-space(text())='{current}']"
        f"/following-sibling::span[contains(@class,'edit')][1]",
    ]


DESIGNATION = {
    "input": ["#designationSugg"],
    "company": ["#companySugg"],
    "save": ["#submitEmployment"] + GENERIC_SAVE,
}

# Key-skill chip widget. Typing text and pressing Enter does NOT create a chip;
# a suggestion has to be clicked. Anything left sitting in the input gets
# committed as a chip when Save is pressed, so the box must be cleared first.
SKILL_CHIP = ".chipsContainer .chip"
SKILL_CHIP_LABEL = ".tagTxt"
SKILL_CHIP_REMOVE = ".material-icons.close"
SKILL_SUGGESTIONS = "#sugDrp_keySkillSugg li.sugTouple"


def suggestions_for(input_id: str) -> str:
    """The suggestion dropdown belonging to a given suggester input.

    Naukri names the popup after the input: #keySkillSugg is served by
    #sugDrp_keySkillSugg, #itSkillSugg by #sugDrp_itSkillSugg. Hardcoding the
    key-skills one is why every IT-skill add failed with an empty suggestion
    list on 2026-09-12 - the code was watching a dropdown that belongs to a
    different dialog, so it saw nothing and reported "no exact suggestion".
    """
    return f"#sugDrp_{input_id} li.sugTouple"

# Resume attachment. #attachCV is the real (hidden) file input; the visible
# "Update" control is input[button]#dummyUpload, which only proxies to it.
# Confirmed 2026-09-12 - attachCV appeared in every dialog dump because it lives
# on the page, not inside any one dialog.
RESUME_UPLOAD = [
    "#attachCV",
    "input[type='file']#attachCV",
    "#lazyAttachCV input[type='file']",
    "input[type='file']",
]

# Where the currently attached filename is rendered.
RESUME_ATTACHED = [
    "#lazyAttachCV .cvPreview",
    ".attachCV .cvPreview",
]


# Toast / confirmation that a save actually landed.
SAVE_CONFIRMATIONS = [
    ".nI-gNb-info",
    "text=/successfully/i",
    "text=/updated/i",
]

# Section names that appear verbatim in the "Quick links" sidebar. Heading-based
# extraction uses these to recognise when it has climbed out of a profile card
# and into the nav: three or more of these in one block means it is the sidebar,
# not a section. See _HEADING_JS in extract.py.
SECTION_LABELS = [
    "Quick links",
    "Resume headline",
    "Key skills",
    "IT skills",
    "Employment",
    "Education",
    "Projects",
    "Profile summary",
    "Accomplishments",
    "Career profile",
    "Personal details",
]


# --------------------------------------------------------------- job listings
#
# Verified against a live job-detail page on 2026-08-21. Naukri ships hashed
# CSS module class names here ("styles_apply-button__uJI3A"), so the stable
# hooks are the id and the unhashed companion class, not the module class.

JOB_APPLY_BUTTON = [
    "#apply-button",
    "button.apply-button",
    "button[class*='apply-button']",
]

# The button's own label is the most reliable signal of what a click will do:
# an off-site posting reads "Apply on company site".
APPLY_OFFSITE_LABELS = ("company site", "company website", "apply on company")
APPLY_DONE_LABELS = ("applied", "already applied")

# The definitive confirmation. Once an application lands, the job page itself
# replaces the Apply button with this badge. It is far more reliable than the
# toast: a questionnaire that completes may show no toast at all, which is how
# a successful application first got recorded as a failure.
APPLY_APPLIED_MARKERS = [
    "[class*='already-applied' i]",
    "span.already-applied",
]

# Shown once an application actually lands.
APPLY_SUCCESS = [
    "text=/successfully applied/i",
    "text=/application sent/i",
    "text=/you have applied/i",
    ".apply-message",
]

# The recruiter questionnaire ("chatbot"). Verified against a live drawer on
# 2026-08-21. Its presence means the application is NOT yet submitted - it is
# waiting on answers.
#
# Every id in this widget is randomised per session (_i7qo2hnh6Drawer one run,
# _7k4bm8lhuDrawer the next), so only class names are usable here.
JOB_CHATBOT = [
    ".chatbot_Drawer",
    ".chatbot_DrawerContentWrapper",
    "[class*='chatBotContainer' i]",
]

JOB_CHATBOT_CLOSE = [
    ".chatbot_Nav .crossIcon",
    ".crossIcon.chatBot",
    "[class*='chatbot' i] [class*='cross' i]",
]

# The bot's messages. The last one is the question currently being asked.
CHATBOT_QUESTION = "li.botItem .botMsg"

# Single-select questions render as radios whose <label> carries the option
# text. The inputs' ids contain spaces ("2 months"), so click the label.
CHATBOT_RADIO_LABEL = "label.ssrc__label"

# Free-text answers go into a contenteditable div, not an <input>. Its wrapper
# carries `d-none` while a choice-based question is on screen.
CHATBOT_TEXT_INPUT = ".chatbot_InputContainer .textArea[contenteditable='true']"
CHATBOT_INPUT_WRAPPER = ".chatbot_SendMessageContainer"

# "Save" is a styled div, not a <button>, and its parent carries `disabled`
# until the current question has an answer.
CHATBOT_SAVE = ".sendMsgbtn_container .sendMsg"
CHATBOT_SAVE_DISABLED = ".sendMsgbtn_container .send.disabled"

# The bot's closing message once every question has been answered.
CHATBOT_SUCCESS = [
    "text=/successfully applied/i",
    "text=/application (has been )?(sent|submitted)/i",
    "text=/thank you for applying/i",
]
