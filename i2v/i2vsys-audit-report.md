# Website Test Report — https://www.i2vsys.com/

**Date:** 2026-06-02
**Method:** Automated browser testing with Playwright 1.57 (real Chromium, Firefox, WebKit engines + device emulation + CDP network throttling), plus HTTP/SSL inspection and manual content/visual review.
**Pages audited:** Home, Why i2V (About), Products, Industries (Solutions), Contact Us, Product‑VMS, plus Careers / Blogs / Resources / Partners for link crawling.
**Raw evidence:** JSON results and screenshots in `i2v/out/` (`engines.json`, `links.json`, `responsive.json`, `throttle.json`, `forms.json`, `misc.json`, `shots/`).

---

## Executive Summary

The site is **functional, secure, and visually polished**, and renders correctly across all three browser engines and every emulated device with **zero horizontal-scroll issues**. All audited pages return HTTP 200, SSL/headers are strong, navigation works, and forms validate.

The dominant problem is **performance / page weight**. Pages are very heavy (the *Why i2V* page transfers **12–15 MB**), server response (TTFB) is slow (~1.3–1.9 s), and the site is effectively **unusable on Slow‑3G** (load timed out >90 s) and poor on Fast‑3G (~57 s). There is also a **large accessibility gap** (hundreds of images without alt text, missing semantic landmarks, no skip link, weak focus indicators) and a handful of **broken links**.

### Severity tally
| Severity | Count | Headline items |
|---|---|---|
| 🔴 High | 3 | Page weight/load time; broken Terms‑of‑Use link sitewide; missing alt text at scale |
| 🟠 Medium | 6 | Slow TTFB; 3G performance; mailto link 404; no `<main>`/`<footer>` landmarks; weak keyboard focus; non‑semantic mobile menu toggle |
| 🟡 Low | 6 | Brand capitalization inconsistency; 2× `<h1>`; no skip link; reCAPTCHA console noise in Safari; YouTube cookie warnings in Firefox; minimal CSP |
| ✅ Pass | many | SSL/HTTPS, security headers, cross-engine rendering, responsive layout, form validation, active nav state, tel/mailto behavior |

---

## 1. Basic Functionality & Performance

### 1.1 Access & Load — 🔴 / 🟠
All pages load successfully (HTTP 200) in every engine. However, load times are **slow**, driven by page weight and server response time.

**Chromium (broadband, 1366×900) — load event / FCP / TTFB / transfer:**
| Page | Load event | FCP | TTFB | Transfer |
|---|---|---|---|---|
| Home | 4.77 s | 2.59 s | 1.75 s | 3.6 MB |
| Why i2V (About) | 6.44 s | 1.89 s | 1.34 s | **15.2 MB** |
| Products | 5.48 s | 2.11 s | 1.56 s | 1.7 MB |
| Industries | 6.74 s | 2.36 s | 1.92 s | 5.7 MB |
| Contact Us | 6.35 s | 2.18 s | 1.84 s | 0.37 MB |
| Product‑VMS | 4.70 s | 1.92 s | 1.59 s | 1.8 MB |

**Findings:**
- 🔴 **Excessive page weight.** *Why i2V* transfers **12–15 MB**, *Industries* ~5.7 MB. The heaviest single assets are uncompressed‑scale WebP images served at full resolution, e.g. `multi-level-permissions.webp` (**1.31 MB**) and `system-hardening.webp` (**1.28 MB**) on *Why i2V*. Home loads **250 resources**.
- 🟠 **Slow TTFB (~1.3–1.9 s)** on every page indicates a slow backend/host response (Apache/WordPress, no edge caching evident). This delays everything downstream.
- 🟠 **Render-blocking embeds.** Auto-playing **YouTube iframes** (e.g. on *Why i2V*) take ~3–4 s and the Google **Maps iframe** on Contact takes ~4.1 s.
- **Slow assets to fix first:** resize/compress the large hero/feature WebP images; lazy-load below-the-fold images and the YouTube/Maps embeds (load on interaction); enable a CDN + far-future caching; serve responsive `srcset` sizes.

### 1.2 Links & Assets — 🔴 / 🟠
Crawled **107 unique links** across 10 pages. **103 return 200; 4 are broken (404):**
| Status | Link | Cause |
|---|---|---|
| 🔴 404 | `…/products/terms-of-use` | "Terms of Use" footer link uses a **relative href without leading slash**, so it resolves under the current path. Breaks on every sub-page. Correct URL is `/terms-of-use/` (verified 200). |
| 🔴 404 | `…/products/video-management-software/terms-of-use` | Same root cause on the VMS page. |
| 🟠 404 | `…/contact-us/mandeep.panwar@i2vsys.com` | An **email address used as a normal link, missing the `mailto:` prefix** — browser treats it as a relative path. |
| 🟠 404 | `…/resources/i2v-vms-pre-installer-1/` | Broken/removed resource download link. |

No broken **images** were detected (`naturalWidth>0` for all loaded images across all engines).

