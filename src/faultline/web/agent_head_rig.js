// FAULTLINE ZERO — 3D Curved Agent Head Rig
// True 3D perspective rotation around the anchored neck pivot.
// Eyes lead the gaze, head follows with natural damping.

const clamp = (value, limit) => Math.max(-limit, Math.min(limit, value));

export class AgentHeadRig {
  constructor(root, hero) {
    this.root = root;
    this.hero = hero;
    this.canvas = root.querySelector('.agent-head-canvas');
    this.ctx = this.canvas.getContext('2d');
    this.svg = root.querySelector('svg');
    this.reduced = matchMedia('(prefers-reduced-motion: reduce)');

    // Head rotation: [yaw, pitch] in radians
    this.position = [0, 0];
    this.velocity = [0, 0];
    this.target = [0, 0];
    this.eyes = [0, 0];

    // Tracking state
    this.running = false;
    this.frame = 0;
    this.previous = 0;
    this.lastDraw = 0;
    this.hasPointer = false;
    this.lastPointerTime = 0;

    // Canvas resolution: 280x300 for crisp 2x retina display
    this.width = 280;
    this.height = 300;
    this.canvas.width = this.width;
    this.canvas.height = this.height;
    this.image = this.ctx.createImageData(this.width, this.height);

    // Event listeners
    this.onPointerMove = event => {
      if (!this.running || this.reduced.matches || event.pointerType === 'touch') return;
      this.lastPointerTime = performance.now();
      this.hasPointer = true;

      const head = this.getHeadCenter();
      if (!head) return;

      const dx = event.clientX - head.cx;
      const dy = event.clientY - head.cy;

      // Distance damping: smooth saturation mapping
      const distDamping = Math.max(140, head.scale * 280);
      const rawYaw = Math.atan2(dx, distDamping);
      const rawPitch = -Math.atan2(dy, distDamping * 1.15);

      // Natural physiological limits:
      // Horizontal yaw: approximately ±30° (±0.52 rad)
      // Vertical pitch: approximately ±15° (±0.26 rad)
      this.target[0] = clamp(rawYaw, 0.52);
      this.target[1] = clamp(rawPitch, 0.26);
    };

    this.onPointerLeave = () => {
      this.hasPointer = false;
      this.target[0] = 0;
      this.target[1] = 0;
    };

    this.onResize = () => {
      // Re-anchor on viewport resize without jumps
      if (!this.hasPointer) {
        this.target[0] = 0;
        this.target[1] = 0;
      }
    };

    this.reducedListener = () => {
      const wasRunning = this.running;
      this.stop();
      if (wasRunning) this.start();
    };

    // Attach listeners at window / document level for global page tracking
    window.addEventListener('pointermove', this.onPointerMove, { passive: true });
    document.addEventListener('mouseleave', this.onPointerLeave);
    window.addEventListener('blur', this.onPointerLeave);
    window.addEventListener('resize', this.onResize, { passive: true });
    this.reduced.addEventListener('change', this.reducedListener);

    this.draw(0);
  }

  getHeadCenter() {
    if (!this.svg) return null;
    const rect = this.svg.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return null;
    const scale = Math.min(rect.width / 600, rect.height / 520);
    // In SVG viewBox (600x520), visual head center is at cx=300, cy=183
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + (rect.height - 520 * scale) / 2 + 183 * scale;
    return { cx, cy, scale };
  }

  surface(longitude, latitude, radius = 49) {
    // 3D Ellipsoid surface point: head radius 49 horizontal, 49 * 1.08 vertical
    // Neck pivot is anchored 50 units below head center
    return [
      radius * Math.sin(longitude) * Math.cos(latitude),
      radius * 1.08 * Math.sin(latitude) - 50,
      radius * Math.cos(longitude) * Math.cos(latitude)
    ];
  }

  rotate([x, y, z], normal = false) {
    // Rotates around anchored neck pivot (yaw horizontally, pitch vertically)
    // Optional subtle roll coupled with yaw (up to ±1.5°) for organic realism
    const [yaw, pitch] = this.position;
    const roll = normal ? 0 : clamp(-yaw * 0.05, 0.026);

    const cy = Math.cos(yaw), sy = Math.sin(yaw);
    const cp = Math.cos(pitch), sp = Math.sin(pitch);
    const cr = Math.cos(roll), sr = Math.sin(roll);

    // Yaw rotation
    const rx = x * cy + z * sy;
    const rz = -x * sy + z * cy;

    // Pitch rotation
    const py = y * cp - rz * sp;
    const pz = y * sp + rz * cp;

    // Subtle roll
    const fx = rx * cr - py * sr;
    const fy = rx * sr + py * cr;

    return [fx, fy, pz];
  }

