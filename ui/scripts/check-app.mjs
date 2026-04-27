import { build } from 'esbuild'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const root = dirname(dirname(fileURLToPath(import.meta.url)))

await build({
  entryPoints: [join(root, 'src', 'App.jsx')],
  bundle: true,
  write: false,
  jsx: 'automatic',
  external: ['react', 'react-dom'],
  loader: {
    '.svg': 'dataurl',
    '.png': 'dataurl',
  },
})

console.log('App.jsx syntax check passed')
