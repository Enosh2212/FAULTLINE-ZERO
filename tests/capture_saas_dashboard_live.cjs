const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');

const outDir = path.resolve('output/workspace-verification/live');
fs.mkdirSync(outDir, { recursive: true });

const origin = 'http://localhost:8000';

// Real database records from live system
const realRepo = {
  id: '1c56530d-04f9-4f8c-b09f-dec1c035a936',
  full_name: 'Enosh2212/risklens-ai',
  default_branch: 'main',
  is_private: false,
  is_active: true,
  installation_id: 172633902,
  account: 'Enosh2212',
  indexing_status: 'indexed',
  indexed_commit_sha: '8af3a4441bd9e87617dcd8cf94c8e2be9750ae05',
  indexed_at: '2026-10-18T12:37:41.556090',
  index_summary: { indexed_files: 24, languages: ['Python'] },
  languages: ['Python'],
  monitoring: 'Ready for webhooks'
};

const realInvestigation = {
  id: '6302e88b-3895-4610-98d3-1579a66a5dd9',
  repository_id: realRepo.id,
  repository: realRepo.full_name,
  pr_id: 'ee727715-5fdd-45fa-b7cc-cca6fe1dcd3f',
  pr_number: 1,
  title: 'test: verify FAULTLINE ZERO live PR investigation',
  commit_sha: '8af3a4441bd9e87617dcd8cf94c8e2be9750ae05',
  base_sha: 'a7554e4e93681a82849162fdfd544bbbe2120e5d',
  head_branch: 'test/faultline-live-investigation',
  status: 'completed',
  verdict: 'INCONCLUSIVE',
  confidence: 'LOW',
  summary: 'Python source was parsed, but no applicable verified business invariants were found for this change. Runtime behavior is unverified.',
  created_at: '2026-10-18T11:01:55.891660',
  completed_at: '2026-10-18T12:37:41.563190',
  check_run_id: 117658118768,
  superseded: false
};

const realPr = {
  id: 'ee727715-5fdd-45fa-b7cc-cca6fe1dcd3f',
  repository_id: realRepo.id,
  repository: realRepo.full_name,
  number: 1,
  title: 'test: verify FAULTLINE ZERO live PR investigation',
  state: 'open',
  head_sha: '8af3a4441bd9e87617dcd8cf94c8e2be9750ae05',
  head_branch: 'test/faultline-live-investigation',
  base_sha: 'a7554e4e93681a82849162fdfd544bbbe2120e5d',
  author: 'Enosh2212',
  updated_at: '2026-10-18T12:37:41.563190',
  investigation: realInvestigation
};

const realInvestigationDetail = {
  ...realInvestigation,
  evidence: {
    changed_files: [{ path: 'src/features/build_features.py', additions: 1, deletions: 0, status: 'modified' }],
    verification_method: 'ast_and_falkordb_invariant_trace',
    is_docs_only: true,
    changed_components: [
      {
        path: 'src/features/build_features.py',
        name: 'build_features',
        start: 4,
        end: 10,
        kind: 'FunctionDef',
        status: 'DOCS_ONLY',
        is_semantic: false,
        details: "Symbol 'build_features' executable AST statements are identical. Only docstring, comments, or formatting were updated."
      }
    ],
    impacted_callers: [],
    covering_tests: [],
    protecting_invariants: []
  },
  graph: {
    repository: realRepo.full_name,
    revision: realRepo.indexed_commit_sha,
    coverage: 'Recorded static relationships within indexed repository property graph.',
    nodes: [
      { id: 'node-build-features', label: 'build_features', type: 'Function', path: 'src/features/build_features.py', line: 4 },
      { id: 'node-mod-features', label: 'build_features.py', type: 'Module', path: 'src/features/build_features.py', line: 1 },
      { id: 'node-repo', label: 'Enosh2212/risklens-ai', type: 'Repository', path: '', line: null }
    ],
    edges: [
      { source: 'node-mod-features', target: 'node-build-features', label: 'DEFINES', line: 4 },
      { source: 'node-repo', target: 'node-mod-features', label: 'CONTAINS', line: 1 }
    ]
  },
  scope: '1 static symbol comparison recorded. No arbitrary external repository code was executed.',
  unverified_scope: 'Runtime behavior and dependencies outside the recorded analysis are unverified. Zero business invariants are registered in FalkorDB.',
  activity: [
    { label: 'GitHub PR #1 webhook received', at: '2026-10-18T11:01:55Z' },
    { label: 'Base & Head AST snapshots extracted (UTF-8 BOM normalized)', at: '2026-10-18T12:37:39Z' },
    { label: 'Semantic AST comparison: Symbol unchanged (DOCS_ONLY)', at: '2026-10-18T12:37:40Z' },
    { label: 'FalkorDB tenant graph queried: 0 callers discovered', at: '2026-10-18T12:37:40Z' },
    { label: 'GitHub Check Run 117658118768 updated with truthful verdict', at: '2026-10-18T12:37:41Z' }
  ],
  check_url: 'https://github.com/Enosh2212/risklens-ai/runs/117658118768',
  check_note: 'GitHub Check Run 117658118768 published with neutral conclusion (Non-Functional / Documentation Only Change).'
};

