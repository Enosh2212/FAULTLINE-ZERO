# Vendored graph libraries

- Cytoscape.js 3.33.1 — https://github.com/cytoscape/cytoscape.js — MIT (CYTOSCAPE-LICENSE)
- elkjs 0.11.0 — https://github.com/kieler/elkjs — EPL-2.0 (ELK-LICENSE.md)

Downloaded from version-pinned npm artifacts via jsDelivr. Served locally; runtime needs no CDN. ELK is used directly to calculate positions consumed by Cytoscape's preset layout, avoiding an extension compatibility dependency. If ELK fails, an explicit horizontal semantic layout is used and the fallback is shown. Rendered arrows always use original graph direction; the layout-only constraint for VALIDATES places the test after the invariant.
