---
name: ExamGuard
description: A calm cinematic supervision tool for detecting suspected cell phone use in exam contexts.
colors:
  bg: "#050805"
  bg-soft: "#0c110c"
  panel: "#ffffff0b"
  panel-strong: "#ffffff13"
  text: "#f4f1e8"
  muted: "#b5b3ad"
  line: "#f4f1e824"
  line-strong: "#f4f1e83d"
  olive: "#aebf7a"
  accent: "#dceea2"
  accent-strong: "#c7f35a"
  alert: "#e8876f"
  alert-bg: "#341a14"
  warning: "#d6a85c"
  scan-cyan: "#8dd9d0"
typography:
  landingDisplay:
    fontFamily: "Be Vietnam Pro, Plus Jakarta Sans, Inter, system-ui, sans-serif"
    fontSize: "clamp(55px, 8vw, 96px)"
    fontWeight: 800
    lineHeight: 1.08
    letterSpacing: "-0.015em"
    usage: "Vietnamese marketing headings"
  display:
    fontFamily: "Be Vietnam Pro, Plus Jakarta Sans, Inter, system-ui, sans-serif"
    fontSize: "clamp(64px, 8vw, 118px)"
    fontWeight: 800
    lineHeight: 0.98
    letterSpacing: "0"
  headline:
    fontFamily: "Be Vietnam Pro, Plus Jakarta Sans, Inter, system-ui, sans-serif"
    fontSize: "clamp(42px, 6vw, 88px)"
    fontWeight: 700
    lineHeight: 1.04
    letterSpacing: "0"
  title:
    fontFamily: "Be Vietnam Pro, Plus Jakarta Sans, Inter, system-ui, sans-serif"
    fontSize: "clamp(28px, 3.5vw, 52px)"
    fontWeight: 700
    lineHeight: 1.08
    letterSpacing: "0"
  body:
    fontFamily: "Be Vietnam Pro, Plus Jakarta Sans, Inter, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.68
    letterSpacing: "0"
  label:
    fontFamily: "Be Vietnam Pro, Plus Jakarta Sans, Inter, system-ui, sans-serif"
    fontSize: "0.82rem"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "0.06em"
  mono:
    fontFamily: "IBM Plex Mono, JetBrains Mono, Consolas, monospace"
    fontSize: "0.73rem"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "0"
rounded:
  sm: "14px"
  md: "18px"
  lg: "28px"
  xl: "30px"
  pill: "999px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "18px"
  lg: "28px"
  xl: "48px"
  section: "142px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.bg}"
    rounded: "{rounded.pill}"
    padding: "0 20px"
    height: "52px"
  button-secondary:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.text}"
    rounded: "{rounded.pill}"
    padding: "0 20px"
    height: "52px"
  nav-command:
    backgroundColor: "{colors.text}"
    textColor: "{colors.bg}"
    rounded: "{rounded.pill}"
    padding: "0 24px"
    height: "54px"
  panel-card:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.text}"
    rounded: "{rounded.lg}"
    padding: "24px"
  input-field:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: "0 14px"
    height: "50px"
  alert-detect-card:
    backgroundColor: "#d7ddb4"
    textColor: "#15180f"
    rounded: "{rounded.lg}"
    padding: "44px"
  alert-high-card:
    backgroundColor: "{colors.alert-bg}"
    textColor: "{colors.text}"
    rounded: "{rounded.lg}"
    padding: "44px"
---

# Design System: ExamGuard

## 1. Overview

**Creative North Star: "The Cinematic Supervision Console"**

ExamGuard should feel like a premium control surface inside a quiet exam operations room: cinematic enough to earn confidence, restrained enough to stay useful under pressure. The system uses deep charcoal surfaces, ivory text, pale olive actions, and muted alert tones to make evidence feel clear without turning every screen into an alarm.

This is a product interface, not a decorative landing page. The hero can carry an editorial atmosphere, but upload forms, camera controls, warnings, and results must stay familiar and fast. The visual system rejects broken Streamlit layering, nested iframe energy, wedding/floral references, cyberpunk neon, loud lime panels, decorative grids, random squiggles, cluttered fake metrics, and hard-to-read Vietnamese serif headings.

