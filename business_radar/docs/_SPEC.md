# MODULE SPEC (from Sagar): CITY-WISE BUSINESS RESEARCH REPORT + HUMAN VERIFIED OUTREACH

Extend the existing AI Business Opportunity & Software Sales Platform with a mandatory:
RESEARCH -> REPORT -> VERIFY -> SELECT -> PERSONALIZE -> PREVIEW -> SEND workflow.
The system must NEVER automatically contact a business simply because the AI has discovered and qualified it.
Human verification is mandatory before outbound communication.

## 1. DAILY / CAMPAIGN SEARCH
Multiple target cities (e.g. Dhule, Shirpur, Nashik, Jalgaon). Optional business categories: All OR Hospital, School,
College, Manufacturer, Distributor, Vehicle Dealer, Retail, Hotel, Bakery, Restaurant, Diagnostic Center, Garage,
Real Estate etc. Optional minimum business size: Medium / Large. Optional minimum opportunity score: 70.
Optional research depth: Standard / Deep.

## 2. SEARCH JOB
Starting a search creates a Search Campaign, e.g. "Dhule-Shirpur-Nashik-Jalgaon - 26 Aug 2026". Store: Campaign ID,
Created by, Created date/time, Target cities, Target industries, Business size filter, Minimum opportunity score,
Research depth, Search status, Number discovered, Number researched, Number qualified, Number skipped,
Number verified, Number contacted.

## 3. CITY-WISE ORGANIZATION
The report MUST organize businesses by city (DHULE / SHIRPUR / NASHIK / JALGAON), each with sections:
Healthcare, Education, Automobile, Manufacturing, Retail, Hospitality, Distribution, Other.

## 4. CATEGORY-WISE ORGANIZATION
Inside each city, group by category: Hospitals, Schools, Manufacturers, Automobile, ...

## 5. HTML REPORT
Generate a professional HTML report after every search campaign. Downloadable, viewable in a browser.
Filename example: business_research_dhule_shirpur_nashik_jalgaon_2026-08-26.html
Completely self-contained where practical.

## 6. HTML REPORT HEADER
AI BUSINESS OPPORTUNITY RESEARCH; Campaign; Search Date; Number of Businesses Found; Number Researched;
Number Qualified; Number Skipped; Number Requiring Verification; Number Ready for Outreach.

## 7. KPI CARDS
Total Businesses, Qualified, High Opportunity, Medium Opportunity, Low Opportunity, Website Available, No Website,
Potential Software Opportunity, Need Verification, Verified, Already Contacted, Interested.

## 8. CITY SUMMARY
Cards per city: Businesses Found, Qualified, High Opportunity, Verified, Ready for Outreach.
These numbers must come from actual database results. Never fabricate them.

## 9. BUSINESS TABLE COLUMNS
Select, Business, City, Category, Size, Website, Digital Maturity, Opportunity Score, Potential Solution,
Contact Available, Research Confidence, Verification Status, Outreach Status, Actions.

## 10. BUSINESS ROW EXAMPLE
[ ] ABC Hospital / Dhule / Healthcare / Medium / Website: Yes / Digital Maturity: 62 / Opportunity: 86 /
Potential Solution: Hospital Operations Platform / Contact: Business Email Available / Confidence: Medium /
Verification: NOT VERIFIED / Outreach: NOT CONTACTED / Actions: View Research, Verify, Generate Message.

## 11. BUSINESS DETAIL
Business Name, Category, City, Website, Public Business Contact, Business Listing, Sources, Business Size,
Digital Maturity, Operational Complexity, Opportunity Score, Research Confidence.

## 12. RESEARCH FINDINGS (MANDATORY SEPARATION)
VERIFIED / OBSERVED = facts directly supported by sources. INFERRED = reasonable conclusions.
UNKNOWN = information that could not be verified. This is mandatory.

## 13. SOFTWARE OPPORTUNITY
Potential Problem, Potential Solution, Recommended Modules, Expected Business Benefit, Opportunity Score, Confidence.
Example modules: Dashboard, Workflow, Finance Tracking, Inventory, Reports, Role Management, Audit Logs.

