# Vouch — Signal design system

Accepted visual contract, revised 2026-10-26. The user-supplied creator growth dashboard is the
primary mood and composition reference, not a page to copy. This system applies its editorial
hierarchy, cool light canvas, restrained red/blue accents and information density to Vouch's actual
workflow. Product, security and API behavior remain governed by the canonical docs.

## Product character

Vouch should feel like a premium creator-operations product: editorial at first glance, precise in
use and trustworthy under scrutiny. Brand members need to move an authorized creator draft through
evidence and an exact-version human decision. Creators receive a warmer, simpler private view.

The product must not invent revenue, reach, compliance scores, customer quotes, creator results or
live model behavior. Find, Try and Track remain clearly labeled as deferred wherever they are shown.
The implemented Check workflow receives the strongest functional emphasis.

## Tokens

[`tokens.css`](tokens.css) is the executable token source.

| Role | Token | Value |
| --- | --- | --- |
| Cool canvas | `--color-paper` | `#F5F7FA` |
| Surface | `--color-surface` | `#FFFFFF` |
| Primary ink | `--color-ink` | `#151922` |
| Muted copy | `--color-muted` | `#687386` |
| Vouch red | `--color-brand` | `#930500` |
| Secondary blue | `--color-blue` | `#95BBEA` |
| Cool border | `--color-rule` | `#DCE3EC` |

Derived soft/strong tokens may support hover, focus, charts and semantic states. Red marks primary
actions, selected navigation and important decisions; it is not a universal card background. Blue
supports evidence, status context and secondary emphasis. White remains the dominant content
surface. Shadows are restrained and reserved for hierarchy, not every box.

## Typography

- Editorial headings: the local system serif stack in `--font-editorial`.
- UI headings and metrics: self-hosted Space Grotesk.
- Body, navigation and forms: self-hosted IBM Plex Sans.
- IDs, timecodes and precision metadata: IBM Plex Mono with tabular numerals.

Large serif headings carry product personality. Dense workflow content stays sans-serif. No
handwriting, doodles, gradient text or decorative copy. Heading levels remain semantic.

## Shared frame and components

- Desktop uses a white persistent rail, slim environment disclosure and a sticky workspace bar.
- Mobile uses a compact brand row and two real navigation destinations; deferred modules are not
  converted into fake links.
- Buttons, fields, badges, focus rings, notices, empty/error/loading states and tables use shared
  tokens and a 44px minimum actionable target.
- Cards differ by purpose: campaigns are dense data, capabilities are blue disclosure, approval is
  red-tinted decision context, storage is a compact meter and evidence is calm and cool.
- Every visible control works, is disabled with an explanation, or truthfully identifies deferred
  functionality.

## Surface character

### Workspace

An editorial overview combines a real-data summary, original creator/product review illustration,
honest module status and a compact campaign pipeline. Campaign, next-step and market counts come
from loaded API data; loading and failure show an em dash. The hero's campaign CTA opens and focuses
the existing form. Search filters the loaded campaign table.

### Campaign review

Campaign review is a professional workbench. The versioned upload, authorization, Check lifecycle,
evidence, findings and exact-version approval retain their existing order and semantics. Blue marks
evidence and processing; red marks consequential decisions; green remains reserved for completed
states. Approval never looks automatic or legally certified.

### Sign-in

Sign-in pairs a Vouch-red editorial introduction with the existing optional interactive ribbon and
a quiet white authentication panel. The form remains usable without WebGL, at reduced motion and
within a 320×900 viewport. Google stays visibly disabled until the runtime provider is configured.

### Creator portal

The creator route is visually distinct from the member shell but uses the same typography and
colors. Its private-link boundary, ended/unavailable states, current draft, exact version metadata
and explicitly published feedback remain clear. It never exposes workspace navigation.

## Imagery and motion

The workspace hero uses an original, intentionally illustrative creator/product review composition;
it is decorative and never presented as a real creator, campaign result or generated Try output.
No remote stock gallery or runtime image request is required. The sign-in ribbon remains a bounded
brand study, not an analysis indicator.

Motion is limited to tactile control feedback, real loading state and the user-controlled ribbon.
Reduced motion removes decorative animation. No scroll-jacking, cursor follower, autoplay carousel
or fake progress is permitted.

## Responsive and accessibility acceptance

Verify 320, 375, 414, 768, 1024, 1280, 1440 and 1920px where tooling permits. Requirements:

- no document-level horizontal overflow;
- visible keyboard focus and semantic native controls;
- 4.5:1 normal-text and 3:1 large-text/control contrast;
- useful loading, empty, error, success and disabled states;
- tables transform into labeled records before becoming unreadable;
- the 320×900 sign-in fold retains the primary submit action;
- reduced motion keeps authentication and workflow controls independent of decoration.

The primary implementation is [`product-design.css`](apps/web/src/app/product-design.css) backed by
the shared tokens. Component-scoped creator and motion styles remain isolated where their trust or
rendering boundaries differ.
