import assert from 'node:assert/strict';
import { test } from 'node:test';
import { mkdtemp, mkdir, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createHandler } from '../serve.mjs';

test('same-origin API proxy preserves backend status, body and correlation', async () => {
  const handler = createHandler({ fetchApi: async (url, init) => {
    assert.equal(url, 'http://api:8000/monitoring/points?city=hanoi');
    assert.equal(init.headers.get('traceparent'), '00-abc');
    return new Response('[]', {status: 503, headers: {'x-trace-id': 'abc'}});
  }});
  const result = await handler(new Request('http://localhost/api/monitoring/points?city=hanoi',
    {headers: {traceparent: '00-abc'}}));
  assert.equal(result.status, 503);
  assert.equal(result.headers.get('x-trace-id'), 'abc');
  assert.equal(await result.text(), '[]');
});

test('Render hostname-only upstream uses HTTPS without changing the browser origin', async () => {
  const handler = createHandler({apiUpstream: 'traffic-api-demo.onrender.com',
    fetchApi: async (url, init) => {
      assert.equal(url, 'https://traffic-api-demo.onrender.com/system/health');
      assert.equal(init.method, 'GET');
      assert.equal(init.signal.aborted, false);
      return Response.json({status: 'healthy'});
    }});
  const result = await handler(new Request('https://traffic-dashboard-demo.onrender.com/api/system/health'));
  assert.equal(result.status, 200);
  assert.equal((await result.json()).status, 'healthy');
});

test('explicit HTTPS upstream does not double-prefix or double-slash', async () => {
  const handler = createHandler({apiUpstream: 'https://traffic-api-demo.onrender.com/',
    fetchApi: async url => {
      assert.equal(url, 'https://traffic-api-demo.onrender.com/monitoring/points?city=all');
      return Response.json([]);
    }});
  assert.equal((await handler(new Request('https://dashboard.test/api/monitoring/points?city=all'))).status, 200);
});

test('proxy removes stale compression headers after fetch decompresses upstream body', async () => {
  const handler = createHandler({fetchApi: async () => new Response('{"points":12}', {headers: {
    'content-type': 'application/json', 'content-encoding': 'br', 'content-length': '401',
  }})});
  const result = await handler(new Request('https://dashboard.test/api/monitoring/points'));
  assert.equal(result.headers.get('content-encoding'), null);
  assert.equal(result.headers.get('content-length'), null);
  assert.deepEqual(await result.json(), {points: 12});
});

test('proxy refuses writes and reports connection failure without leaking internals', async () => {
  const handler = createHandler({fetchApi: async () => { throw new Error('secret-sentinel'); }});
  assert.equal((await handler(new Request('http://localhost/api/roads', {method: 'POST'}))).status, 405);
  const result = await handler(new Request('http://localhost/api/roads'));
  assert.equal(result.status, 503);
  assert.doesNotMatch(await result.text(), /secret-sentinel/);
});

test('built assets have correct content types, SSR handles routes, files stay confined', async () => {
  const root = await mkdtemp(join(tmpdir(), 'traffic-static-'));
  await mkdir(join(root, 'assets'));
  await writeFile(join(root, 'assets', 'app.js'), 'export const value = 1;');
  const handler = createHandler({clientDir: root,
    serverEntry: {fetch: async () => new Response('<html>operator</html>', {headers: {'content-type': 'text/html'}})}});
  const asset = await handler(new Request('http://localhost/assets/app.js'));
  assert.match(asset.headers.get('content-type'), /javascript/);
  assert.match(await asset.text(), /export const/);
  assert.equal(await (await handler(new Request('http://localhost/live-map'))).text(), '<html>operator</html>');
  assert.equal(await (await handler(new Request('http://localhost/'))).text(), '<html>operator</html>');
  const traversal = await handler(new Request('http://localhost/assets/%2e%2e%2f%2e%2e%2fsecret'));
  assert.equal(traversal.status, 404);
});
