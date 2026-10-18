# FAULTLINE ZERO: phase 1 design audit and system

Stack: FastAPI serves static HTML, native ES modules and CSS. No React, Tailwind, TypeScript or frontend bundler. Motion is already installed but React Motion cannot mount without adding React. Cytoscape/ELK, Firebase Web SDK, backend sessions and graph services are preserved.

UI UX Pro Max local skill consulted. Its operations-landing and Inter typography recommendations fit the product; neon/glitch and purple defaults conflict with the requested restrained cyan/amber direction, so those palette suggestions are overridden deliberately. General web guidance: semantic HTML, visible keyboard focus, 44px controls, 4.5:1 body contrast, reduced motion and pausable decoration.

Reference attachments: liquid/metal buttons and Gateway Flow React component. Adopt their inset highlights, tactile borders and flowing paths using native CSS/SVG. Do not add shadcn, React, Tailwind, GSAP, remote iframe scripts or stock images just to host a decorative component. Existing component path is src/faultline/web, not components/ui. A disconnected TSX folder would not render in this architecture.

Tokens: charcoal #080c11; surface #10171f; raised #151e28; text #edf2f7; muted #a1afbe; cyan #8cdeeb; amber #e9bc78; border #253340. Cyan identifies interaction and graph context. Amber marks demo scope, not an invented alert. Existing execution verdict colors retain their meaning. System Inter/Segoe UI stack; no new remote font dependency. Spacing 8/12/16/24/32/48/64/96; card radius 18px; controls 10px. Hover 250ms, existing reversible scroll motion retained; reduced-motion static state and manual pause.

Phase 1: landing hero hierarchy, restrained background, current cursor-following illustration, glass-edge CTAs, section cards and evidence-tab styling, footer, landing-only header styling. Exact product hook and explanatory copy preserved; sample demo explicitly labeled. All evidence remains sourced through existing APIs.

Approval required for later work: investigation/dashboard panel hierarchy and loading states; graph explorer node selection, labels and inspector; project/memory/docs alignment. Auth design, Firebase configuration, backend APIs, environment and graph connections are outside this phase.

Validation: static frontend has no compile/build script. Check JS module syntax, Python wheel packaging (actual deployable frontend artifact), browser rendering/assets, mobile/tablet/desktop overflow, keyboard/motion states, existing demo actions and protected auth navigation. Record results in output/landing-phase1-results.json.

## User-approved palette revision
Landing now follows supplied Baroworks reference: primary muted gold #d4b34e, background #09090b, card #101012, secondary #19191d, border #29292e, soft off-white #f4f3ef. Native Apple font / locally hosted Inter retained. Video-inspired flowing particle gateway replaces the landing ASCII backdrop; auth ASCII and all product views remain unchanged. Gateway pauses offscreen/hidden, at user request and under reduced motion. No additional runtime dependency.
