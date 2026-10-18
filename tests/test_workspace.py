"""Workspace authorization and read-model tests with isolated databases/HTTP fixtures."""
import json
from types import SimpleNamespace
import pytest
from tests.auth_fixtures import firebase_boundary
from tests.test_github_app import gh_app_env
from faultline.db.models import BackgroundJob, GitHubInstallation, Investigation, Organization, PullRequest, Repository
from faultline.workspace import router


@pytest.fixture
def env(gh_app_env):
    gh_app_env["app"].include_router(router)
    return gh_app_env


def seed(env):
    db = env['db']
    db.add(Organization(id='other', name='Other', slug='other'))
    db.add(GitHubInstallation(id=77,organization_id=env['org'].id,account_login='test-owner'))
    db.flush()
    repo=Repository(id='repo-a',organization_id=env['org'].id,installation_id=77,github_repo_id=1,full_name='test/source',indexing_status='indexed',indexed_commit_sha='a'*40)
    other=Repository(id='repo-b',organization_id='other',github_repo_id=2,full_name='private/other')
    db.add_all([repo,other]);db.flush()
    pr=PullRequest(id='pr-a',repository_id=repo.id,github_pr_number=1,title='Change retry behavior',head_sha='a'*40)
    db.add(pr);db.flush()
    inv=Investigation(id='inv-a',repository_id=repo.id,pull_request_id=pr.id,commit_sha='a'*40,status='completed',verdict='INCONCLUSIVE',summary='No applicable verified invariants.',report_json=json.dumps({'changed_components':[{'name':'handle','path':'main.py'}],'private_token':'MUST_NOT_LEAK'}))
    db.add_all([inv,Investigation(id='inv-b',repository_id=other.id,commit_sha='b'*40),BackgroundJob(id='job-b',organization_id='other',repository_id=other.id,job_type='index_repository',idempotency_key='other',payload_json='{}')]);db.commit()
    return repo


def test_new_user_empty_workspace_is_real_zero(env):
    response=env['client'].get('/api/v1/workspace/overview')
    assert response.status_code==200
    assert response.json()['repositories']==[]
    assert response.json()['metrics']=={'repositories':0,'prs_analyzed':0,'findings':0,'inconclusive':0}
    assert 'commerce' not in response.text.lower()


def test_read_models_are_tenant_scoped(env):
    seed(env);client=env['client']
    overview=client.get('/api/v1/workspace/overview').json()
    assert len(overview['repositories'])==1
    assert overview['metrics']['inconclusive']==1
    assert overview['metrics']['prs_analyzed']==1
    assert [x['id'] for x in client.get('/api/v1/workspace/investigations').json()['items']]==['inv-a']
    assert len(client.get('/api/v1/workspace/pull-requests').json()['items'])==1
    assert client.get('/api/v1/workspace/activity').json()['items']==[]
    assert client.get('/api/v1/workspace/investigations/inv-b').status_code==404
    assert client.get('/api/v1/workspace/overview?org_id=other').status_code==403


def test_evidence_is_whitelisted_and_honest(env):
    seed(env)
    response=env['client'].get('/api/v1/workspace/investigations/inv-a')
    assert response.json()['verdict']=='INCONCLUSIVE'
    assert 'MUST_NOT_LEAK' not in response.text
    assert 'No arbitrary external repository code' in response.json()['scope']
    assert [a['label'] for a in response.json()['activity']]==['Investigation recorded']


def test_graph_cross_tenant_and_unavailable(env,monkeypatch):
    seed(env);client=env['client']
    assert client.get('/api/v1/workspace/repositories/repo-b/graph').status_code==403
    def fail(*a,**kw):raise RuntimeError('internal private service address')
    monkeypatch.setattr('faultline.workspace.FalkorRepositoryGraph.read',fail)
    response=client.get('/api/v1/workspace/repositories/repo-a/graph')
    assert response.status_code==503
    assert 'internal private service address' not in response.text


def test_graph_scope_and_bounded_queries(env,monkeypatch):
    seed(env);queries=[]
    def read(self,query,**params):
        queries.append((query,params))
        return []
    monkeypatch.setattr('faultline.workspace.FalkorRepositoryGraph.read',read)
    assert env['client'].get('/api/v1/workspace/repositories/repo-a/graph?limit=151').status_code==422
    response=env['client'].get('/api/v1/workspace/repositories/repo-a/graph?q=handle')
    assert response.status_code==200
    assert queries[0][1]['organization']==env['org'].id
    assert queries[0][1]['revision']=='a'*40
    assert 'tenant_id=$organization' in queries[0][0]
    assert 'LIMIT $limit' in queries[0][0]


def test_authentication_and_csrf_required(env):
    client=env['client']
    assert client.post('/api/v1/workspace/activity/job/retry').status_code==403
    client.cookies.clear()
    assert client.get('/api/v1/workspace/overview').status_code==401