## 14. SOURCE PANEL
Every research result: Source Name, Source URL, Source Type, Date Checked, Information Obtained, Confidence.
The user must be able to open the source.

## 15. HUMAN VERIFICATION
Add a VERIFY BUSINESS button. Business must NOT become outreach-eligible until verified. Verification screen shows:
Business Name, Category, Location, Website, Contact, Research Summary, Sources, AI Recommendation,
Potential Software Opportunity.

## 16. VERIFICATION CHECKLIST
- [ ] Business identity appears correct
- [ ] Business is located in target city
- [ ] Business category is correct
- [ ] Business appears operational
- [ ] Contact information appears to be a legitimate business contact
- [ ] Research is relevant
- [ ] Software opportunity appears reasonable
- [ ] Outreach is appropriate
- [ ] No do-not-contact record exists

Only after verification: Status = VERIFIED

## 17. VERIFICATION STATES
AI_RESEARCHED, NEEDS_VERIFICATION, VERIFIED, REJECTED, SKIPPED, CONTACT_READY, CONTACTED, RESPONDED, INTERESTED,
HUMAN_HANDOFF

## 18. BULK SELECTION
Select multiple verified businesses across cities (Dhule 5, Nashik 7, Jalgaon 3 = 15 selected).
Only businesses with VERIFIED and CONTACT_READY can be selected for outreach.

## 19. NEVER SEND DIRECTLY FROM SEARCH RESULTS
The "Send" button must NOT exist on the raw AI research result.
Research -> Verify -> Select -> Prepare Outreach -> Preview -> Confirm -> Send

## 20. OUTREACH WORKSPACE
PREPARE OUTREACH opens a dedicated screen: Selected Business, Research Summary, Why selected, Potential software
opportunity, Recommended solution, Recommended modules, Available contact channels.

## 21. CHANNEL SELECTION
Email, WhatsApp, Phone, Manual. Initially focus on Email and official business messaging/WhatsApp integration where
permitted. Do not implement unofficial WhatsApp automation.

## 22. MESSAGE GENERATION
EMAIL -> personalized email. WHATSAPP -> shorter personalized business message. AI must use: Business name, Industry,
City, Relevant public observation, Potential operational opportunity, Relevant software solution, Demo offer,
Sagar's role/company information.

## 23. MESSAGE MUST NOT MAKE UNSUPPORTED CLAIMS
Bad: "We noticed that you are managing your hospital through Excel." (if unverified)
Good: "Based on the scale and nature of your operations, a centralized management system may help provide better
visibility across workflows and reporting."
Bad: "We know your company has inventory problems."
Good: "We believe inventory visibility may be an area where a centralized system could provide value."

## 24. EMAIL TEMPLATE
Structure: Subject, Greeting, Business-specific observation, Problem/opportunity, Solution concept, Relevant benefit,
Demo offer, Short CTA, Professional signature.

Subject: A possible digital operations solution for {{business_name}}

Hello {{contact_name/business_team}},

We work on customized business-management software for established organizations.
While researching businesses in {{city}}, we came across {{business_name}} and reviewed its publicly available
business information.
Based on the nature of your operations, we believe there may be opportunities to centralize areas such as
{{relevant_modules}} and provide management visibility through a controlled dashboard.
We are building demonstration systems for businesses in this category covering areas such as {{modules}}.
If this is relevant to your organization, I would be happy to show you a short demonstration and discuss whether such
a system could fit your current workflow.

Regards, Sagar

Do not use this exact wording for every business. Personalize the message.

## 25. WHATSAPP TEMPLATE (concise)
Hello {{business_name}} team, I work on customized business-management software for established businesses.
I came across your organization while researching businesses in {{city}}. Based on your business type, I believe a
centralized system for {{relevant_area}} could potentially improve operational visibility and reporting.
We have a working demonstration for this type of business. If you are interested, I can share a short demo and
explain how it could be customized around your workflow. Regards, Sagar

Do not send automatically. Show preview first.

