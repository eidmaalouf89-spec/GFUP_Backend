/* Wrapper page: renders the fiche inside the app shell with a back button. */
function ConsultantFichePage({ consultant, onBack, focusMode }) {
  // For this prototype all consultants share FICHE_DATA, but we inject the
  // selected consultant's display name/role/id so the masthead feels right.
  const base = window.FICHE_DATA;
  const data = consultant ? {
    ...base,
    consultant: {
      ...base.consultant,
      id: consultant.id ?? base.consultant.id,
      slug: consultant.slug ?? base.consultant.slug,
      display_name: consultant.name ?? base.consultant.display_name,
      role: consultant.role ?? base.consultant.role,
    },
    header: {
      ...base.header,
      total: consultant.total ?? base.header.total,
      answered: consultant.answered ?? base.header.answered,
      open_count: consultant.pending ?? base.header.open_count,
    }
  } : base;

  return (
    <div style={{ animation: 'fadeInUp 0.4s cubic-bezier(.4,0,.2,1)' }}>
      <window.ConsultantFiche data={data} lang="fr" onBack={onBack}/>
    </div>
  );
}
window.ConsultantFichePage = ConsultantFichePage;