**Key Characteristics:**
- Dark cinematic background with evidence-focused foreground controls.
- Vietnamese-safe sans typography across headings, labels, forms, and navigation.
- Pale olive as a rare action and detection color, not a blanket decoration.
- Soft tonal layering, subtle borders, and glass only where it supports camera or evidence context.
- Motion is calm, short, and optional through reduced-motion support.

## 2. Colors

The palette is a restrained institutional dark scheme: near-black operational surfaces, warm ivory text, pale olive primary action, and muted coral alerts.

### Primary
- **Exam Room Black** (`bg`): The body and hero foundation. Use it for primary page backgrounds and media frames.
- **Pale Evidence Olive** (`accent`): Primary actions, focus rings, detector labels, and selected states. Its rarity is what makes it feel important.
- **Cell Signal Olive** (`olive`): Secondary support color for borders, subdued chips, and detection-adjacent surfaces.

### Tertiary
- **Muted Violation Coral** (`alert`): Warning text, live status dots, and HIGH alert accents. It must feel serious, not theatrical.
- **Deep Alert Burgundy** (`alert-bg`): HIGH alert cards and violation surfaces where the UI needs more gravity than a red label.

### Neutral
- **Ivory Evidence Text** (`text`): Primary foreground text and high-priority labels.
- **Muted Ivory Text** (`muted`): Body support text, descriptions, metadata, and inactive navigation.
- **Soft Divider Line** (`line`, `line-strong`): Borders and dividers. Lines should stay quiet and never become decorative scaffolding.
- **Glass Panel** (`panel`, `panel-strong`): Panels, result cards, and control surfaces on dark backgrounds.

### Named Rules
**The Rare Olive Rule.** Pale olive is reserved for actions, detection, and focus. Never flood large surfaces with `accent-strong`; it turns supervision into neon signage.

**The Evidence Contrast Rule.** Body text must remain readable over dark media. If a photo sits behind copy, add a real gradient overlay before lowering text contrast.

## 3. Typography

**Display Font:** Be Vietnam Pro, with Plus Jakarta Sans, Inter, system-ui fallbacks.  
**Body Font:** Be Vietnam Pro, with Plus Jakarta Sans, Inter, system-ui fallbacks.  
**Label/Mono Font:** IBM Plex Mono, with JetBrains Mono and Consolas fallbacks.

**Vietnamese-First Typography:** Be Vietnam Pro is used across the landing page, navigation, product controls, evidence labels, and all tool surfaces. The interface no longer uses an editorial serif because every public-facing heading is Vietnamese.

**Character:** A single Vietnamese-safe sans family keeps the product calm and credible. Mono is used only for live frame metadata, machine status, and technical readouts.

### Hierarchy
- **Display** (800, `clamp(64px, 8vw, 118px)`, `0.98`): Vietnamese hero and major product statements. Split long headlines into balanced spans so diacritics breathe, and never tighten tracking beyond `-0.015em`.
- **Landing Display** (800, `clamp(55px, 8vw, 96px)`, `1.08`): Vietnamese marketing statements on the public landing page, with tracking no tighter than `-0.015em`.
- **Headline** (700, `clamp(42px, 6vw, 88px)`, `1.04`): Major page and section headings.
- **Title** (700, `clamp(28px, 3.5vw, 52px)`, `1.08`): Large cards and feature panels.
- **Body** (400, `16px`, `1.68`): Explanatory copy, control descriptions, and result text. Keep prose near 65-75ch.
- **Label** (800, `0.82rem`, `0.06em`, uppercase only when short): Field labels, compact states, and process labels.
- **Mono Metadata** (800, `0.73rem`, no tracking): Camera bars, frame status, detection confidence, and machine-readable UI.

### Named Rules
**The Vietnamese-First Rule.** Never use serif display type for Vietnamese headings in this product. Vietnamese headings use Be Vietnam Pro at 700-800 weight, at least `1.08` line-height, and no tighter than `-0.015em` tracking so diacritics never collide with neighboring lines.

**The Mono Containment Rule.** Mono is evidence metadata only. Buttons, headings, body copy, and form labels stay sans.

## 4. Elevation

The system uses a hybrid of tonal layering, soft borders, and deep ambient shadows. Cards are mostly dark tonal panels; shadows appear on floating evidence frames, control panels, and camera surfaces to separate them from photographic backgrounds.

