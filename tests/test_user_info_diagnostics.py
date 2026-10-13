from unittest.mock import Mock

import httpx

from checkin import get_user_info


USER_INFO_URL = 'https://agentrouter.org/api/user/self'
HEADERS = {'new-api-user': '12345', 'Cookie': 'session=private-session-value'}
SECRET_MARKER = 'private-session-value'


def _client_with_response(response: httpx.Response) -> Mock:
	client = Mock()
	client.get.return_value = response
	return client


def test_successful_user_info_keeps_balance_parsing(capsys):
	response = httpx.Response(
		200,
		json={'success': True, 'data': {'quota': 62500000, 'used_quota': 0}},
		headers={'content-type': 'application/json; charset=utf-8'},
	)
	result = get_user_info(_client_with_response(response), HEADERS, USER_INFO_URL)

	assert result['success'] is True
	assert result['quota'] == 125.0
	assert result['used_quota'] == 0.0
	assert 'HTTP 200, Content-Type=application/json, JSON=valid' in capsys.readouterr().out


def test_html_response_is_reported_without_logging_body(capsys):
	response = httpx.Response(
		200,
		text=f'<html>Access verification {SECRET_MARKER}</html>',
		headers={'content-type': f'text/html; boundary={SECRET_MARKER}'},
	)
	result = get_user_info(_client_with_response(response), HEADERS, USER_INFO_URL)
	log = capsys.readouterr().out

	assert result['success'] is False
	assert 'invalid JSON' in result['error']
	assert 'HTTP 200, Content-Type=text/html, JSON=invalid' in log
	assert SECRET_MARKER not in log
	assert SECRET_MARKER not in result['error']


def test_403_response_does_not_print_server_body(capsys):
	response = httpx.Response(
		403,
		text=f'Blocked: {SECRET_MARKER}',
		headers={'content-type': 'text/html'},
	)
	result = get_user_info(_client_with_response(response), HEADERS, USER_INFO_URL)
	log = capsys.readouterr().out

	assert result['success'] is False
	assert 'HTTP 403' in result['error']
	assert 'HTTP 403, Content-Type=text/html, JSON=not-checked' in log
	assert SECRET_MARKER not in log


def test_json_api_failure_does_not_log_response_message(capsys):
	response = httpx.Response(
		200,
		json={'success': False, 'message': SECRET_MARKER},
	)
	result = get_user_info(_client_with_response(response), HEADERS, USER_INFO_URL)
	log = capsys.readouterr().out

	assert result['success'] is False
	assert 'API reported failure' in result['error']
	assert 'JSON=valid' in log
	assert SECRET_MARKER not in log


def test_unknown_content_type_is_not_logged_verbatim(capsys):
	response = httpx.Response(
		200,
		text='not JSON',
		headers={'content-type': f'application/{SECRET_MARKER}'},
	)
	get_user_info(_client_with_response(response), HEADERS, USER_INFO_URL)
	log = capsys.readouterr().out

	assert 'Content-Type=other, JSON=invalid' in log
	assert SECRET_MARKER not in log


def test_network_exception_details_are_not_logged(capsys):
	client = Mock()
	client.get.side_effect = httpx.ConnectError(
		f'Connection failed with cookie={SECRET_MARKER}',
		request=httpx.Request('GET', USER_INFO_URL),
	)
	result = get_user_info(client, HEADERS, USER_INFO_URL)
	log = capsys.readouterr().out

	assert result['success'] is False
	assert 'network request failed' in result['error']
	assert 'ConnectError' in log
	assert SECRET_MARKER not in log
	assert SECRET_MARKER not in result['error']