  project(point) {
    const [x, y, z] = point;
    const perspective = 550 / (550 - z);
    return [70 + x * perspective, 124 + y * perspective];
  }

  draw(time) {
    const ctx = this.ctx;
    const pixels = this.image.data;
    pixels.fill(0);

    const [yaw, pitch] = this.position;
    const c = Math.cos(yaw), s = Math.sin(yaw);
    const p = Math.cos(pitch), q = Math.sin(pitch);

    // Camera origin in rotated local ellipsoid coordinate frame
    const ox = -550 * p * s;
    const oy = 550 * q + 50;
    const oz = 550 * p * c;

    const rx = 49 * 49;
    const ry = (49 * 1.08) ** 2;
    const C = (ox * ox + oz * oz) / rx + (oy * oy) / ry - 1;

    // Raycast active bounding box (px: 36..244, py: 36..260)
    for (let py = 36; py < 260; py++) {
      const vy = (py / 2 - 124) / 550;
      const iy = vy * p - q, iz = -vy * q - p;

      for (let px = 36; px < 244; px++) {
        const vx = (px / 2 - 70) / 550;
        const dx = vx * c - iz * s, dz = vx * s + iz * c;
        const A = (dx * dx + dz * dz) / rx + (iy * iy) / ry;
        const B = 2 * ((ox * dx + oz * dz) / rx + (oy * iy) / ry);
        const discriminant = B * B - 4 * A * C;
        if (discriminant < 0) continue;

        const distance = (-B - Math.sqrt(discriminant)) / (2 * A);
        const x = ox + distance * dx;
        const y = oy + distance * iy;
        const z = oz + distance * dz;

        // Surface normal in local space
        let nx = x / rx, ny = y / ry, nz = z / rx;
        const norm = Math.hypot(nx, ny, nz);
        nx /= norm; ny /= norm; nz /= norm;

        // World normal
        const wx = nx * c + nz * s;
        const wz = -nx * s + nz * c;
        const wy = ny * p - wz * q;
        const wzz = ny * q + wz * p;

        // Lighting & specular
        const light = Math.max(0, wx * -0.42 + wy * -0.53 + wzz * 0.73);
        const spec = Math.pow(Math.max(0, wx * -0.23 + wy * -0.29 + wzz * 0.93), 24);

        // Spherical coordinates on curved head surface
        const longitude = Math.atan2(x, z);
        const latitude = Math.asin(clamp(y / (49 * 1.08), 1));

        // Visor: curved squircle on 3D surface
        const cornerX = Math.max(Math.abs(longitude) - 0.70, 0);
        const cornerY = Math.max(Math.abs(latitude - 0.32) - 0.17, 0);
        const visor = cornerX * cornerX + cornerY * cornerY < 0.18 * 0.18;

        const brightness = 0.38 + light * 0.65;
        const offset = (py * 280 + px) * 4;

        if (visor) {
          // Curved obsidian visor with subtle specular reflection
          const visorSpec = Math.pow(Math.max(0, wx * -0.25 + wy * -0.32 + wzz * 0.91), 16) * 45;
          pixels[offset] = Math.min(255, 11 + light * 6 + visorSpec * 0.4);
          pixels[offset + 1] = Math.min(255, 30 + light * 14 + visorSpec * 0.9);
          pixels[offset + 2] = Math.min(255, 22 + light * 8 + visorSpec * 0.7);
        } else {
          // Mint green metallic shell
          pixels[offset] = Math.min(255, 105 * brightness + spec * 95);
          pixels[offset + 1] = Math.min(255, 166 * brightness + spec * 80);
          pixels[offset + 2] = Math.min(255, 131 * brightness + spec * 90);
        }
        pixels[offset + 3] = 255;
      }
    }

    // Paint head shell & visor to canvas
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.putImageData(this.image, 0, 0);
    ctx.setTransform(2, 0, 0, 2, 0, 0);

    // Eyes gaze shift: eyes lead the head turn
    const leadX = (this.eyes[0] - this.position[0]) * 0.38;
    const biasX = this.target[0] * 0.12;
    const lookX = clamp(leadX + biasX, 0.14);

    const leadY = -(this.eyes[1] - this.position[1]) * 0.28;
    const biasY = -this.target[1] * 0.10;
    const lookY = clamp(leadY + biasY, 0.08);

    // Natural lifelike blink cycle (every ~5.5s)
    const blinkCycle = time % 5500;
    let blink = 1.0;
    if (blinkCycle > 4400 && blinkCycle < 4580) {
      const p = (blinkCycle - 4400) / 180;
      blink = Math.max(0.06, 0.5 + 0.5 * Math.cos(p * Math.PI * 2));
    }
    if (this.reduced.matches) blink = 1.0;

    // Render glowing eyes on curved visor with near/far perspective foreshortening
    for (const side of [-1, 1]) {
      const eyeLon = side * 0.28 + lookX;
      const eyeLat = 0.29 + lookY;

      // Normal vector in camera space
      const normal = this.rotate([
        Math.sin(eyeLon) * Math.cos(eyeLat),
        Math.sin(eyeLat),
        Math.cos(eyeLon) * Math.cos(eyeLat)
      ], true);

      // Occlusion test: behind the horizon of the sphere
      if (normal[2] < 0.08) continue;

      // Near/far eye perspective:
      // When turning sideways, the eye on the receding side foreshortens horizontally
      // and softens slightly in opacity as it approaches the grazing edge
      const foreshorten = clamp(normal[2] * 1.05, 0.35, 1.0);
      const eyeAlpha = clamp((normal[2] - 0.06) / 0.26, 0.38, 1.0);

      ctx.save();
      ctx.globalAlpha = eyeAlpha;
      ctx.beginPath();

      const hRadius = 0.092 * foreshorten;
      const vRadius = 0.165 * blink;

      for (let i = 0; i <= 32; i++) {
        const t = (i / 32) * Math.PI * 2;
        const ptLon = eyeLon + Math.cos(t) * hRadius;
        const ptLat = eyeLat + Math.sin(t) * vRadius;
        const point = this.project(this.rotate(this.surface(ptLon, ptLat, 50.2)));
        if (i === 0) ctx.moveTo(point[0], point[1]);
        else ctx.lineTo(point[0], point[1]);
      }

      ctx.closePath();
      ctx.fillStyle = '#d9ffe9';
      ctx.shadowColor = '#8bffc3';
      ctx.shadowBlur = 4 * foreshorten;
      ctx.fill();
      ctx.restore();
    }
  }