### 1.3 Navigation — ✅
- Primary header nav and footer nav links resolve correctly (Home, Why i2V, Products, Industries, Partners, Careers, Blogs & News, Resources, Contact).
- **Active state is correct:** on `/products/`, the "i2V products" nav link carries `aria-current="page"` ✅.

### 1.4 Forms — ✅ with 🟠 caveat
The Contact page hosts **6 forms** (1 site search + 5 Contact Form 7 instances: Contact, Demo/Quote, Partner, Career/Partnership, Technology Partner). Inspected the full field inventory.
- ✅ **Email validation works** — entering `not-an-email` is rejected by the browser ("Please include an '@'…").
- ✅ `type="tel"` phone field with a placeholder → correct numeric keypad on mobile; `type="url"` for website; `<select>` dropdowns for industry/enquiry; reCAPTCHA present for spam protection.
- 🟠 **No HTML5 `required` attributes** on the visible fields (only the search field is `required`). Fields are marked required *visually* (asterisks) but enforcement depends entirely on **CF7 server-side validation** — there is no client-side "this field is required" guard. Recommend adding `required`/`aria-required` to the visible mandatory fields for instant feedback.
- 🟡 Name/email fields lack `autocomplete` hints (phone is `autocomplete="off"`), and no `inputmode` is set — minor mobile-UX/autofill improvements available.
- *Note:* a true end-to-end "successful submission" was **not** completed to avoid sending live leads/triggering reCAPTCHA. Validation behavior was verified instead.

### 1.5 Content — 🟡
Text is largely clean and professional. Issues:
- 🟡 **Inconsistent brand capitalization**: `i2V`, `i2v`, and "i2V systems" (lowercase *systems*) appear in different places (e.g., header "Why i2V?" vs footer email `i2v@i2vsys.com`; Contact heading "Contact i2V systems…"). Standardize to one form.
- 🟡 Minor redundancy ("intelligent video **security** solutions…") and a repeated tagline ("Trusted by leading global brands…").
- ✅ No lorem-ipsum/placeholder content found.

### 1.6 SSL / Security — ✅ (strong)
- ✅ Valid certificate (GoDaddy Secure CA G2, CN=i2vsys.com), valid **Aug 21 2025 → Aug 27 2026**.
- ✅ **HTTP → HTTPS 301 redirect**.
- ✅ Strong headers: `Strict-Transport-Security` (2-yr, includeSubDomains, preload), `X-Frame-Options: SAMEORIGIN`, `X-Content-Type-Options: nosniff`.
- 🟡 `Content-Security-Policy` is minimal (`upgrade-insecure-requests` only) — a fuller CSP would harden further.

---

## 2. User Experience (UX)

### 2.1 Intuition & flow — ✅
Clear value proposition ("Transform security with next-gen AI video management solutions"), logical IA (Why → Products → Industries → Partners → Contact), and prominent, well-placed **"Request a demo" / "Speak to our experts"** CTAs on every page. Finding product info and reaching a demo request are both low-friction.

### 2.2 Visuals — ✅
Strong, consistent branding; dark hero with high-contrast white headings; clean product/footer layout (Products / Industries / Company / Resources / Legal columns). Body font 16 px. Imagery is high quality (arguably *too* high-resolution — see performance).

### 2.3 Interactivity — ✅ / needs manual confirm
Carousels, hover CTAs, and embedded video are present and animate smoothly in testing. (Subjective smoothness of hover/scroll animations should be spot-checked manually.)

### 2.4 Accessibility (basic) — 🟠 / 🔴
| Check | Result |
|---|---|
| `html lang` | ✅ `en-US` |
| Viewport meta | ✅ `width=device-width, initial-scale=1` |
| Alt text on images | 🔴 **Home: 401 of 575 images have empty/missing alt** (~70%); similar ratios on every page. (Some are decorative SVG icons that legitimately use `alt=""`, so the *true* gap is smaller — but a large number of meaningful images clearly lack alt text.) |
| Semantic landmarks | 🟠 **No `<main>` and no `<footer>` element** detected (header & nav exist). Screen-reader navigation suffers. |
| Skip-to-content link | 🟠 **Absent.** |
| Headings | 🟡 **2× `<h1>`** on Home (should be exactly one). |
| Keyboard focus visible | 🟠 Tab order is logical, but computed focus **outline width is 0 px** with no box-shadow — the **visible focus indicator appears suppressed**. (Confirm manually; if so, add a clear `:focus-visible` style.) |

### 2.5 Perceived performance — 🟠
FCP of ~2 s on broadband is acceptable but not snappy; the heavy hero media and auto-playing video make the page *feel* busy and slow to settle. On mobile networks the perception is poor (see §4).

---

## 3. Cross-Browser Compatibility

Ran the same 6 pages through **Chromium, Firefox, and WebKit** (WebKit is the Safari engine; native macOS Safari hardware was not available, so this is the closest faithful proxy).

| Metric | Chromium | Firefox | WebKit (Safari) |
|---|---|---|---|
| All pages HTTP 200 | ✅ | ✅ | ✅ |
| Layout/rendering | ✅ consistent | ✅ consistent | ✅ consistent |
| Avg load event | ~5.7 s | ~5.9 s | ~8.1 s (slowest) |
| Console errors | 0 | 2 (Why i2V) | 4–5 per page |