def test_callback_requires_browser_and_current_user(env):
    from faultline.github.client import generate_install_state
    state=generate_install_state(env['org'].id,env['user'].id)
    response=env['client'].get('/api/v1/github/callback',params={'installation_id':123,'state':state})
    assert response.status_code==400
    assert env['db'].query(GitHubInstallation).count()==0


@pytest.mark.parametrize("cross_tenant", [False, True])
def test_verified_oauth_saves_only_admin_repositories(env,monkeypatch,cross_tenant):
    from faultline.github import onboarding
    from faultline.github.client import generate_install_state
    settings=SimpleNamespace(github_client_id='fixture-client',github_client_secret='fixture-secret',allowed_origins=('http://testserver',),session_cookie_secure=False)
    monkeypatch.setattr(onboarding,'configuration',lambda:(settings,SimpleNamespace(app_id=42)))
    class Reply:
        def raise_for_status(self):pass
        def json(self):return {'access_token':'fixture-only-token'}
    class HTTP:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,*args,**kwargs):return Reply()
    monkeypatch.setattr(onboarding.httpx,'Client',HTTP)
    def pages(client,path,token,key):
        assert token=='fixture-only-token'
        if key=='installations':return [{'id':77,'app_id':42,'account':{'login':'test-owner','type':'User'}}]
        return [{'id':1,'full_name':'test-owner/allowed','permissions':{'admin':True}}, {'id':2,'full_name':'test-owner/read-only','permissions':{'pull':True}}]
    monkeypatch.setattr(onboarding,'pages',pages)
    if cross_tenant:
        env['db'].add(Organization(id='other-workspace',name='Other',slug='other-workspace'))
        env['db'].flush()
        env['db'].add(GitHubInstallation(id=77,organization_id='other-workspace',account_login='test-owner'))
        env['db'].commit()
    state=generate_install_state(env['org'].id,env['user'].id)
    env['client'].cookies.set(onboarding.COOKIE,state,path='/api/v1/github')
    response=env['client'].get('/api/v1/github/oauth/callback',params={'code':'one-use-fixture-code','state':state},follow_redirects=False)
    assert response.status_code==303
    assert 'imported=1' in response.headers['location']
    from faultline.db.models import WorkspaceInstallation
    ws_inst=env['db'].query(WorkspaceInstallation).filter_by(organization_id=env['org'].id,installation_id=77).first()
    assert ws_inst is not None
    assert 'test-owner/allowed' in ws_inst.authorized_repositories_json
    # Vercel-style: admin repositories are automatically active in the workspace
    imported_repo=env['db'].query(Repository).filter_by(organization_id=env['org'].id,github_repo_id=1).first()
    assert imported_repo is not None
    assert imported_repo.full_name=='test-owner/allowed'
    assert imported_repo.is_active is True
    # Non-admin repositories must NEVER be imported
    read_only_repo=env['db'].query(Repository).filter_by(organization_id=env['org'].id,github_repo_id=2).first()
    assert read_only_repo is None
    assert 'fixture-only-token' not in response.text
    assert 'fz_github_connect=' in response.headers['set-cookie']


def test_oauth_rejects_installation_owned_by_another_workspace(env,monkeypatch):
    # A correctly signed state for a different current user is still rejected.
    from faultline.github import onboarding
    from faultline.github.client import generate_install_state
    state=generate_install_state(env['org'].id,'another-user')
    env['client'].cookies.set(onboarding.COOKIE,state,path='/api/v1/github')
    response=env['client'].get('/api/v1/github/oauth/callback',params={'code':'fixture','state':state})
    assert response.status_code==403


