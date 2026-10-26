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
