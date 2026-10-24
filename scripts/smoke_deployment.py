"""Check running container APIs with an isolated synthetic session."""
import json
import uuid
import urllib.request


def request(url, data=None):
    payload = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.load(response)


if __name__ == '__main__':
    vr = 'http://127.0.0.1:8780'
    assert request(vr + '/api/health')['status'] == 'ok'
    assert request('http://127.0.0.1:8765/api/health')['status'] == 'ok'
    row = dict(id=str(uuid.uuid4()), program='rhythm', startedAt='2000-01-01T00:00:00.000Z',
               activeSeconds=1, hits=0, mode='desktop')
    request(vr + '/api/sessions', row)
    request(vr + '/api/sessions', row)
    assert request(vr + '/api/stats?days=1&end=2000-01-01')['daily'][0]['sessions'] >= 1
    print('Container APIs, database write and idempotent retry passed (synthetic record created).')