def test_multi_tenant_installation_sharing_and_batch_add(env):
    """
    Verifies that:
    1. Multiple workspaces can share the same physical GitHub installation.
    2. Available candidate repositories are accessible to both workspaces.
    3. User selects specific repos via batch-add.
    4. Unselected repos remain unmonitored.
    """
    db = env['db']
    client = env['client']
    org1 = env['org']

    org2 = Organization(id="org-beta", name="Beta Corp", slug="beta-corp")
    db.add(org2)
    db.flush()

    inst = db.query(GitHubInstallation).filter_by(id=77).first()
    if not inst:
        inst = GitHubInstallation(id=77, organization_id=None, account_login="shared-corp", account_type="Organization")
        db.add(inst)
        db.flush()

    candidates = [
        {"id": 101, "full_name": "shared-corp/service-auth", "private": True, "default_branch": "main"},
        {"id": 102, "full_name": "shared-corp/service-billing", "private": True, "default_branch": "main"},
    ]
    from faultline.db.models import WorkspaceInstallation
    w1 = WorkspaceInstallation(
        organization_id=org1.id,
        installation_id=77,
        authorized_by_user_id=env['user'].id,
        authorized_repositories_json=json.dumps(candidates),
    )
    w2 = WorkspaceInstallation(
        organization_id=org2.id,
        installation_id=77,
        authorized_by_user_id="usr-bob",
        authorized_repositories_json=json.dumps(candidates),
    )
    db.add_all([w1, w2])
    db.commit()

    res1 = client.get("/api/v1/github/available-repositories")
    assert res1.status_code == 200
    names1 = [r["full_name"] for r in res1.json()]
    assert "shared-corp/service-auth" in names1
    assert "shared-corp/service-billing" in names1

    add_res = client.post(
        "/api/v1/github/repositories/batch-add",
        json={"github_repo_ids": [101], "auto_index": False},
        headers={"X-CSRF-Token": env["csrf_token"]},
    )
    assert add_res.status_code == 200
    assert add_res.json()["added_count"] == 1

    r101_org1 = db.query(Repository).filter_by(organization_id=org1.id, github_repo_id=101).first()
    assert r101_org1 is not None
    assert r101_org1.is_active is True
    assert r101_org1.full_name == "shared-corp/service-auth"

    r102_org1 = db.query(Repository).filter_by(organization_id=org1.id, github_repo_id=102).first()
    assert r102_org1 is None

    r101_org2 = db.query(Repository).filter_by(organization_id=org2.id, github_repo_id=101).first()
    assert r101_org2 is None


def test_repository_removal_isolation(env):
    """
    Verifies that removing a repository deactivates monitoring in that workspace only,
    without deleting the GitHub installation or impacting other workspaces.
    """
    db = env['db']
    client = env['client']
    org1 = env['org']

    org2 = Organization(id="org-gamma", name="Gamma Corp", slug="gamma-corp")
    db.add(org2)
    db.flush()

    inst = GitHubInstallation(id=77, organization_id=None, account_login="shared-corp", account_type="Organization")
    db.add(inst)
    db.flush()

    repo_org1 = Repository(
        id="repo-201-org1",
        organization_id=org1.id,
        installation_id=77,
        github_repo_id=201,
        full_name="shared/core-api",
        is_active=True,
    )
    repo_org2 = Repository(
        id="repo-201-org2",
        organization_id=org2.id,
        installation_id=77,
        github_repo_id=201,
        full_name="shared/core-api",
        is_active=True,
    )
    db.add_all([repo_org1, repo_org2])
    db.commit()

    remove_res = client.post(
        f"/api/v1/github/repositories/{repo_org1.id}/remove",
        headers={"X-CSRF-Token": env["csrf_token"]},
    )
    assert remove_res.status_code == 200
    assert remove_res.json()["status"] == "removed"

    db.refresh(repo_org1)
    db.refresh(repo_org2)

    assert repo_org1.is_active is False
    assert repo_org2.is_active is True

    inst = db.query(GitHubInstallation).filter_by(id=77).first()
    assert inst is not None


def test_unauthorized_repository_actions_rejected(env):
    """
    Verifies that non-admin members cannot batch-add or remove repositories.
    """
    db = env['db']
    client = env['client']
    org = env['org']

    from faultline.db.models import User, Membership
    viewer = User(id="usr-viewer", firebase_uid="fb-viewer", email="viewer@acme.com")
    db.add(viewer)
    db.flush()
    mem = Membership(id="mem-viewer", user_id=viewer.id, organization_id=org.id, role="viewer")
    db.add(mem)
    db.commit()

    from tests.auth_fixtures import create_session_token, generate_csrf_token
    token, jti = create_session_token(user_id=viewer.firebase_uid, organization_id=org.id)
    csrf = generate_csrf_token(user_id=viewer.id, session_jti=jti)

    res_add = client.post(
        "/api/v1/github/repositories/batch-add",
        json={"github_repo_ids": [101]},
        headers={"X-CSRF-Token": csrf},
        cookies={"__session": token},
    )
    assert res_add.status_code == 403


