export function renderVerificationLoader() {
  return `<section class="report-empty running-report" role="status" aria-label="Investigation in progress">
    <div class="verification-illustration" aria-hidden="true">
      <svg viewBox="0 0 320 280" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <radialGradient id="scout-sky"><stop stop-color="#254e37"/><stop offset="1" stop-color="#102219"/></radialGradient>
          <linearGradient id="scout-body" x1="120" y1="140" x2="207" y2="258" gradientUnits="userSpaceOnUse"><stop stop-color="#f1faf4"/><stop offset="1" stop-color="#b7d4c2"/></linearGradient>
          <linearGradient id="scout-metal" x1="197" y1="98" x2="229" y2="138" gradientUnits="userSpaceOnUse"><stop stop-color="#b2f1c7"/><stop offset=".5" stop-color="#70bd91"/><stop offset="1" stop-color="#367655"/></linearGradient>
          <radialGradient id="scout-lens" cx=".35" cy=".3"><stop stop-color="#bdffe0"/><stop offset=".4" stop-color="#4c9a73"/><stop offset="1" stop-color="#123727"/></radialGradient>
          <clipPath id="scout-scene"><circle cx="160" cy="140" r="106"/></clipPath>
        </defs>
        <circle cx="160" cy="140" r="106" fill="url(#scout-sky)" stroke="#76bc9133"/>
        <g clip-path="url(#scout-scene)" stroke="#77b38b" stroke-opacity=".25" stroke-width="1.3">
          <path d="M53 227 93 197V152l30-28V66m-30 86-30-30V96m60 28 27-25V48M93 197l-32-19m63-76-21-20M244 234l-25-41v-49l28-24V72m-28 72-30-26V82"/>
          <g fill="#91d4a6"><circle cx="123" cy="66" r="3"/><circle cx="63" cy="96" r="3"/><circle cx="150" cy="48" r="3"/><circle cx="189" cy="82" r="3"/><circle cx="247" cy="72" r="3"/></g>
        </g>
        <g class="scout-stars" stroke="#a5ebbf" stroke-width="1.4" stroke-linecap="round"><path d="M93 77v8m-4-4h8M203 54v6m-3-3h6M255 175v8m-4-4h8"/></g>
        <ellipse cx="161" cy="252" rx="61" ry="8" fill="#000" opacity=".16"/>
        <g class="verification-scout">
          <path d="M105 244c4-26 0-66 14-94 6-12 14-20 24-21l6-19 11 17c24-2 42 16 47 40 5 21 9 52 12 77-12 8-18-5-28 1-9 7-17 7-26 0-9-6-16 9-27 1-10-8-19 9-33-2Z" fill="url(#scout-body)"/>
          <path d="m179 133 14-16-1 26" fill="#d4e8db"/>
          <g class="scout-eyes" fill="#182d22"><ellipse cx="155" cy="155" rx="4.5" ry="7"/><ellipse cx="179" cy="151" rx="4.5" ry="7"/></g>
          <ellipse cx="169" cy="174" rx="3" ry="3.5" fill="#2e4e3b"/>
          <g class="scout-telescope">
            <path d="m171 151 36-28 10 16-37 23Z" fill="#4c9770"/>
            <path d="m200 119 41-31 28 36-42 31c-8 5-34-30-27-36Z" fill="url(#scout-metal)"/>
            <path d="m236 89 8-6c12-8 39 29 27 38l-8 6Z" fill="#397453"/>
            <ellipse cx="257" cy="102" rx="15" ry="25" transform="rotate(-36 257 102)" fill="#183c29" stroke="#a9e5bb" stroke-width="3"/>
            <ellipse cx="257" cy="102" rx="10" ry="19" transform="rotate(-36 257 102)" fill="url(#scout-lens)"/>
            <path d="m248 92 7-5" stroke="#e4fff0" stroke-width="3" stroke-linecap="round" opacity=".65"/>
            <path d="M194 141c-9-8-15-2-12 5-9-4-13 2-7 8 8 8 19 10 23 2 3-6 2-10-4-15Z" fill="#e4f3e9"/>
            <path class="scout-signal" d="M280 76q12 6 15 20m-9-28q17 9 22 28" stroke="#a8f0bf" stroke-width="1.5" stroke-linecap="round"/>
          </g>
        </g>
      </svg>
    </div>
    <div class="verification-copy"><span class="section-kicker">INVESTIGATION IN PROGRESS</span><h1>Verifying the selected change.</h1><p>The server is investigating this change. Results and completed actions will appear when verification finishes.</p><div class="verification-wait"><span class="verification-pulse" aria-hidden="true"></span><p id="elapsed-time" aria-live="off">Elapsed: 0 seconds</p></div></div>
  </section>`;
}
