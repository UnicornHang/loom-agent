import socket
import pytest
from app.services.model_gateway import public_addresses, ModelCallError

@pytest.mark.parametrize('address', ['127.0.0.1', '10.1.2.3', '169.254.169.254', '::1', '192.168.1.2', '0.0.0.0'])
def test_private_destinations_rejected(monkeypatch, address):
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (address, 443))])
    with pytest.raises(ModelCallError): public_addresses('model.example', 443)

def test_mixed_public_private_dns_rejected(monkeypatch):
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **k: [(2, 1, 6, '', (address, 443)) for address in ['8.8.8.8', '127.0.0.1']])
    with pytest.raises(ModelCallError): public_addresses('model.example', 443)