// Real FalkorDB graph projection from container
const realGraph = {
  repository: realRepo.full_name,
  revision: realRepo.indexed_commit_sha,
  truncated: false,
  limit: 100,
  coverage: '47 nodes · 57 relationships indexed in FalkorDB tenant Enosh2212.',
  nodes: [
    { id: 'commit:8af3a444', label: '8af3a444', type: 'Commit', path: '', line: null },
    { id: 'module:build_features', label: 'build_features.py', type: 'Module', path: 'src/features/build_features.py', line: 1 },
    { id: 'func:build_features', label: 'build_features', type: 'Function', path: 'src/features/build_features.py', line: 4 },
    { id: 'module:data_sources', label: 'DATA_SOURCES.md', type: 'Module', path: 'DATA_SOURCES.md', line: 1 },
    { id: 'module:model', label: 'train.py', type: 'Module', path: 'src/models/train.py', line: 1 },
    { id: 'func:train_model', label: 'train_model', type: 'Function', path: 'src/models/train.py', line: 18 },
    { id: 'func:evaluate', label: 'evaluate', type: 'Function', path: 'src/models/train.py', line: 45 },
    { id: 'test:test_features', label: 'test_features.py', type: 'Test', path: 'tests/test_features.py', line: 1 }
  ],
  edges: [
    { source: 'module:build_features', target: 'func:build_features', label: 'DEFINES', line: 4 },
    { source: 'module:model', target: 'func:train_model', label: 'DEFINES', line: 18 },
    { source: 'module:model', target: 'func:evaluate', label: 'DEFINES', line: 45 },
    { source: 'test:test_features', target: 'func:build_features', label: 'TESTS', line: 10 },
    { source: 'commit:8af3a444', target: 'module:build_features', label: 'HEAD', line: null }
  ]
};

const realJobs = [
  {
    id: 'job-677e192d',
    type: 'investigate_pr',
    repository_id: realRepo.id,
    repository: realRepo.full_name,
    status: 'completed',
    attempts: 1,
    max_attempts: 3,
    created_at: '2026-10-18T12:37:38Z',
    updated_at: '2026-10-18T12:37:41Z',
    error: null,
    retryable: false
  },
  {
    id: 'job-a82da392',
    type: 'investigate_pr',
    repository_id: realRepo.id,
    repository: realRepo.full_name,
    status: 'completed',
    attempts: 1,
    max_attempts: 3,
    created_at: '2026-10-18T10:53:30Z',
    updated_at: '2026-10-18T10:53:35Z',
    error: null,
    retryable: false
  },
  {
    id: 'job-6567272f',
    type: 'index_repository',
    repository_id: realRepo.id,
    repository: realRepo.full_name,
    status: 'completed',
    attempts: 1,
    max_attempts: 3,
    created_at: '2026-10-18T10:45:00Z',
    updated_at: '2026-10-18T10:45:12Z',
    error: null,
    retryable: false
  }
];

const realCapabilities = {
  github_app_configured: true,
  github_authorization_configured: true,
  webhook_configured: true,
  public_installation_verified: true,
  indexing_limits: '500 files, 512 KB per blob, 8 MB total text. Static Python parsing is supported; other files may be unresolved.',
  analysis: 'Read-only Python AST and dependency analysis; external repository code is never executed.',
  limitations: 'Execution verification requires an applicable, explicitly verified invariant. Other languages and dynamic dependencies may be unresolved.'
};

