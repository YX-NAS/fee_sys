from app.ai_models import AIProvider
from app.services.ai.credentials import api_credential_hint, validate_api_credentials
from app.services.ai.security import generate_gateway_key, hash_gateway_key, sanitize_provider_error


def test_gateway_key_only_hash_is_persistable():
    plaintext, prefix, digest = generate_gateway_key()
    assert plaintext.startswith("fgw_")
    assert prefix == plaintext[:16]
    assert digest == hash_gateway_key(plaintext)
    assert plaintext not in digest


def test_provider_error_redacts_keys():
    message = sanitize_provider_error(RuntimeError("api_key=sk-secret-value authorization: Bearer fgw_abcdefghijklmnop"))
    assert "sk-secret-value" not in message
    assert "fgw_abcdefghijklmnop" not in message


def test_api_credentials_are_provider_specific_and_only_expose_hint():
    credentials = {"api_key": "sk-1234567890-secret"}
    validate_api_credentials(AIProvider.deepseek, "api_key", credentials)
    hint = api_credential_hint(AIProvider.deepseek, credentials)
    assert hint == "sk-1***cret"
    assert credentials["api_key"] not in hint
