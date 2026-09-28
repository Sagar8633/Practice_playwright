# Target output format: `resume.yaml`

The redesigned resume is written as a YAML file that an existing ATS-safe DOCX
builder renders. Produce **exactly** these keys — no others, no renames.

```yaml
name: KAMLESH BEHERE            # string, ALL CAPS
title: <headline>               # single line, " | " separated keywords
contact:                        # list of strings, one per centred line
- <line 1>
- <line 2>
summary: >-                     # one paragraph, folded scalar
  <text>
skills:                         # list of label/items pairs, each renders as one line
- label: <group name>
  items: <comma-separated keywords>
experience:                     # REQUIRED, at least one entry
- title: <job title>
  org: <employer>
  loc: <city, country>          # optional
  dates: <Mon YYYY - Mon YYYY>  # REQUIRED
  bullets:                      # REQUIRED, list of strings
  - <bullet>
achievements:                   # optional, list of plain strings
- <achievement>
projects:                       # optional, list of label/description pairs
- label: <project name>
  description: >-
    <prose; renders as "• label: description" on one flowed paragraph>
certifications:                 # optional, list of plain strings
- <line>
education:                      # optional
- degree: <degree>
  institution: <school>
  years: <YYYY - YYYY>
output_basename: Kamlesh_Behere_QA_Automation_Resume
```

## Hard constraints from the renderer

1. **Single-column, linear paragraphs only.** No tables, columns, text boxes,
   images or icons — the builder emits body paragraphs and the ATS reads them as
   a stream. Anything else scrambles the reading order.
2. `projects[].description` renders as **one flowed paragraph** after a bold
   label. It cannot contain sub-bullets or line breaks. If a project needs a
   module keyword list, fold it into the prose, e.g.
   `"Modules - A, B, C. Then the prose sentences."`
3. `experience[].bullets` DO render as real bullets. Per-project bullet lists are
   only possible by promoting a project into `experience`.
4. Section headings are fixed by the builder and cannot be renamed from YAML:
   Professional Summary, Technical Skills, Professional Experience, Key
   Achievements, Key Projects, Certifications & Continuous Learning, Education.
5. Plain ASCII hyphens `-`, not en/em dashes. Avoid `&` inside unquoted YAML only
   where it starts a value; mid-string `&` is fine.
6. Every `experience` entry MUST have title, org, dates and bullets or the build
   fails loudly.

## Placeholder convention for unknown facts

Where the source resume does not supply a fact (dates, graduation year, LinkedIn
URL), write a visible bracketed placeholder such as `[CONFIRM: start month/year]`
rather than inventing a value. These are meant to be seen and filled in by
Kamlesh before he sends the file.
