# EduPortal Design System

This document is the **single source of truth** for EduPortal UI styling.

## 1) Design Principles

- **Clarity first**: readable typography, high-contrast text, predictable layouts.
- **Soft surfaces**: light gradients, subtle borders, and low-elevation shadows.
- **Rounded geometry**: generous radii on containers and controls.
- **Consistent interaction**: smooth transitions (`0.15s`–`0.3s`) and focus rings.

## 2) System Configuration (How styles are applied)

- **Tailwind CSS**: loaded via CDN
  - `https://cdn.jsdelivr.net/npm/tailwindcss@3.4.15/dist/tailwind.min.css`
- **Tailwind Browser Runtime**:
  - `https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4`
- **Icons**: Iconify
  - `https://code.iconify.design/3/3.1.1/iconify.min.js`
- **No local Tailwind config detected** (`tailwind.config.*` not present). The project relies on Tailwind defaults + template-level styles.

**Source-of-truth templates for design tokens**

- `templates/base.html` (Student app shell + “Minimal” component styles)
- `templates/admin_base.html` (Admin component styles)
- `templates/login.html`, `templates/admin_login.html` (Splash screen + auth card)
- `templates/register.html` (Wizard + auth card)

## 3) Color System

This project primarily uses Tailwind’s **Slate** scale for neutrals and **Indigo/Purple** as the main brand accent.

### 3.1 Neutrals (Slate)

Used heavily via Tailwind classes:

- `bg-gradient-to-br from-slate-50 to-slate-100` (page background)
- `text-slate-800` (default text)
- `text-slate-900` (headings)
- `text-slate-500` / `text-slate-400` (secondary text)
- `border-slate-200` / `border-slate-300` (borders & dividers)
- `bg-slate-50` / `bg-slate-100` / `bg-slate-200` (soft surfaces)
- `bg-slate-900` / `to-slate-800` (dark surfaces)

Additional neutral hex values used in inline styles:

- `#f8fafc` (table header background)
- `#e2e8f0` (borders, soft button backgrounds, rings, etc.)
- `#cbd5e1` (hover border, soft button border)
- `#64748b` (muted text)
- `#334155` (hover text / focus border)
- `#0f172a` / `#020617` (dark primary/admin)

### 3.2 Brand Accent (Indigo / Purple)

Used for primary actions and highlights:

- **Primary gradient**: `linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)`
- **Primary hover gradient**: `linear-gradient(135deg, #4f46e5 0%, #4338ca 100%)`
- Tailwind usage:
  - `bg-indigo-50`, `text-indigo-600`, `text-indigo-700`
  - `from-indigo-500 to-purple-600`

### 3.3 Status / Semantic Colors

- **Success (Emerald)**
  - Tailwind: `bg-emerald-50`, `text-emerald-700`, `border-emerald-200`
  - Primary success CTA: `from-emerald-500 to-emerald-600`
- **Danger (Rose)**
  - Tailwind: `bg-rose-50`, `text-rose-700`, `border-rose-200`
  - Admin danger button hex:
    - `#fff1f2` (bg)
    - `#be123c` (text)
    - `#ffe4e6` (hover bg)
- **Info (Blue / Sky)**
  - Progress bar gradient: `linear-gradient(90deg, #3b82f6, #8b5cf6)`
  - Attendance ring uses: `#0ea5e9`

### 3.4 Data Visualization (Attendance “heat”)

Inline palette in `templates/base.html`:

- `level-0`: `#ebedf0`
- `level-1`: `#9be9a8`
- `level-2`: `#40c463`
- `level-3`: `#30a14e`
- `level-4`: `#216e39`

## 4) Typography

The project uses **Tailwind defaults** (system-ui stack). No custom font-family was found.

### 4.1 Type Scale (observed)

Common Tailwind sizes used:

- `text-xs` (labels, metadata)
- `text-sm` (body, buttons)
- `text-lg` (section titles)
- `text-xl` (page header title)

Custom sizes used:

- `text-[11px]` (mobile nav label)

### 4.2 Font Weights

- `font-medium` (buttons, labels)
- `font-semibold` (headers, card titles)
- `font-bold`/`700` (splash branding)

### 4.3 Letter Spacing / Case

- “App brand” label: `uppercase tracking-[0.2em]`
- Form labels: `uppercase tracking-wider`
- Admin table headers:
  - `font-size: 12px`
  - `letter-spacing: 0.06em`
  - `text-transform: uppercase`

## 5) Spacing (Padding, Margin, Layout)

Spacing is primarily Tailwind spacing scale.

### 5.1 Layout Containers

- **Page background**: `min-h-screen bg-gradient-to-br from-slate-50 to-slate-100`
- **App layout grid**: `grid grid-cols-1 md:grid-cols-[280px_1fr]`
- **Main padding**:
  - Student content area: `p-6 md:p-8`
  - Admin content area: `p-4 sm:p-6 md:p-8`
