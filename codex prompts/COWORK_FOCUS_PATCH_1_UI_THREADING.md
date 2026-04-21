# COWORK PATCH — Thread Focus Mode to All Pages

## OBJECTIVE
Focus Mode currently only works on the Dashboard (OverviewPage). The Consultants and Contractors pages ignore it completely — they call the API without focus parameters, so they always show unfiltered data. This patch threads `focusMode` and `staleDays` from App state through every page.

## RULES
- PATCH ONLY — surgical edits to `ui/src/App.jsx`, nothing else
- Do NOT touch any Python files
- Do NOT run `npm run build` (it fails in sandbox with spawn EPERM — this is known and expected)
- Apply all 5 edits below, then run the verification checks at the bottom

---

## EDIT 1 — renderPage: pass focus props to ConsultantsPage and ContractorsPage

Find this exact block (around line 1797):
```jsx
      case 'Consultants':
        return <ConsultantsPage />
      case 'Contractors':
        return <ContractorsPage />
```

Replace with:
```jsx
      case 'Consultants':
        return <ConsultantsPage focusMode={focusMode} staleDays={staleDays} />
      case 'Contractors':
        return <ContractorsPage focusMode={focusMode} staleDays={staleDays} />
```

---

## EDIT 2 — ConsultantsPage: accept focus props, pass to API and to fiche view

Find the function signature (around line 1229):
```jsx
function ConsultantsPage() {
```

Replace with:
```jsx
function ConsultantsPage({ focusMode, staleDays }) {
```

Find the API call (around line 1240):
```jsx
        const data = await api.call("get_consultant_list")
```

Replace with:
```jsx
        const data = await api.call("get_consultant_list", focusMode, staleDays)
```

Find the useEffect dependency array (around line 1255):
```jsx
  }, [])
```

Replace with:
```jsx
  }, [focusMode, staleDays])
```

Find where ConsultantFicheView is rendered (around line 1259):
```jsx
    return <ConsultantFicheView key={selectedConsultant} consultantName={selectedConsultant} onBack={() => setSelectedConsultant(null)} />
```

Replace with:
```jsx
    return <ConsultantFicheView key={selectedConsultant} consultantName={selectedConsultant} onBack={() => setSelectedConsultant(null)} focusMode={focusMode} staleDays={staleDays} />
```

---

## EDIT 3 — ConsultantFicheView: accept focus props, pass to API call

Find the function signature (around line 1150):
```jsx
function ConsultantFicheView({ consultantName, onBack }) {
```

Replace with:
```jsx
function ConsultantFicheView({ consultantName, onBack, focusMode, staleDays }) {
```

Find the API call (around line 1157):
```jsx
    api.call("get_consultant_fiche", consultantName)
```

Replace with:
```jsx
    api.call("get_consultant_fiche", consultantName, focusMode, staleDays)
```

Find the useEffect dependency array (around line 1173):
```jsx
  }, [consultantName])
```

Replace with:
```jsx
  }, [consultantName, focusMode, staleDays])
```

---

## EDIT 4 — ContractorsPage: accept focus props, pass to API and to fiche

Find the function signature (around line 1563):
```jsx
function ContractorsPage() {
```

Replace with:
```jsx
function ContractorsPage({ focusMode, staleDays }) {
```

Find the API call (around line 1574):
```jsx
        const data = await api.call("get_contractor_list")
```

Replace with:
```jsx
        const data = await api.call("get_contractor_list", focusMode, staleDays)
```

Find the useEffect dependency array (around line 1589):
```jsx
  }, [])
```

Replace with:
```jsx
  }, [focusMode, staleDays])
```

Find where ContractorFiche is rendered (around line 1593):
```jsx
    return <ContractorFiche contractorCode={selectedContractor} onBack={() => setSelectedContractor(null)} />
```

Replace with:
```jsx
    return <ContractorFiche contractorCode={selectedContractor} onBack={() => setSelectedContractor(null)} focusMode={focusMode} staleDays={staleDays} />
```

---

## EDIT 5 — ContractorFiche: accept focus props, pass to API call

Find the function signature (around line 1357):
```jsx
function ContractorFiche({ contractorCode, onBack }) {
```

Replace with:
```jsx
function ContractorFiche({ contractorCode, onBack, focusMode, staleDays }) {
```

Find the API call (around line 1367):
```jsx
        const data = await api.call("get_contractor_fiche", contractorCode)
```

Replace with:
```jsx
        const data = await api.call("get_contractor_fiche", contractorCode, focusMode, staleDays)
```

Find the useEffect dependency array (around line 1382):
```jsx
  }, [contractorCode])
```

Replace with:
```jsx
  }, [contractorCode, focusMode, staleDays])
```

---

## MANDATORY VERIFICATION (do not skip)

After ALL edits are applied, run these checks IN ORDER.
Do NOT report the task as complete until all pass.

### Check 1 — File integrity
```bash
echo "=== App.jsx tail ===" && tail -5 ui/src/App.jsx
echo "=== ConsultantFiche.jsx tail ===" && tail -5 ui/src/components/ConsultantFiche.jsx
```
App.jsx must end with a closing `}`.
ConsultantFiche.jsx must end with `export default ConsultantFiche;`.
If either file is truncated, STOP and fix before continuing.

### Check 2 — Verify the 5 edits took effect
```bash
echo "=== Edit 1 ===" && grep -n "ConsultantsPage\|ContractorsPage" ui/src/App.jsx | grep "focusMode"
echo "=== Edit 2 ===" && grep -n "function ConsultantsPage" ui/src/App.jsx
echo "=== Edit 3 ===" && grep -n "function ConsultantFicheView" ui/src/App.jsx
echo "=== Edit 4 ===" && grep -n "function ContractorsPage" ui/src/App.jsx
echo "=== Edit 5 ===" && grep -n "function ContractorFiche" ui/src/App.jsx
```
Each function must show `focusMode` in its props. Each API call must show `focusMode, staleDays` as arguments.

### Check 3 — Fast syntax check (no Vite, no spawn issues)
```bash
cd ui && npx esbuild src/App.jsx --bundle --jsx=automatic --outfile=/dev/null --loader:.svg=file --loader:.png=file --external:react --external:react-dom 2>&1 | head -20
```
Must exit 0 with no errors. If syntax errors appear, fix them and re-run.

Only after all 3 checks pass, report the result and stop.
