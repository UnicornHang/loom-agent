import json
from io import BytesIO
from app.services import mcp_gateway

def test_sse_rpc_response_is_decoded_and_session_preserved(monkeypatch):
    body = BytesIO(b'event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{"ok":true}}\n\n')
    class Response:
        status = 200
        def getheader(self, name, default=None): return {'Content-Type': 'text/event-stream', 'Mcp-Session-Id': 'session-1'}.get(name, default)
        def readline(self, limit): return body.readline(limit)
    calls = []
    class Connection:
        def __init__(self, *args): calls.append(args)
        def request(self, *args, **kwargs): calls.append(kwargs)
        def getresponse(self): return Response()
        def close(self): pass
    monkeypatch.setattr(mcp_gateway, 'public_addresses', lambda *a: ['8.8.8.8'])
    monkeypatch.setattr(mcp_gateway, 'PinnedHTTPS', Connection)
    result, session = mcp_gateway.rpc('https://example.com/mcp', 'secret', {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'}, 10)
    assert result == {'ok': True} and session == 'session-1'
    assert calls[0] == ('example.com', '8.8.8.8', 443, 10)

def test_discovery_never_calls_tool_execution(monkeypatch):
    methods = []
    def rpc(endpoint, token, payload, timeout, session=None):
        methods.append(payload['method'])
        if payload['method'] == 'initialize': return {'protocolVersion': '2025-06-18', 'capabilities': {'tools': {}}}, 'session'
        if payload['method'] == 'notifications/initialized': return {}, 'session'
        return {'tools': [{'name': 'search', 'description': '说明', 'inputSchema': {'type': 'object'}}]}, 'session'
    monkeypatch.setattr(mcp_gateway, 'rpc', rpc)
    assert mcp_gateway.discover('https://example.com/mcp', None, 10)[0]['name'] == 'search'
    assert methods == ['initialize', 'notifications/initialized', 'tools/list']