**Findings:**
- ✅ **Layout and functionality are consistent** across all three engines — no broken layouts, no engine-specific functional failures.
- 🟡 **WebKit/Safari console noise:** every page logs **401 errors from `google.com/recaptcha/api2/pat`**. This is a known reCAPTCHA telemetry behavior under WebKit (the badge/forms still work) — cosmetic console noise rather than a functional break, but worth knowing for Safari QA.
- 🟡 **Firefox:** 2 console warnings on *Why i2V* — third-party **YouTube `__Secure-YEC` cookie SameSite** rejections from the embedded video. Benign/third-party.
- 🟠 **WebKit is meaningfully slower** (Why i2V load 14.6 s vs 6.4 s Chromium), amplifying the page-weight problem for Safari users.

---

## 4. Mobile View & Responsiveness

Tested with device emulation on **iPhone 15 Pro, Pixel 7, iPad Pro 11, Galaxy Tab S4**, in **portrait and landscape**, across Home / Products / Contact (24 combinations). *(Emulation reproduces viewport, DPR, touch and UA; it is not real hardware.)*

| Check | Result |
|---|---|
| Horizontal scrolling | ✅ **None** on any device/orientation/page (`scrollWidth ≤ innerWidth` in all 24 runs). |
| Fluid layout adaptation | ✅ Layout reflows cleanly; mobile hero + stacked CTAs render well (see `shots/mobile-iPhone-15-Pro.png`). |
| Body font legibility | ✅ 16 px base — readable without zoom. |
| Mobile menu | ⚠️ Hamburger (☰) **is visibly present** top-left on mobile, **but** the toggle is **not a semantic `<button>`** (0 header buttons; automated open failed/timed out). It likely works for sighted mouse/touch users but is **not keyboard/AT-friendly** and lacks `aria-expanded`. Recommend converting to a `<button>` with proper ARIA. |
| Touch targets | ✅ Primary CTAs are large and finger-friendly in screenshots. |
| Tel / email links | ✅ `tel:+919810056691` and 4 `mailto:` links (sales@, support@, i2v@, lokesh.jain@) present and correctly formatted on Contact — will trigger dialer/mail client. *(Exception: the `mandeep.panwar@` link is missing `mailto:` — see §1.2.)* |

### Mobile network performance (Chromium CDP throttling) — 🔴
Home page, mobile viewport:
| Profile | Load event | FCP |
|---|---|---|
| 4G (~9 Mbps, 60 ms) | 12.5 s | 3.2 s |
| Fast 3G (~1.6 Mbps, 150 ms) | **57.3 s** | 7.1 s |
| Slow 3G (~400 kbps, 400 ms) | **timeout > 90 s** | — |

🔴 The page is **too heavy for real-world mobile networks.** Even on 4G the load event is 12.5 s; on 3G it ranges from unbearable to unusable. This is the single highest-impact issue for actual visitors on phones — and it is the same root cause as §1.1 (page weight + TTFB).

---

## Prioritized Recommendations

**Do first (High impact):**
1. **Cut page weight.** Resize/recompress oversized images (the multiple ~1.3 MB WebPs), add responsive `srcset`, and **lazy-load** below-the-fold images + YouTube/Maps embeds (load on click). Target Why i2V from ~15 MB to <3 MB.
2. **Fix the Terms-of-Use footer link** — use absolute `/terms-of-use/` (currently 404s on every sub-page).
3. **Add alt text** to meaningful images (and explicit `alt=""` on decorative ones).

**Do next (Medium):**
4. Improve **TTFB** — add server/edge caching or a CDN; the ~1.5 s server response gates every page.
5. Fix the **`mailto:` link** (`mandeep.panwar@…`) and the broken **`/resources/i2v-vms-pre-installer-1/`** download.
6. Add `<main>` and `<footer>` landmarks, a **skip link**, a visible **`:focus-visible`** style, and convert the **mobile menu toggle to a `<button>`** with `aria-expanded`.

**Polish (Low):**
7. Standardize **brand capitalization** (pick "i2V"), reduce Home to one `<h1>`, add a fuller **CSP**, and add `autocomplete`/`required` attributes to contact-form fields.

---

## Testing Limitations (transparency)
- **No browser-automation MCP** was connected; testing used the project's Playwright install driving real browser engines.
- **WebKit** is the Safari rendering engine but **not** native macOS/iOS Safari hardware; **devices are emulated** (viewport/DPR/touch/UA), not physical phones/tablets.
- **3G/4G/5G** results use Chromium **CDP network emulation**, not real cellular radios. (5G is effectively equivalent to the unthrottled broadband numbers in §1.1.)
- **Form submission** was validated (client-side validation, field inventory) but **not submitted end-to-end** to avoid sending live leads and tripping reCAPTCHA.
- Image **alt** counts include intentionally-decorative images (`alt=""`), so the true "missing meaningful alt" figure is somewhat lower than the raw 70%.
