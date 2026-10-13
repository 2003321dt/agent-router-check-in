#!/usr/bin/env python3
"""Choose the light-weight cookie-only or browser runtime without logging secrets."""

import os
from pathlib import Path

from utils.config import AccountConfig, AppConfig, load_accounts_config


def browser_required(accounts: list[AccountConfig] | None, app_config: AppConfig) -> bool:
	"""Browser login or WAF cookie collection requires CloakBrowser and Xvfb."""
	if not accounts:
		# Keep conservative behavior for absent or malformed account configuration.
		return True

	for account in accounts:
		provider = app_config.get_provider(account.provider)
		if account.has_login_credentials() or account.has_github_credentials():
			return True
		if provider is None or provider.needs_waf_cookies():
			return True

	return False


def main() -> None:
	accounts = load_accounts_config()
	app_config = AppConfig.load_from_env()
	required = browser_required(accounts, app_config)

	output_path = os.environ.get("GITHUB_OUTPUT")
	if not output_path:
		raise RuntimeError("GITHUB_OUTPUT is required")
	with Path(output_path).open("a", encoding="utf-8") as output:
		output.write("needs_browser=true\n" if required else "needs_browser=false\n")

	if required:
		print("[INFO] Browser login/WAF mode: install CloakBrowser and Xvfb")
	else:
		print("[INFO] Cookie-only mode: skip CloakBrowser and Xvfb")


if __name__ == "__main__":
	main()
