# FAULTLINE ZERO — Motion System & Animation Engineering

## Motion Philosophy
Motion in FAULTLINE ZERO serves a functional, communicative purpose. It provides immediate spatial awareness of dependency paths, commit propagation, and agent reasoning steps without distracting or introducing lag.

---

## 1. 3D Spatial Network Canvas (`hero_network.js`)

The hero section features a custom HTML5 canvas rendering an interactive 3D spatial network of service nodes and invariant links.

### Technical Implementation
- **Coordinate Space**: 3D coordinates `(x, y, z)` with perspective projection `focalLength = 400`:
  $$\text{scale} = \frac{f}{\text{distance} + z}$$
  $$x' = x \times \text{scale} + \text{cx}, \quad y' = y \times \text{scale} + \text{cy}$$
- **Service Clusters**:
  - `S-GATEWAY` (Ingress entry point)
  - `S-PAYMENTS` (Payment processing service)
  - `S-ORDERS` (Order management service)
  - `S-INVENTORY` (Stock reservation service)
  - `S-REFUNDS` (Refund processing service)
  - `INV-PAY-01` (Payment idempotency rule, flagged with dynamic break alert)
  - `INV-REFUND-01` (Refund ledger invariant)
- **Commit Pulse Waves**:
  - Continuous data packets travel along the edges between nodes at constant velocity.
  - As pulses cross nodes, subtle radial alpha ripples expand and dissipate.
- **Dynamic Anomaly Highlighting**:
  - `INV-PAY-01` pulses with a coral warning halo (`rgba(224, 82, 68, 0.4)`), visualizing live detection of duplicate charge vulnerabilities.

### Performance & Energy Management
- **`requestAnimationFrame` Optimization**: Zero DOM mutations during animation frames; all rendering occurs directly on the canvas buffer.
- **`IntersectionObserver` Auto-Pause**: When the user scrolls past the hero section into lower documentation sections, the canvas loop automatically pauses to preserve GPU/CPU cycles.
- **Reduced Motion Support**:
  When `@media (prefers-reduced-motion: reduce)` is detected, node velocities drop to zero, pulse waves are disabled, and a static, high-contrast topological diagram is rendered.

---

## 2. Cytoscape.js Investigation Canvas

The central investigation viewport uses Cytoscape.js for interactive topological manipulation.

### Dynamic Layout & Physics
- Uses the `cose` (Compound Spring Embedder) physics layout algorithm with tuned spring constants:
  - Node repulsion: `8000`
  - Ideal edge length: `100`
  - Gravity: `0.25`
  - Animated transitions: `500ms` with cubic-bezier easing.
- **Live Traversal Highlighting**:
  When an investigation runs, the traversed path from Git Change → Modified Symbol → Business Invariant illuminates sequentially in mint green (`#29C481`).
- **Focus & Zoom Transitions**:
  Clicking any node smoothly animates the camera viewport to center and zoom (`fit(node, 100)` over `400ms`).

---

## 3. UI Micro-Transitions

- **Button Press Physics**:
  Interactive buttons employ a tactile 0.98 scale transition with quick release:
  ```css
  transition: transform 0.12s cubic-bezier(0.4, 0, 0.2, 1),
              box-shadow 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  button:active {
    transform: scale(0.98);
  }
  ```
- **Timeline Progress Stepper**:
  The active step pulse smoothly glides across `READY → DIFF → GRAPH → SYNTHESIS → COMPARE → VERDICT` with an emerald glow trail.
- **Expandable Parameter Drawers**:
  Tool step details transition with CSS `max-height` and opacity (`cubic-bezier(0, 0, 0.2, 1)`).