## 26. MESSAGE PERSONALIZATION BY INDUSTRY
- Hospital: Patients / appointments / departments / billing / inventory / reports
- School: Students / fees / attendance / staff / transport / reports
- College: Admissions / students / departments / fees / examinations / reports
- Manufacturer: Inventory / production / purchasing / sales / quality / reports
- Distributor: Inventory / orders / customers / receivables / sales
- Bakery: Orders / production / inventory / delivery / customers / payments
- Clothing business: Inventory / variants / purchasing / sales / customers / profitability
- Vehicle dealer: Inventory / purchases / expenses / sales / profit / customers

## 27. MESSAGE PREVIEW
BUSINESS, CHANNEL, CONTACT, RESEARCH BASIS, OPPORTUNITY, GENERATED MESSAGE, AI CONFIDENCE, POLICY CHECK,
CONTACT HISTORY.

## 28. FINAL SEND CONFIRMATION
Button says "CONFIRM & SEND", not "Auto Send". Before enabling, display:
"You are about to contact this business using the selected business contact."
Show: Business, Contact, Channel, Message, Previous contact history, Opt-out status, Approval status.

## 29. DUPLICATE CONTACT PROTECTION
Before sending check: same business, same email, same phone, same WhatsApp identifier where supported, recent
campaign, previous response, opt-out. If already contacted recently: BLOCK SEND and display
"Contact already exists / recent outreach detected."

## 30. OPT-OUT PROTECTION
If business has opted out: BLOCK ALL OUTREACH. Display DO NOT CONTACT, Reason, Date, Source.

## 31. CONTACT FREQUENCY (configurable)
Minimum days between outreach, Maximum outreach attempts, Maximum follow-ups, Stop after explicit rejection,
Stop after opt-out.

## 32. OUTREACH HISTORY
Per organization: Date, Channel, Message, Sender, Delivery status, Response, AI classification, Next action.

## 33. RESPONSE MONITORING / CLASSIFICATION
INTERESTED, VERY_INTERESTED, DEMO_REQUESTED, MEETING_REQUESTED, PRICE_REQUESTED, MORE_INFORMATION, LATER,
NOT_INTERESTED, ALREADY_HAVE_SOFTWARE, WRONG_CONTACT, OPT_OUT, COMPLAINT, UNKNOWN

## 34. HUMAN HANDOFF
On INTERESTED, VERY_INTERESTED, DEMO_REQUESTED, MEETING_REQUESTED, PRICE_REQUESTED create
"HUMAN ACTION REQUIRED" and notify Sagar. Include: Business, City, Category, Contact, Research report, Opportunity,
Recommended modules, Messages sent, Full response, AI interpretation, Confidence, Recommended next action.

## 35. HANDOFF EXAMPLE
ABC Industries / Dhule / Manufacturing / Opportunity 91 / Manufacturing Management Platform /
response "Yes, please show us what you can provide." / Status DEMO REQUESTED / Action: Sagar should contact.

## 36. CAMPAIGN DASHBOARD
CAMPAIGN MANAGEMENT with statistics: Businesses Found, Researched, Qualified, Verified, Selected, Outreach Prepared,
Approved, Sent, Responses, Interested, Demos, Proposals, Won.

## 37. CITY COMPARISON
City | Businesses | Qualified | High Opportunity | Verified | Contacted | Responses | Interested | Conversion |
Potential Revenue. Use actual database values.

## 38. INDUSTRY COMPARISON
Industry | Businesses | Opportunity | Verified | Contacted | Responses | Interested | Demos | Won | Revenue.

## 39. HTML REPORT FILTERS
City, Industry, Business size, Opportunity score, Website status, Digital maturity, Research confidence,
Verification status, Contact status, Outreach status, Date discovered.

## 40. HTML REPORT ACTIONS
Per row: VIEW, RESEARCH, VERIFY, REJECT, SELECT, PREPARE OUTREACH, VIEW MESSAGE, SEND, HISTORY.
SEND only available after: research complete, verified, contact eligible, no opt-out, no duplicate block,
message approved.

## 41. EXPORT
HTML, CSV, PDF, Excel. Preserve: Business, City, Industry, Score, Research, Verification, Contact, Outreach status.

## 42. REPORT ARCHIVE
Store every campaign; reopen previous campaigns.

