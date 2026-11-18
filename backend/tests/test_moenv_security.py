import ssl
from unittest.mock import Mock

import httpx
import pytest

from app.ingestion import moenv_client


def test_source_client_requires_certificate_and_hostname_verification(monkeypatch):
    monkeypatch.delenv("MOENV_CA_BUNDLE", raising=False)
    factory = Mock()
    monkeypatch.setattr(moenv_client.httpx, "Client", factory)

    client = moenv_client.MoenvClient()
    context = factory.call_args.kwargs["verify"]

    assert isinstance(context, ssl.SSLContext)
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    assert context.get_ca_certs()
    client.close()


def test_custom_ca_bundle_keeps_verification_enabled(monkeypatch, tmp_path):
    # Use a trusted root from the local store as a custom bundle.
    ca_file = tmp_path / "trusted-ca.pem"
    root = ssl.create_default_context().get_ca_certs(binary_form=True)[0]
    ca_file.write_text(ssl.DER_cert_to_PEM_cert(root))
    monkeypatch.setenv("MOENV_CA_BUNDLE", str(ca_file))
    factory = Mock()
    monkeypatch.setattr(moenv_client.httpx, "Client", factory)

    client = moenv_client.MoenvClient()
    context = factory.call_args.kwargs["verify"]

    assert context.get_ca_certs(binary_form=True) == [root]
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    client.close()


def test_invalid_ca_bundle_fails_closed(monkeypatch, tmp_path):
    ca_file = tmp_path / "invalid.pem"
    ca_file.write_text("not a certificate")
    monkeypatch.setenv("MOENV_CA_BUNDLE", str(ca_file))

    with pytest.raises(ssl.SSLError):
        moenv_client.MoenvClient()


def test_certificate_failure_is_not_retried_without_verification(monkeypatch):
    monkeypatch.delenv("MOENV_CA_BUNDLE", raising=False)
    factory = Mock()
    factory.return_value.post.side_effect = httpx.ConnectError("certificate verify failed")
    monkeypatch.setattr(moenv_client.httpx, "Client", factory)
    client = moenv_client.MoenvClient()
    try:
        with pytest.raises(httpx.ConnectError):
            client.get_toilets_by_area("63000")
        factory.assert_called_once()
        factory.return_value.post.assert_called_once()
    finally:
        client.close()
