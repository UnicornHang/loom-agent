"""Bounded OpenAI-compatible text calls with DNS-pinned public TLS destinations."""
import http.client
import ipaddress
import json
import socket
import ssl
from urllib.parse import urlsplit, quote

class ModelCallError(Exception):
    pass

def public_addresses(host: str, port: int):
    try:
        addresses = list(dict.fromkeys(info[4][0] for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)))
    except OSError:
        raise ModelCallError('模型地址无法解析') from None
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ModelCallError('模型地址必须解析为公网地址')
    return addresses

class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address, port, timeout):
        super().__init__(host, port=port, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        raw = socket.create_connection((self.address, self.port), self.timeout)
        try: self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise

def complete(base_url: str, api_key: str, model: str, messages: list, max_tokens: int, temperature: float, timeout: int):
    parsed = urlsplit(base_url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ModelCallError('不支持的模型 API 地址')
    try: port = parsed.port or 443
    except ValueError: raise ModelCallError('模型地址端口不合法') from None
    address = public_addresses(parsed.hostname, port)[0]
    connection = PinnedHTTPS(parsed.hostname, address, port, min(timeout, 120))
    payload = json.dumps({'model': model, 'messages': messages, 'max_tokens': max_tokens, 'temperature': temperature}).encode()
    path = quote(parsed.path.rstrip('/') + '/chat/completions', safe='/%:@')
    try:
        connection.request('POST', path, body=payload, headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json', 'Accept-Encoding': 'identity'})
        response = connection.getresponse()
        if response.status != 200: raise ModelCallError(f'模型请求失败（HTTP {response.status}）')
        raw = response.read(2_000_001)
        if len(raw) > 2_000_000: raise ModelCallError('模型响应超过大小限制')
        result = json.loads(raw)
        text = result['choices'][0]['message']['content']
        if not isinstance(text, str) or not text.strip(): raise ModelCallError('模型未返回有效文本')
        return {'text': text, 'usage': result.get('usage')}
    except ModelCallError: raise
    except Exception: raise ModelCallError('模型请求超时或响应格式不兼容，请检查连接配置') from None
    finally: connection.close()


def embed(base_url, api_key, model, text, timeout=30):
    import math
    parsed = urlsplit(base_url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment: raise ModelCallError('无效嵌入模型地址')
    port = parsed.port or 443
    connection = PinnedHTTPS(parsed.hostname, public_addresses(parsed.hostname, port)[0], port, timeout)
    try:
        connection.request('POST', quote(parsed.path.rstrip('/') + '/embeddings', safe='/%:@'), body=json.dumps({'model': model, 'input': text}).encode(), headers={'Authorization': 'Bearer ' + api_key, 'Content-Type': 'application/json', 'Accept-Encoding': 'identity'})
        response = connection.getresponse()
        if response.status != 200: raise ModelCallError('嵌入模型请求失败')
        raw = response.read(1_000_001)
        if len(raw) > 1_000_000: raise ModelCallError('嵌入响应过大')
        value = json.loads(raw)
        vector = value['data'][0]['embedding']
        if not isinstance(vector, list) or not 1 <= len(vector) <= 4096 or not all(isinstance(v, (float, int)) and math.isfinite(v) for v in vector): raise ModelCallError('嵌入向量格式不支持')
        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0 or not math.isfinite(norm): raise ModelCallError('嵌入向量无效')
        usage = value.get('usage')
        return {'embedding': [v / norm for v in vector], 'usage': {**usage, 'completion_tokens': 0} if isinstance(usage, dict) else None}
    except ModelCallError: raise
    except Exception: raise ModelCallError('嵌入请求超时或格式不兼容') from None
    finally: connection.close()
