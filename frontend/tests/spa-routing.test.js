import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

test('Vercel serves SPA routes after preserving filesystem and API paths', () => {
  const config = JSON.parse(readFileSync(new URL('../vercel.json', import.meta.url)));
  assert.equal(config.routes[0].handle, 'filesystem');
  const fallback = config.routes.filter((route) => route.dest === '/index.html');
  const matches = (path) => fallback.some((route) => new RegExp(`^${route.src}$`).test(path));
  for (const path of ['/', '/inventario', '/inventario/almacenes', '/inventario/materiales',
    '/inventario/movimientos', '/inventario/kardex', '/inventario/requisiciones',
    '/inventario/resumen', '/inventario/traspasos', '/inventario/proveedores',
    '/inventario/ordenes-compra', '/inventario/proyectos', '/inventario/equipos',
    '/inventario/ordenes-trabajo', '/inventario/reportes']) {
    assert.ok(matches(path), path);
  }
  for (const path of ['/api', '/api/health', '/inventory/requisitions', '/assets/missing.js',
    '/assets/app.css', '/images/logo.png', '/images/logo.jpg', '/images/logo.webp',
    '/images/logo.svg', '/favicon.ico', '/manifest.json', '/manifest.webmanifest',
    '/inventario/missing.js', '/inventario/logo.png', '/api/inventory/requisitions']) {
    assert.equal(matches(path), false, path);
  }
});
