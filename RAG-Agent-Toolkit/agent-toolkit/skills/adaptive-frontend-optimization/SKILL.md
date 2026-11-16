---
name: adaptive-frontend-optimization
description: Audit and incrementally optimize existing frontend workflows, responsive layout, asynchronous state and accessibility; deliver evidence-backed changes using the project's existing framework.
---

# Adaptive Frontend Optimization

Use for frontend improvement requests, reusable UI foundations, and responsive or async workflow defects. Do not turn a dashboard into a marketing page or replace the framework as a default optimization.

## Discover Before Editing

Read project instructions, package manifests, shared styles, entry points, relevant components and tests. Inspect git status and preserve unrelated work. Identify the actual product category, principal user journey, framework, component library, rendering environment and supported devices. Describe missing measurements as unknown, not failed or passed.

Read [the optimization playbook](references/playbook.md) for routing, evidence requirements and the current project's extracted lessons. Use its principles, not its project-specific paths or numeric defaults, in other repositories.

## Adaptive Decisions

- Operational tools: prioritize scanning, dense but legible content and predictable actions. Consumer content: prioritize reading and navigation. Editors: preserve canvas space and contextual controls. Marketing: use a relevant real visual and product identity only when that is the requested page.
- Reuse existing tokens and accessible components. React examples provide design ideas, not permission to insert React into Vue. Add dependencies only for a verified gap.
- Choose breakpoints from content/container failure, not device names. Prefer CSS layout; use JS observers only for behavior that requires measured dimensions.
- Fix blockers, misleading task state and lost input before visual polish. For asynchronous reads, cancel obsolete work and reject late results. For writes, cancellation does not undo server operations; require server idempotency and reconciliation.
- Let normal users operate domain actions, not internal JSON. Automatic review must still perform real checks and expose recoverable failures; never replace validation with unconditional approval.

## Execute And Verify

Capture baseline evidence before changing one ownership boundary at a time. Cover loading, empty, error, retry, success and disabled states. Test keyboard access, long/localized text, reduced motion and narrow containers. Check local clipping as well as document overflow; allow intentional scrolling only with an explicit reason.

Use the original, optional [frontend kit](assets/frontend-kit/README.md) when the host has no equivalent. It includes latest-result control, URL cleanup, scoped responsive CSS and an overflow probe. Read its limitations first. Do not automatically copy everything or globally import its CSS.

Run relevant behavior tests and host build. Browser-check meaningful routes at narrow and wide widths, including containers narrowed by sidebars; preserve screenshots and actual measurements. Report what was tested, what remains untested and how to roll back. Static source matching, screenshots alone and a successful build are not proof that a business workflow works.
