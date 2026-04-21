# COWORK PATCH — Dashboard Chart Title + Weekly Label

## OBJECTIVE
When Focus Mode is ON, the dashboard timeseries switches to weekly data (backend already does this). But the UI still shows "Monthly Activity" as the chart title, and doesn't adapt the label display. This patch fixes both.

## RULES
- PATCH ONLY — surgical edits to `ui/src/App.jsx`, nothing else
- Do NOT touch any Python files
- Do NOT run `npm run build`
- Apply both edits below, then run the verification checks at the bottom

---

## EDIT 1 — Change chart title based on focusMode

Find this exact line (around line 576):
```jsx
          <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 16, color: T.text }}>Monthly Activity</div>
```

Replace with:
```jsx
          <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 16, color: T.text }}>{focusMode ? 'Weekly Activity (Focus)' : 'Monthly Activity'}</div>
```

---

## EDIT 2 — Adapt x-axis label for weekly format

The weekly data uses labels like `"2026-S14"`. The current code does `m.month.slice(5)` which produces `S14` — that's actually fine for weekly. But for monthly it produces `03`, `04`, etc. which is also fine. No change needed here.

However, when there are 26 weekly bars vs 12 monthly bars, the chart gets cramped. Add a max-width constraint.

Find this line (around line 588):
```jsx
                  <div style={{ fontSize: 9, color: T.dim, transform: 'rotate(-45deg)', transformOrigin: 'center', whiteSpace: 'nowrap' }}>
                    {m.month.slice(5)}
```

Replace with:
```jsx
                  <div style={{ fontSize: focusMode ? 8 : 9, color: T.dim, transform: 'rotate(-45deg)', transformOrigin: 'center', whiteSpace: 'nowrap' }}>
                    {m.month.slice(5)}
```

---

## MANDATORY VERIFICATION (do not skip)

After ALL edits are applied, run these checks IN ORDER.

### Check 1 — File integrity
```bash
echo "=== App.jsx tail ===" && tail -5 ui/src/App.jsx
echo "=== ConsultantFiche.jsx tail ===" && tail -5 ui/src/components/ConsultantFiche.jsx
```
App.jsx must end with a closing `}`.
ConsultantFiche.jsx must end with `export default ConsultantFiche;`.

### Check 2 — Verify the edits took effect
```bash
grep -n "Weekly Activity\|Monthly Activity" ui/src/App.jsx
```
Must show the ternary expression with both strings.

### Check 3 — Fast syntax check
```bash
cd ui && npx esbuild src/App.jsx --bundle --jsx=automatic --outfile=/dev/null --loader:.svg=file --loader:.png=file --external:react --external:react-dom 2>&1 | head -20
```
Must exit 0 with no errors.

Only after all 3 checks pass, report the result and stop.