### Shadow Vocabulary
- **Ambient Control Shadow** (`0 32px 96px rgba(0, 0, 0, 0.42)`): Use for control panels, camera stage, and important floating containers.
- **Hero Evidence Shadow** (`0 34px 120px rgba(0, 0, 0, 0.46)`): Use only for the detection frame on the hero or similarly important visual evidence.
- **Soft Panel Shadow** (`0 22px 80px rgba(0, 0, 0, 0.22)`): Use for media cards that need depth without competing with the result.

### Named Rules
**The Evidence Floats Rule.** Only evidence, controls, and media preview surfaces may float. Decorative boxes should stay flat or disappear.

## 5. Components

### Buttons
- **Shape:** Full pill for command buttons (`999px`) so primary actions are immediately recognizable.
- **Primary:** Pale Evidence Olive background with Exam Room Black text (`accent` on `bg`), `52px` height, `0 20px` padding, 800 weight.
- **Hover / Focus:** Hover translates up by `-2px`; focus uses a visible olive outline. Never remove focus visibility.
- **Secondary:** Transparent dark panel with soft border and ivory text. Use for secondary camera/video actions, never for destructive actions.

### Chips
- **Style:** Use compact pill chips only for short metadata, source labels, or detection states.
- **State:** Active chips may use olive text or border; inactive chips stay muted. Avoid large chip rows that imitate fake dashboards.

### Cards / Containers
- **Corner Style:** Product cards use restrained large radii (`18px` to `30px`). Hero evidence may use `28px`; avoid escalating every card above that.
- **Background:** Default cards use Glass Panel. Alert cards may use Pale Olive or Deep Alert Burgundy when the card represents the actual process state.
- **Shadow Strategy:** Apply Ambient Control Shadow to forms and camera panels; use border-only panels for passive content.
- **Border:** Soft ivory border at low alpha. Borders are structural, not decorative stripes.
- **Internal Padding:** Most panels use `24px`; large alert cards use `30px-44px`.

### Inputs / Fields
- **Style:** Dark filled fields with a soft border, `16px-18px` radius, `50px` minimum height, and ivory text.
- **Focus:** Border shifts to Pale Evidence Olive with a soft `0 0 0 3px` focus halo.
- **Error / Disabled:** Error states use muted coral on a dark red tint; disabled states reduce opacity without changing layout.

### Navigation
- **Style:** Fixed top navigation over the hero. Brand left, simple text links center, pill CTA right.
- **Typography:** Sans, 700-800 weight, no heavy background capsule around the whole nav.
- **Default / Hover / Active:** Inactive links use muted ivory; active and hover use ivory plus a thin underline. CTA uses ivory fill and dark text.
- **Mobile:** Collapse menu into a compact overlay; keep brand and toggle visible, avoid horizontal overflow.

### Detection Frame
- **Style:** Floating dark glass evidence panel with a soft border, subdued image crop, mono toolbar, olive bounding box, and compact confidence labels.
- **Role:** Hero demonstration and live evidence metaphor. It should support the product promise, not look like a fake dashboard.

## 6. Do's and Don'ts

### Do:
- **Do** keep the interface calm enough for an operator to use during a real supervision session.
- **Do** use Be Vietnam Pro or the configured sans fallbacks for every Vietnamese heading and label.
- **Do** preserve the image / video / camera workflow vocabulary across screens.
- **Do** show visible evidence before escalating alert language.
- **Do** keep motion short, ease-out, and disabled through `prefers-reduced-motion`.
- **Do** protect contrast when text sits over photographic backgrounds.

### Don't:
- **Don't** look like a broken Streamlit app, nested iframe UI, wedding/floral landing page, cyberpunk dashboard, loud neon interface, or fake demo showcase.
- **Don't** use hard-to-read Vietnamese serif headings.
- **Don't** flood the screen with neon lime, heavy purple gradients, decorative grids, random squiggles, or fake metrics.
- **Don't** add side-stripe accent borders, gradient text, or decorative glass panels that do not support evidence review.
- **Don't** let upload controls, result cards, tables, or camera panels overflow horizontally on mobile.
- **Don't** hide missing model, camera, upload, Telegram, or alert errors behind vague copy.