- **Sidebars**: `p-6` with `gap-6`

### 5.2 Form spacing

- Forms often use `space-y-4` or `space-y-6`
- Labels typically use `mb-2`

## 6) Radius (“Softness”)

The interface leans toward **rounded** components.

Observed radii:

- `rounded-xl` (controls, buttons, nav items)
- `rounded-2xl` (cards, avatar containers)
- `rounded-t-3xl` (bottom sheet)
- `rounded-full` / `999px` (pills, dots)

Inline radii:

- `12px` (buttons/inputs)
- `14px` (avatar)
- `16px` (cards)
- `20px` (badge)
- `24px` (splash logo)

## 7) Elevation (Shadows)

The project uses subtle shadows with Slate-based RGBA.

### 7.1 Key shadow tokens (observed)

- **App shell / Auth card shadow**
  - `0 30px 80px rgba(15, 23, 42, 0.15), 0 2px 10px rgba(15, 23, 42, 0.06)`
- **Card base**
  - `0 1px 3px rgba(15, 23, 42, 0.04)`
- **Card hover**
  - `0 4px 12px rgba(15, 23, 42, 0.08)`
- **Avatar**
  - `0 2px 8px rgba(15, 23, 42, 0.08)`
- **Admin soft button**
  - `0 1px 2px rgba(15, 23, 42, 0.06)`
- **Splash logo**
  - `0 20px 60px rgba(0, 0, 0, 0.3)`

## 8) Motion & Transitions

### 8.1 Transition timings

- `0.15s` (admin buttons)
- `0.2s` (minimal card/button/nav/input)
- `0.3s` (progress bar width/opacity; bottom-sheet transforms)

### 8.2 Animations

- **Fade-in content** (`templates/base.html`)
  - `fadeIn`: `opacity` + `translateY(10px)`
- **Splash screen** (`templates/login.html`, `templates/admin_login.html`)
  - `splash-pulse`: scale `1.00` → `1.05`
  - `splash-fade-in`: `opacity` + `translateY(20px)`

## 9) Focus States & Accessibility

Focus patterns are consistent:

- Inputs use:
  - `focus:outline-none`
  - `focus:border-...`
  - `focus:ring-4 focus:ring-.../10`
- Admin input focus (inline):
  - `box-shadow: 0 0 0 4px rgba(15, 23, 42, 0.08)`

Guidelines:

- Use **ring + border** for focus visibility.
- Avoid removing focus state unless an alternative focus style is present.

## 10) Component System (Project Elements)

### 10.1 Student “Minimal” components (`templates/base.html`)

- **Card**: `.minimal-card`
  - White background, `16px` radius, `1px` slate border, subtle shadow, hover elevation.
- **Button**: `.minimal-btn` + `.minimal-btn-primary`
  - `12px` radius, gradient primary, hover lift + shadow.
- **Input**: `.minimal-input`
  - `12px` radius, slate border, soft indigo ring on focus.
- **Navigation item**: `.minimal-nav-item` (+ `.active`)
  - Rounded, padded, muted slate text; soft hover surface.
- **Badge**: `.minimal-badge`
  - Pill-like rounded corners, small text.
- **Avatar**: `.minimal-avatar`
  - Rounded, border + subtle shadow.

### 10.2 Admin components (`templates/admin_base.html`)

- **Card**: `.admin-card`
  - Same surface language as minimal card.
- **Table header**: `.admin-table thead`, `.admin-table th`
- **Input**: `.admin-input`
  - Slightly larger padding (`12px 16px`), dark/slate focus ring.
- **Buttons**:
  - `.admin-btn` base (inline-flex, `12px` radius)
  - `.admin-btn-primary` (dark slate)
  - `.admin-btn-soft` (soft slate surface)
  - `.admin-btn-danger` (rose)
- **Pill**: `.admin-pill` (fully rounded)

### 10.3 Auth cards (login/register)

- Shared auth card style:
  - `bg-white border border-slate-200 rounded-2xl`
  - shadow token: `shadow-[0_30px_80px_rgba(15,23,42,0.15),0_2px_10px_rgba(15,23,42,0.06)]`

## 11) Recommended Usage Rules

- Prefer **Tailwind utilities** for layout and spacing.
- Reuse existing component classes (`minimal-*`, `admin-*`) when matching existing UI.
- When introducing new colors or shadows, add them here first (this file stays authoritative).

## 12) Future Improvements (Optional)

If you want a stricter design system:

- Add a local `tailwind.config.js` and define `theme.extend` tokens.
- Move inline `<style>` blocks into a single `static/styles.css` and keep templates utility-only.
- Define CSS variables for tokens (`--color-*`, `--radius-*`, `--shadow-*`) to reduce repetition.
