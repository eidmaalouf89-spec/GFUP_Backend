const { build } = await import('vite')
const react = (await import('@vitejs/plugin-react')).default

await build({
  configFile: false,
  plugins: [react()],
})
