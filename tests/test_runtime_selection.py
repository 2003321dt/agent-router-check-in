import json

from scripts.select_runtime import browser_required, main
from utils.config import AccountConfig, AppConfig


def _cookie_account(provider="agentrouter"):
	return AccountConfig(cookies={"session": "fake-session"}, api_user="123", provider=provider)


def _cookie_only_provider(monkeypatch):
	monkeypatch.setenv(
		"PROVIDERS",
		json.dumps(
			{
				"agentrouter": {
					"domain": "https://agentrouter.org",
					"bypass_method": None,
					"waf_cookie_names": [],
					"use_proxy": False,
				}
			}
		),
	)
	return AppConfig.load_from_env()


def test_cookie_only_without_waf_skips_browser(monkeypatch):
	config = _cookie_only_provider(monkeypatch)
	assert browser_required([_cookie_account()], config) is False


def test_cookie_only_with_default_waf_uses_browser(monkeypatch):
	monkeypatch.delenv("PROVIDERS", raising=False)
	config = AppConfig.load_from_env()
	assert browser_required([_cookie_account()], config) is True


def test_email_login_uses_browser_even_with_cookie(monkeypatch):
	config = _cookie_only_provider(monkeypatch)
	account = _cookie_account()
	account.email = "account@example.invalid"
	account.password = "fake-password"
	assert browser_required([account], config) is True


def test_github_login_uses_browser_even_with_cookie(monkeypatch):
	config = _cookie_only_provider(monkeypatch)
	account = _cookie_account()
	account.github_username = "example"
	account.github_password = "fake-password"
	assert browser_required([account], config) is True


def test_mixed_accounts_use_browser(monkeypatch):
	config = _cookie_only_provider(monkeypatch)
	second = AccountConfig(cookies=None, email="fake@example.invalid", password="fake-password")
	assert browser_required([_cookie_account(), second], config) is True


def test_unknown_provider_uses_browser_conservatively(monkeypatch):
	config = _cookie_only_provider(monkeypatch)
	assert browser_required([_cookie_account("missing")], config) is True


def test_missing_accounts_use_browser_conservatively(monkeypatch):
	config = _cookie_only_provider(monkeypatch)
	assert browser_required(None, config) is True
	assert browser_required([], config) is True


def test_github_output_contains_only_mode_not_credentials(monkeypatch, tmp_path, capsys):
	_cookie_only_provider(monkeypatch)
	secret = "never-print-this-session"
	monkeypatch.setenv(
		"ANYROUTER_ACCOUNTS",
		json.dumps([{"provider": "agentrouter", "api_user": "123", "cookies": {"session": secret}}]),
	)
	output_file = tmp_path / "github_output"
	monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))
	main()
	assert output_file.read_text(encoding="utf-8") == "needs_browser=false\n"
	assert secret not in capsys.readouterr().out
