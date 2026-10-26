/** Small Node adapter for the built TanStack fetch handler and same-origin API. */
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { resolve, extname, sep } from 'node:path';
import { pathToFileURL } from 'node:url';

const types = {'.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.ico': 'image/x-icon', '.woff2': 'font/woff2', '.json': 'application/json'};

export function createHandler({clientDir = resolve('dist/client'),
  apiUpstream = process.env.API_UPSTREAM || 'http://api:8000', fetchApi = fetch, serverEntry} = {}) {
  const root = resolve(clientDir);
  let entry = serverEntry;
  return async request => {
    const url = new URL(request.url);
    if (!['GET', 'HEAD'].includes(request.method)) return new Response('Method not allowed', {status: 405});
    if (url.pathname.startsWith('/api/')) {
      try {
        const headers = new Headers();
        for (const key of ['accept', 'traceparent', 'tracestate']) {
          if (request.headers.has(key)) headers.set(key, request.headers.get(key));
        }
        return await fetchApi(`${apiUpstream}${url.pathname.slice(4)}${url.search}`,
          {method: request.method, headers, signal: AbortSignal.timeout(10000), redirect: 'manual'});
      } catch {
        return Response.json({detail: 'Traffic API is unavailable'}, {status: 503});
      }
    }
    let pathname;
    try { pathname = decodeURIComponent(url.pathname); } catch { return new Response('Not found', {status: 404}); }
    const file = resolve(root, `.${pathname}`);
    if (file !== root && !file.startsWith(root + sep)) return new Response('Not found', {status: 404});
    try {
      const body = await readFile(file);
      return new Response(request.method === 'HEAD' ? null : body,
        {headers: {'content-type': types[extname(file)] || 'application/octet-stream'}});
    } catch {
      if (url.pathname.startsWith('/assets/')) return new Response('Not found', {status: 404});
    }
    entry ??= (await import('./dist/server/server.js')).default;
    return entry.fetch(request);
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const handler = createHandler();
  createServer(async (incoming, outgoing) => {
    try {
      const request = new Request(`http://${incoming.headers.host || 'localhost'}${incoming.url}`,
        {method: incoming.method, headers: incoming.headers});
      const response = await handler(request);
      outgoing.writeHead(response.status, Object.fromEntries(response.headers));
      outgoing.end(Buffer.from(await response.arrayBuffer()));
    } catch {
      outgoing.writeHead(500, {'content-type': 'text/plain'});
      outgoing.end('Dashboard unavailable');
    }
  }).listen(Number(process.env.PORT || 5173), '0.0.0.0');
}