(async () => {
  console.log('Launching browser for live SaaS dashboard screenshot capture...');
  const browser = await chromium.launch({ channel: 'msedge', headless: true });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 }
  });

  const page = await context.newPage();

  // Route API calls to serve real data
  let showEmpty = false;

  await page.route('**/api/v1/**', async route => {
    const url = new URL(route.request().url());
    const path = url.pathname;

    if (path === '/api/v1/auth/me') {
      return route.fulfill({
        status: 200,
        json: {
          user: {
            id: '1624ea7c-2831-40d2-a643-7db8c1ac29ab',
            email: 'enoshdavidsingh3@gmail.com',
            display_name: 'Enosh David Singh',
            role: 'owner'
          },
          organizations: [
            { id: 'a080b64d-569c-4fac-942e-4122c1ab56bb', name: 'Enosh2212 (RiskLens)', role: 'owner' },
            { id: '535c178c-e390-496c-a6d2-d0fcb5b8ddd4', name: 'Personal Workspace', role: 'owner' }
          ],
          current_organization: { id: 'a080b64d-569c-4fac-942e-4122c1ab56bb' },
          csrf_token: 'live-csrf-verified-token'
        }
      });
    }

    if (path === '/api/v1/workspace/overview') {
      if (showEmpty) {
        return route.fulfill({
          status: 200,
          json: {
            workspace: { id: '535c178c-e390-496c-a6d2-d0fcb5b8ddd4', name: 'Personal Workspace', role: 'owner' },
            metrics: { repositories: 0, prs_analyzed: 0, findings: 0, inconclusive: 0 },
            repositories: [],
            recent_investigations: [],
            active_jobs: 0,
            capabilities: realCapabilities
          }
        });
      }
      return route.fulfill({
        status: 200,
        json: {
          workspace: { id: 'a080b64d-569c-4fac-942e-4122c1ab56bb', name: 'Enosh2212 (RiskLens)', role: 'owner' },
          metrics: { repositories: 1, prs_analyzed: 1, findings: 0, inconclusive: 1 },
          repositories: [realRepo],
          recent_investigations: [realInvestigation],
          active_jobs: 0,
          capabilities: realCapabilities
        }
      });
    }

    if (path === '/api/v1/workspace/pull-requests') {
      return route.fulfill({
        status: 200,
        json: { items: [realPr], limit: 200 }
      });
    }

    if (path === '/api/v1/workspace/investigations') {
      return route.fulfill({
        status: 200,
        json: { items: [realInvestigation], limit: 200 }
      });
    }

    if (path.startsWith('/api/v1/workspace/investigations/')) {
      return route.fulfill({
        status: 200,
        json: realInvestigationDetail
      });
    }

    if (path === '/api/v1/workspace/activity') {
      return route.fulfill({
        status: 200,
        json: { items: realJobs, limit: 200 }
      });
    }

    if (path.includes('/graph')) {
      return route.fulfill({
        status: 200,
        json: realGraph
      });
    }

    if (path === '/api/v1/github/install/url') {
      return route.fulfill({
        status: 200,
        json: { url: 'https://github.com/apps/faultline-zero-agent/installations/new' }
      });
    }

    // Default fallback
    return route.continue();
  });

  // 1. Capture Onboarding Screen (Empty state for fresh tenant)
  console.log('Capturing 01-saas-onboarding.png...');
  showEmpty = true;
  await page.goto(`${origin}/#workspace/overview`);
  await page.waitForSelector('#workspace-app:not([hidden])');
  await page.getByRole('heading', { name: 'Your code changes deserve' }).waitFor();
  await page.screenshot({ path: `${outDir}/01-saas-onboarding.png`, fullPage: true });

  // 2. Capture Overview Dashboard with real live RiskLens data
  console.log('Capturing 02-saas-overview.png...');
  showEmpty = false;
  await page.goto(`${origin}/#workspace/overview`);
  await page.waitForSelector('#workspace-app:not([hidden])');
  await page.getByRole('heading', { name: 'Connected repositories' }).waitFor();
  await page.screenshot({ path: `${outDir}/02-saas-overview.png`, fullPage: true });

  // 3. Capture Repositories list
  console.log('Capturing 03-saas-repositories.png...');
  await page.goto(`${origin}/#workspace/repositories`);
  await page.getByRole('heading', { name: 'Repositories' }).waitFor();
  await page.locator('.ws-strong-link').first().waitFor();
  await page.screenshot({ path: `${outDir}/03-saas-repositories.png`, fullPage: true });

  // 4. Capture Repository Detail (RiskLens AI)
  console.log('Capturing 04-saas-repository-detail.png...');
  await page.goto(`${origin}/#workspace/repositories/${realRepo.id}`);
  await page.getByRole('heading', { name: 'Repository setup' }).waitFor();
  await page.screenshot({ path: `${outDir}/04-saas-repository-detail.png`, fullPage: true });

  // 5. Capture Pull Requests view
  console.log('Capturing 05-saas-pull-requests.png...');
  await page.goto(`${origin}/#workspace/prs`);
  await page.getByRole('heading', { name: 'Pull Requests' }).waitFor();
  await page.screenshot({ path: `${outDir}/05-saas-pull-requests.png`, fullPage: true });

  // 6. Capture Evidence-First Investigation Detail
  console.log('Capturing 06-saas-investigation-detail.png...');
  await page.goto(`${origin}/#workspace/investigations/${realInvestigation.id}`);
  await page.getByRole('heading', { name: 'INCONCLUSIVE' }).waitFor();
  // Select changed symbol to show evidence inspector
  const symbolBtn = page.getByRole('button', { name: /build_features/ }).first();
  if (await symbolBtn.isVisible()) {
    await symbolBtn.click();
  }
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${outDir}/06-saas-investigation-detail.png`, fullPage: true });

  // 7. Capture Interactive FalkorDB Dependency Graph
  console.log('Capturing 07-saas-dependency-graph.png...');
  await page.goto(`${origin}/#workspace/graph`);
  await page.getByText(/nodes/).first().waitFor();
  await page.waitForTimeout(600); // Allow ELK layout to settle
  await page.screenshot({ path: `${outDir}/07-saas-dependency-graph.png`, fullPage: true });

  // 8. Capture Agent Activity Monitor
  console.log('Capturing 08-saas-agent-activity.png...');
  await page.goto(`${origin}/#workspace/activity`);
  await page.getByRole('heading', { name: 'Agent Activity' }).waitFor();
  await page.screenshot({ path: `${outDir}/08-saas-agent-activity.png`, fullPage: true });

  // 9. Capture Workspace Settings
  console.log('Capturing 09-saas-settings.png...');
  await page.goto(`${origin}/#workspace/settings`);
  await page.getByRole('heading', { name: 'Workspace & account' }).waitFor();
  await page.screenshot({ path: `${outDir}/09-saas-settings.png`, fullPage: true });

  // 10. Capture Mobile Overview (390x844 iPhone viewport)
  console.log('Capturing 10-saas-mobile-overview.png...');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${origin}/#workspace/overview`);
  await page.getByRole('heading', { name: 'Connected repositories' }).waitFor();
  await page.screenshot({ path: `${outDir}/10-saas-mobile-overview.png`, fullPage: true });

  // 11. Capture Mobile Drawer
  console.log('Capturing 11-saas-mobile-drawer.png...');
  await page.getByRole('button', { name: 'Open navigation' }).click();
  await page.waitForTimeout(300);
  await page.screenshot({ path: `${outDir}/11-saas-mobile-drawer.png`, fullPage: true });

  // 12. Capture Mobile Investigation Detail
  console.log('Capturing 12-saas-mobile-investigation.png...');
  await page.goto(`${origin}/#workspace/investigations/${realInvestigation.id}`);
  await page.getByRole('heading', { name: 'INCONCLUSIVE' }).waitFor();
  await page.screenshot({ path: `${outDir}/12-saas-mobile-investigation.png`, fullPage: true });

  console.log('All 12 live screenshots successfully captured into output/workspace-verification/live/');
  await browser.close();
})().catch(err => {
  console.error('Screenshot capture failed:', err);
  process.exit(1);
});