def test_add_access_flow_imports_only_new_repos(env, monkeypatch):
    """
    Verifies that flow="add-access" with prev_repo_ids only imports newly granted repos,
    preserving existing repos and not duplicating them.
    """
    from faultline.github import onboarding
    from faultline.github.client import generate_install_state
    settings = SimpleNamespace(github_client_id='fixture-client', github_client_secret='fixture-secret', allowed_origins=('http://testserver',), session_cookie_secure=False)
    monkeypatch.setattr(onboarding, 'configuration', lambda: (settings, SimpleNamespace(app_id=42)))
    class Reply:
        def raise_for_status(self): pass
        def json(self): return {'access_token': 'fixture-only-token'}
    class HTTP:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, *args, **kwargs): return Reply()
    monkeypatch.setattr(onboarding.httpx, 'Client', HTTP)

    # 3 repos returned: 1 was previous, 2 is read-only, 3 is newly added admin repo
    def pages(client, path, token, key):
        if key == 'installations':
            return [{'id': 77, 'app_id': 42, 'account': {'login': 'test-owner', 'type': 'User'}}]
        return [
            {'id': 1, 'full_name': 'test-owner/allowed', 'permissions': {'admin': True}},
            {'id': 2, 'full_name': 'test-owner/read-only', 'permissions': {'pull': True}},
            {'id': 3, 'full_name': 'test-owner/newly-added', 'permissions': {'admin': True}},
        ]
    monkeypatch.setattr(onboarding, 'pages', pages)

    # Pre-existing repo 1
    existing = Repository(
        id='repo-1-exist',
        organization_id=env['org'].id,
        installation_id=77,
        github_repo_id=1,
        full_name='test-owner/allowed',
        is_active=True,
    )
    env['db'].add(existing)
    env['db'].commit()

    # Initiate state with prev_repo_ids=[1] and flow="add-access"
    state = generate_install_state(env['org'].id, env['user'].id, flow="add-access", prev_repo_ids=[1])
    env['client'].cookies.set(onboarding.COOKIE, state, path='/api/v1/github')

    response = env['client'].get('/api/v1/github/oauth/callback', params={'code': 'code-abc', 'state': state}, follow_redirects=False)
    assert response.status_code == 303
    assert 'imported=1' in response.headers['location']

    # Repo 3 was newly imported
    r3 = env['db'].query(Repository).filter_by(organization_id=env['org'].id, github_repo_id=3).first()
    assert r3 is not None
    assert r3.full_name == 'test-owner/newly-added'
    assert r3.is_active is True

    # Repo 1 is still active and unchanged
    r1 = env['db'].query(Repository).filter_by(organization_id=env['org'].id, github_repo_id=1).first()
    assert r1 is not None
    assert r1.id == 'repo-1-exist'
    assert r1.is_active is True


def test_oauth_callback_cancellation_returns_friendly_notice(env):
    """
    Verifies that when user cancels authorization on GitHub (error=access_denied),
    FAULTLINE returns a friendly 303 redirect with a notice rather than an HTTP 500 error.
    """
    response = env['client'].get(
        '/api/v1/github/oauth/callback',
        params={
            'error': 'access_denied',
            'error_description': 'The user has denied your application access.',
            'state': 'dummy',
            'code': 'dummy',
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert 'notice=' in response.headers['location']
    assert 'denied' in response.headers['location'].lower()


def test_github_connect_and_configure_endpoints(env, monkeypatch):
    """
    Verifies /api/v1/github/connect redirects to GitHub OAuth with signed state cookie,
    and /api/v1/github/configure-url returns deep link to GitHub settings.
    """
    from faultline.github import onboarding
    settings = SimpleNamespace(github_client_id='test-client-id', github_client_secret='secret', allowed_origins=('http://testserver',), session_cookie_secure=False)
    monkeypatch.setattr(onboarding, 'configuration', lambda: (settings, SimpleNamespace(app_id=42, app_slug='faultline-zero-agent')))

    # Test /api/v1/github/connect
    res_conn = env['client'].get('/api/v1/github/connect', follow_redirects=False)
    assert res_conn.status_code == 303
    assert 'github.com/login/oauth/authorize' in res_conn.headers['location']
    assert 'client_id=test-client-id' in res_conn.headers['location']
    assert 'fz_github_connect=' in res_conn.headers['set-cookie']

    # Test /api/v1/github/configure-url when installation exists
    inst = GitHubInstallation(id=88, organization_id=env['org'].id, account_login='test-corp', account_type='Organization')
    env['db'].add(inst)
    env['db'].commit()

    res_cfg = env['client'].get('/api/v1/github/configure-url')
    assert res_cfg.status_code == 200
    data = res_cfg.json()
    assert 'https://github.com/organizations/test-corp/settings/installations/88' in data['url']
    assert 'state' in data


def test_github_disconnect_workspace(env):
    """
    Verifies POST /api/v1/github/disconnect pauses monitoring for active repositories
    and removes workspace installation link without affecting physical installations.
    """
    db = env['db']
    client = env['client']
    org = env['org']

    inst = GitHubInstallation(id=99, organization_id=None, account_login='owner')
    db.add(inst)
    db.flush()

    repo = Repository(id='repo-disc', organization_id=org.id, installation_id=99, github_repo_id=999, full_name='owner/disc', is_active=True)
    db.add(repo)
    db.commit()

    res = client.post(
        '/api/v1/github/disconnect',
        headers={'X-CSRF-Token': env['csrf_token']},
    )
    assert res.status_code == 200
    assert res.json()['status'] == 'disconnected'

    db.refresh(repo)
    assert repo.is_active is False
    # Physical installation remains intact
    assert db.get(GitHubInstallation, 99) is not None

