"""Read-only discovery over public HTTPS Streamable HTTP. Never executes tools."""
import json
import time
from urllib.parse import urlsplit, quote
from app.services.model_gateway import PinnedHTTPS, public_addresses

class MCPError(Exception):
    pass

def rpc(endpoint, token, payload, timeout, session=None):
    parsed = urlsplit(endpoint)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment: raise MCPError('仅支持无查询参数的 HTTPS MCP 地址')
    port = parsed.port or 443
    connection = PinnedHTTPS(parsed.hostname, public_addresses(parsed.hostname, port)[0], port, timeout)
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream', 'Accept-Encoding': 'identity'}
    if token: headers['Authorization'] = 'Bearer ' + token
    if session: headers['Mcp-Session-Id'] = session
    if payload['method'] != 'initialize': headers['MCP-Protocol-Version'] = '2025-06-18'
    try:
        connection.request('POST', quote(parsed.path or '/', safe='/%:@'), body=json.dumps(payload).encode(), headers=headers)
        response = connection.getresponse()
        if response.status == 202 and 'id' not in payload: return {}, session
        if response.status != 200: raise MCPError('MCP HTTP 请求失败')
        new_session = response.getheader('Mcp-Session-Id') or session
        if new_session and (len(new_session) > 512 or any(ord(c) < 33 or ord(c) > 126 for c in new_session)): raise MCPError('无效 MCP 会话标识')
        deadline = time.monotonic() + timeout
        size = 0
        if response.getheader('Content-Type', '').startswith('text/event-stream'):
            data = []
            found = False
            while time.monotonic() < deadline:
                line = response.readline(65537)
                size += len(line)
                if not line or size > 1_000_000 or len(line) > 65536: break
                line = line.decode('utf-8').rstrip('\r\n')
                if line.startswith('data:'): data.append(line[5:].lstrip())
                if not line and data:
                    value = json.loads('\n'.join(data)); data = []
                    if value.get('id') == payload.get('id'):
                        found = True
                        break
            else: raise MCPError('MCP 响应超时')
            if not found or size > 1_000_000: raise MCPError('MCP 响应未完成或超过大小限制')
        else:
            raw = response.read(1_000_001)
            if len(raw) > 1_000_000: raise MCPError('MCP 响应超过大小限制')
            value = json.loads(raw)
        if value.get('jsonrpc') != '2.0' or value.get('id') != payload.get('id') or 'error' in value: raise MCPError('MCP 协议响应无效')
        return value['result'], new_session
    except MCPError: raise
    except Exception: raise MCPError('MCP 连接或协议不兼容') from None
    finally: connection.close()

def discover(endpoint, token, timeout):
    initialized, session = rpc(endpoint, token, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 'loom', 'version': '0.1.0'}}}, timeout)
    if initialized.get('protocolVersion') != '2025-06-18' or 'tools' not in initialized.get('capabilities', {}): raise MCPError('服务未协商受支持的工具能力')
    rpc(endpoint, token, {'jsonrpc': '2.0', 'method': 'notifications/initialized'}, timeout, session)
    listed, _ = rpc(endpoint, token, {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list', 'params': {}}, timeout, session)
    if listed.get('nextCursor'): raise MCPError('工具列表分页暂不支持，请使用较小的工具服务')
    tools = listed.get('tools')
    if not isinstance(tools, list) or len(tools) > 100: raise MCPError('工具列表格式或数量不支持')
    cleaned = []
    for tool in tools:
        if not isinstance(tool.get('name'), str) or not 1 <= len(tool['name']) <= 128 or not isinstance(tool.get('inputSchema'), dict): raise MCPError('工具定义不完整')
        if len(json.dumps(tool['inputSchema'])) > 20000: raise MCPError('工具参数定义过大')
        cleaned.append({'name': tool['name'], 'description': str(tool.get('description', ''))[:4000], 'inputSchema': tool['inputSchema']})
    if len({t['name'] for t in cleaned}) != len(cleaned): raise MCPError('工具名称重复')
    return cleaned