## 43. DAILY REPORT
DAILY BUSINESS OPPORTUNITY REPORT: Date, Cities researched, Businesses discovered, Businesses qualified,
Top opportunities, Businesses needing verification, Businesses ready for outreach, Outreach sent, Responses,
Interested leads.

## 44. TOP OPPORTUNITIES
Top 20: Rank, Business, City, Industry, Opportunity Score, Potential System, Reason, Confidence, Verification.

## 45. NO BLIND OUTREACH (HARD SYSTEM RULE)
NEVER: AI finds business -> automatically sends message.
Instead: AI finds -> Research -> Report -> Sagar verifies -> Sagar selects -> AI prepares personalized message ->
Sagar previews -> Sagar confirms -> Send.

## 46. FUTURE AUTOMATION
Modes: Manual, Human Approval, Semi-Automated, Fully Automated (only when legally/platform appropriate and
explicitly enabled). Default: HUMAN APPROVAL.

## 47. SECURITY
Protect business data, contact data, research data, messages, credentials, API keys, campaign data, client data.
Use RBAC, encryption, secure secrets, audit logs, rate limits, API security, input validation, secure file handling,
backups.

## 48. OUTREACH AUDIT
Every send creates an immutable-style audit record: Business, Contact, Channel, Message, Research ID, Campaign ID,
User approval, Timestamp, Provider response, Delivery status.

## 49. AI MESSAGE AUDIT
Store: Original research, Facts used, Inferences used, Prompt/version, Generated message, Policy result, Human edits,
Final message, Approval, Send result. So Sagar can understand exactly why the AI generated the message.

## 50. UI DESIGN
Professional enough to present internally: clean dashboard, KPI cards, city tabs, industry tabs, tables, search,
filters, score badges, confidence badges, verification badges, outreach badges, expandable research panels,
responsive design.

## 51. RECOMMENDED UI COLORS
Green: Verified / Interested / Won. Yellow: Needs verification / Follow-up. Red: Rejected / Opt-out / Blocked.
Blue: Research / Information. Do not use excessive colors.

## 52. EXAMPLE COMPLETE WORKFLOW
Sagar enters cities, industries All, size Medium+Large, min opportunity 70, clicks START RESEARCH. System researches.
GENERATE REPORT. Sagar opens Dhule > Healthcare > ABC Hospital (Opportunity 87, Research Complete,
Verification Pending). Clicks VERIFY, reviews website/identity/contact/research/opportunity, approves -> VERIFIED.
Selects ABC Hospital, clicks PREPARE OUTREACH, selects Email. AI generates personalized email. Sagar reviews.
AI displays research basis, message, compliance check, previous contact. Sagar clicks CONFIRM & SEND. Email sent,
recorded. Later hospital replies "Please send details." AI classifies INTERESTED. Notification HUMAN ACTION REQUIRED.
Sagar opens the lead and personally contacts the hospital.

## 53. BUSINESS VALUE
Answer: which city gives best opportunities, which industries respond most, which businesses have highest software
potential, which outreach works, which demos generate interest, which proposals convert, what software to build next.

## 54. IMPORTANT PRODUCT METRIC
Do not optimize for number of messages sent. Optimize for QUALIFIED CONVERSATIONS.
Track: Research -> Qualification -> Verification -> Outreach -> Response -> Interest -> Demo -> Proposal -> Client.

## 55. FINAL PRINCIPLE
Behave like a DIGITAL BUSINESS DEVELOPMENT ASSISTANT: research, analyze, prioritize, explain, recommend, prepare,
verify, draft, track, notify. But it must NOT blindly send messages. Sagar remains the final decision-maker for
initial outreach and personally handles serious prospects.

## 56. DEVELOPMENT TASK
First provide: (1) Database schema additions (2) Campaign schema (3) HTML report architecture (4) Verification
workflow (5) Outreach workflow (6) Message template engine (7) Email integration architecture (8) WhatsApp official
API integration architecture (9) Response classification (10) Human handoff (11) Audit architecture (12) UI wireframe
(13) API endpoints (14) Background jobs (15) Security model (16) MVP implementation plan.
Do not implement automatic outreach first.
Build RESEARCH -> REPORT -> VERIFY -> SELECT -> PREVIEW -> SEND as the initial production workflow.
