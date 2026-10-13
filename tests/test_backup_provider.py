import httpx
import pytest

import checkin
from checkin import backup_cookie_domain_matches, check_in_account, run_check_in_requests
from scripts.select_runtime import browser_required
from utils.config import AccountConfig, AppConfig


def _backup_account(cookie_domain=None):
	data = {
		'name': 'backup',
		'provider': 'agentrouter_backup',
		'cookies': {'session': 'dummy-session-not-a-real-secret'},
		'api_user': '42',
	}
	if cookie_domain is not None:
		data['cookie_domain'] = cookie_domain
	return AccountConfig.from_dict(data, 0)


def _config(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)
	return AppConfig.load_from_env()


def test_backup_provider_is_builtin_and_cookie_only(monkeypatch):
	config = _config(monkeypatch)
	backup = config.get_provider('agentrouter_backup')
	main = config.get_provider('agentrouter')
	assert backup is not None
	assert main is not None
	assert backup.domain == 'https://ps.air-outer.com'
	assert main.domain == 'https://agentrouter.org'
	assert backup.sign_in_path is None
	assert backup.needs_waf_cookies() is False
	assert backup.use_proxy is False
	assert browser_required([_backup_account('ps.air-outer.com')], config) is False


@pytest.mark.parametrize('value', [None, '', 'agentrouter.org', 'evil.example'])
def test_backup_cookie_domain_is_explicitly_required(monkeypatch, value):
	backup = _config(monkeypatch).get_provider('agentrouter_backup')
	assert backup is not None
	assert backup_cookie_domain_matches(_backup_account(value), backup) is False


def test_backup_cookie_domain_matches_only_target(monkeypatch):
	backup = _config(monkeypatch).get_provider('agentrouter_backup')
	assert backup is not None
	assert backup_cookie_domain_matches(_backup_account('ps.air-outer.com'), backup) is True
	assert backup_cookie_domain_matches(_backup_account('PS.AIR-OUTER.COM'), backup) is True


def test_backup_provider_disallows_password_modes(monkeypatch):
	backup = _config(monkeypatch).get_provider('agentrouter_backup')
	assert backup is not None
	account = _backup_account('ps.air-outer.com')
	account.github_username = 'someone'
	account.github_password = 'not-real'
	assert backup_cookie_domain_matches(account, backup) is False


@pytest.mark.asyncio
async def test_backup_wrong_domain_fails_before_network(monkeypatch):
	config = _config(monkeypatch)
	def refuse_network(*args, **kwargs):
		raise AssertionError('No network requests expected for a mismatched cookie domain')
	monkeypatch.setattr(checkin, 'run_check_in_requests', refuse_network)
	result = await check_in_account(_backup_account('agentrouter.org'), 0, config)
	assert result == (False, None, None)


def test_backup_session_sent_only_to_backup_host(monkeypatch):
	config = _config(monkeypatch)
	provider = config.get_provider('agentrouter_backup')
	assert provider is not None
	account = _backup_account('ps.air-outer.com')
	requests = []

	def responder(request: httpx.Request) -> httpx.Response:
		requests.append(request)
		assert request.url.host == 'ps.air-outer.com'
		assert request.headers.get('cookie') == 'session=dummy-session-not-a-real-secret'
		return httpx.Response(200, json={'success': True, 'data': {'quota': 62500000, 'used_quota': 0}})

	transport = httpx.MockTransport(responder)
	original_client = httpx.Client

	def mock_client(**kwargs):
		return original_client(**{**kwargs, 'transport': transport})

	monkeypatch.setattr(checkin.httpx, 'Client', mock_client)
	success, info_before, info_after = run_check_in_requests(
		account.cookies, account, 'backup', provider, use_proxy=False
	)
	assert success is True
	assert info_before['success'] is True
	assert info_after['success'] is True
	assert len(requests) == 2