  tick = now => {
    if (!this.running || this.reduced.matches) return;
    const dt = Math.min((now - (this.previous || now - 16)) / 1000, 0.033);
    this.previous = now;

    // Organic idle micro-motion when cursor is idle or pointer is absent
    const isIdle = !this.hasPointer || (now - this.lastPointerTime > 2500);
    let targetYaw = this.target[0];
    let targetPitch = this.target[1];

    if (isIdle) {
      // Subtle breathing micro-drift: ±1°
      const breathe = Math.sin(now * 0.001) * 0.018;
      const drift = Math.cos(now * 0.0007) * 0.012;
      targetYaw += breathe;
      targetPitch += drift;
    }

    // Stage A: Eyes react fast (~80ms response)
    const eyeSpeed = 1 - Math.exp(-dt * 13.5);
    this.eyes[0] += (targetYaw - this.eyes[0]) * eyeSpeed;
    this.eyes[1] += (targetPitch - this.eyes[1]) * eyeSpeed;

    // Stage B: Head follows smoothly (~240ms response, critically damped spring)
    const omega = 6.2;
    const zeta = 1.08;
    const springX = (targetYaw - this.position[0]) * (omega * omega);
    const springY = (targetPitch - this.position[1]) * (omega * omega);
    const dampX = -this.velocity[0] * (2.0 * zeta * omega);
    const dampY = -this.velocity[1] * (2.0 * zeta * omega);

    this.velocity[0] += (springX + dampX) * dt;
    this.velocity[1] += (springY + dampY) * dt;
    this.position[0] += this.velocity[0] * dt;
    this.position[1] += this.velocity[1] * dt;

    this.draw(now);
    this.frame = requestAnimationFrame(this.tick);
  };

  start() {
    this.running = true;
    if (!this.frame && !this.reduced.matches) {
      this.previous = 0;
      this.frame = requestAnimationFrame(this.tick);
    }
  }

  stop() {
    this.running = false;
    cancelAnimationFrame(this.frame);
    this.frame = 0;
    this.previous = 0;
    this.position = [0, 0];
    this.velocity = [0, 0];
    this.target = [0, 0];
    this.eyes = [0, 0];
    this.draw(0);
  }

  destroy() {
    this.stop();
    window.removeEventListener('pointermove', this.onPointerMove);
    document.removeEventListener('mouseleave', this.onPointerLeave);
    window.removeEventListener('blur', this.onPointerLeave);
    window.removeEventListener('resize', this.onResize);
    this.reduced.removeEventListener('change', this.reducedListener);
  }
}
