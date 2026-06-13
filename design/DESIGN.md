---
name: Pro-Stream Communications
colors:
  surface: '#f8f9ff'
  surface-dim: '#d0dbed'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e6eeff'
  surface-container-high: '#dee9fc'
  surface-container-highest: '#d9e3f6'
  on-surface: '#121c2a'
  on-surface-variant: '#444653'
  inverse-surface: '#27313f'
  inverse-on-surface: '#eaf1ff'
  outline: '#757684'
  outline-variant: '#c4c5d5'
  surface-tint: '#3755c3'
  primary: '#00288e'
  on-primary: '#ffffff'
  primary-container: '#1e40af'
  on-primary-container: '#a8b8ff'
  inverse-primary: '#b8c4ff'
  secondary: '#4648d4'
  on-secondary: '#ffffff'
  secondary-container: '#6063ee'
  on-secondary-container: '#fffbff'
  tertiary: '#003d27'
  on-tertiary: '#ffffff'
  tertiary-container: '#00563a'
  on-tertiary-container: '#3fd298'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dde1ff'
  primary-fixed-dim: '#b8c4ff'
  on-primary-fixed: '#001453'
  on-primary-fixed-variant: '#173bab'
  secondary-fixed: '#e1e0ff'
  secondary-fixed-dim: '#c0c1ff'
  on-secondary-fixed: '#07006c'
  on-secondary-fixed-variant: '#2f2ebe'
  tertiary-fixed: '#6ffbbe'
  tertiary-fixed-dim: '#4edea3'
  on-tertiary-fixed: '#002113'
  on-tertiary-fixed-variant: '#005236'
  background: '#f8f9ff'
  on-background: '#121c2a'
  surface-variant: '#d9e3f6'
typography:
  headline-lg:
    fontFamily: Hanken Grotesk
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
  headline-md:
    fontFamily: Hanken Grotesk
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Hanken Grotesk
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Hanken Grotesk
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.05em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  base: 8px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  gutter: 16px
  margin-mobile: 16px
  margin-desktop: 24px
---

## Brand & Style

The visual identity of this design system is rooted in **Corporate Modernism**, prioritizing utility, speed, and information density for professional communication management. The brand personality is efficient, reliable, and transparent, aimed at logistics, accounting, and professional services where clarity is paramount.

The design system utilizes a clean, high-density layout with structured information hierarchies. It blends functional minimalism with subtle tactile cues—like soft borders and clear button states—to ensure the interface feels responsive and trustworthy. The primary objective is to reduce cognitive load in data-heavy environments while maintaining a professional, enterprise-grade aesthetic.

## Colors

The palette is anchored by a deep **Executive Blue** (#1E40AF), representing authority and stability. This is complemented by a range of functional grays and semantic colors to indicate status without overwhelming the user.

- **Primary:** Used for key actions, active navigation states, and primary buttons.
- **Secondary:** An indigo accent for secondary interactions or specific toolsets (e.g., Internal Communications).
- **Surface:** A pure white (#FFFFFF) background to maximize contrast, with light gray (#F3F4F6) for subtle container separation.
- **Semantic:** Green (#10B981) for online/success, Red (#EF4444) for urgent/closed, and Amber (#F59E0B) for pending/warning states.
- **Text:** Dark gray (#1F2937) for primary content and a medium gray (#6B7280) for metadata and timestamps.

## Typography

This design system uses **Hanken Grotesk** for primary UI elements and body text to provide a modern, sharp, and highly legible experience. **Inter** is utilized for labels and metadata (timestamps, badges) to ensure clarity at small sizes.

For mobile responsiveness, `headline-lg` scales down to 20px. The system relies heavily on weight variation (Medium vs. Regular) to distinguish between unread and read messages in list views. Line heights are kept tight (1.2 - 1.5x) to maintain the high-density requirement of a dashboard.

## Layout & Spacing

The system follows a strict **8px Grid**. Layouts are structured as a **Fluid-Fixed Hybrid**: 
- **Sidebar:** Fixed width (80px on desktop, bottom-tab bar on mobile).
- **Navigation/List Pane:** Flexible width with a minimum of 320px.
- **Content Area:** Fluid, expanding to fill remaining viewport space.

**Breakpoints:**
- **Mobile (<768px):** Single-pane view. Users navigate from list to thread.
- **Tablet (768px - 1024px):** Split-view (List + Content). Sidebar may collapse to icons only.
- **Desktop (>1024px):** Full three-pane view (Navigation + List + Content).

Padding within cards and list items is set to `md` (16px) for comfort, while utility toolbars use `sm` (8px) to maximize screen real estate.

## Elevation & Depth

Hierarchy is established through **Tonal Layering** and **Low-Contrast Outlines** rather than heavy shadows. 

- **Level 0 (Canvas):** The base background (#F9FAFB).
- **Level 1 (Panes):** Sidebar and list panes use a subtle right-hand border (1px #E5E7EB) to separate content.
- **Level 2 (Cards/Threads):** White backgrounds with a 1px #E5E7EB border. 
- **Interactive:** Elements like active message threads or hovered buttons use a very soft, ambient shadow (4px blur, 5% opacity) and a primary-colored accent border to indicate focus.
- **Modals:** High-diffuse shadows (16px blur, 10% opacity) are reserved exclusively for overlays and dropdown menus.

## Shapes

The shape language is **Soft and Professional**. A standard 4px (`0.25rem`) radius is used for most UI elements—including input fields, buttons, and list item containers—to maintain a modern look without appearing overly casual.

- **Standard (4px):** Buttons, inputs, small cards.
- **Large (8px):** Main content containers and message bubbles.
- **Pill:** Reserved for status badges (e.g., "Entregado") and notification counters to distinguish them from structural elements.

## Components

### Buttons & Controls
- **Primary:** Solid #1E40AF background, white text, 4px radius. 
- **Ghost:** Transparent background with primary-colored icon/text; used for toolbar actions (Reply, Forward).
- **Icon-Only:** Contained within a 32x32px square with a light gray border for secondary utilities.

### Sidebar Navigation
- Icons must be centered. Labels are placed directly below the icon in `label-sm` caps.
- Active state: Vertical 4px bar on the left edge + Primary-colored icon and text.

### Message Thread List
- **Unread:** Bolded name, primary-colored status dot.
- **Selected:** Light blue tint (#EFF6FF) background with a primary left-border.
- **Hover:** Very light gray tint (#F9FAFB).

### Input Fields
- Search bars use a 1px border (#D1D5DB) and an inset search icon.
- Message input area is pinned to the bottom of the thread, featuring a multi-line auto-expanding field and quick-action icons (attachment, templates) in the gutter.

### Message Bubbles
- **Inbound:** Light gray background, aligned left.
- **Outbound:** Light green or blue tint background, aligned right, with status indicators (double-check icons) in the bottom right corner.