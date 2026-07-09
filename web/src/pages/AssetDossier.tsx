import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useParams } from "react-router-dom";
import { getAssetDossier } from "../lib/api";
import type { AssetDossier as Dossier, Source } from "../lib/types";
import { Icon } from "../components/Icon";
import { StagePill } from "../components/StagePill";
import { EvidenceBadgeView } from "../components/EvidenceBadgeView";
import { SourceToggle, loadSources } from "../components/SourceToggle";

function Bar({ label, value, max }: { label: string; value: number; max: number }) {
  return (
    <div className="flex items-center gap-2 text-[12px]">
      <span className="w-40 truncate text-ink-light" title={label}>{label}</span>
      <span className="h-2 rounded-sm bg-accent" style={{ width: `${(value / max) * 160}px` }} />
      <span className="font-mono text-ink-muted-light">{value}</span>
    </div>
  );
}

function Section({ title, icon, children }: { title: string; icon: string; children: ReactNode }) {
  return (
    <section className="mt-8">
      <h2 className="mb-3 flex items-center gap-2 text-section-sm text-ink-light">
        <Icon name={icon} size={18} className="text-ink-muted-light" />
        {title}
      </h2>
      {children}
    </section>
  );
}

export function AssetDossier() {
  const { name = "" } = useParams();
  const [sources, setSources] = useState<Source[]>(loadSources());
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    getAssetDossier(name, sources)
      .then((d) => { setDossier(d); setError(false); })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [name, sources]);

  const maxCountry = Math.max(1, ...(dossier?.countries ?? []).map((c) => c.trials));

  return (
    <div className="mx-auto max-w-6xl px-8 py-10">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-sans text-display-lg text-ink-light">{decodeURIComponent(name)}</h1>
          <p className="mt-1 font-serif text-[16px] text-ink-muted-light">
            {dossier?.asset.sponsor ? `${dossier.asset.sponsor} · ` : ""}
            {dossier?.trials.length ?? 0} trials across {dossier?.countries.length ?? 0} countries.
          </p>
        </div>
        <SourceToggle value={sources} onChange={setSources} />
      </div>

      {error && <p className="mt-6 font-mono text-[13px] text-risk-high">Could not load the dossier.</p>}
      {loading && !dossier && <p className="mt-6 font-mono text-[13px] text-ink-muted-light">Building dossier…</p>}

      {dossier && (
        <>
          <Section title="Sub-indications" icon="account_tree">
            <div className="grid gap-3 md:grid-cols-2">
              {dossier.sub_indications.map((g) => (
                <div key={g.signature} className="rounded-md hairline bg-card-light p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[14px] font-medium text-ink-light">{g.label}</span>
                    <span className="font-mono text-[12px] text-ink-muted-light">{g.trial_ids.length} trials</span>
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {g.phases.map((p) => (
                      <StagePill key={p} phase={p as never} />
                    ))}
                  </div>
                  {g.evidence && <EvidenceBadgeView badge={g.evidence} />}
                </div>
              ))}
            </div>
          </Section>

          <Section title="Geography" icon="public">
            {dossier.countries.length === 0 ? (
              <p className="text-[13px] text-ink-muted-light">No location data.</p>
            ) : (
              <div className="space-y-1">
                {dossier.countries.slice(0, 12).map((c) => (
                  <Bar key={c.country} label={c.country} value={c.trials} max={maxCountry} />
                ))}
              </div>
            )}
          </Section>

          <Section title="Readouts" icon="fact_check">
            {dossier.readouts.length === 0 ? (
              <p className="text-[13px] text-ink-muted-light">No trials have posted results yet.</p>
            ) : (
              <ul className="space-y-1">
                {dossier.readouts.map((t) => (
                  <li key={t.nct_id} className="flex items-center gap-2 text-[13px] text-ink-light">
                    <Icon name="check_circle" size={15} className="text-risk-low" />
                    <span className="font-mono text-ink-muted-light">{t.nct_id}</span>
                    <StagePill phase={t.phase} />
                    <span className="truncate">{t.title}</span>
                    {t.results_posted_date && (
                      <span className="ml-auto font-mono text-[11px] text-ink-muted-light">
                        {t.results_posted_date}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section title="Regulatory approvals" icon="verified">
            {dossier.approvals.length === 0 ? (
              <p className="text-[13px] text-ink-muted-light">
                No approvals found{sources.includes("openfda") ? "." : " (openFDA source is off)."}
              </p>
            ) : (
              <ul className="space-y-1">
                {dossier.approvals.map((a) => (
                  <li key={a.application_number} className="flex items-center gap-2 text-[13px]">
                    <Icon name="verified" size={15} className="text-accent" />
                    <span className="font-medium text-ink-light">{a.brand_names.join(", ") || a.drug}</span>
                    <span className="font-mono text-ink-muted-light">{a.application_number}</span>
                    {a.approval_date && <span className="text-ink-muted-light">· {a.approval_date}</span>}
                    {a.marketing_status && <span className="text-ink-muted-light">· {a.marketing_status}</span>}
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section title={`All trials (${dossier.trials.length})`} icon="science">
            <div className="overflow-x-auto rounded-md hairline bg-card-light">
              <table className="min-w-[760px] w-full text-[13px]">
                <thead>
                  <tr className="hairline-b text-left text-label-caps uppercase text-ink-muted-light">
                    <th className="p-2">Trial</th>
                    <th className="p-2">Phase</th>
                    <th className="p-2">Status</th>
                    <th className="p-2 text-right">Enrolment</th>
                    <th className="p-2">Countries</th>
                    <th className="p-2">Readout</th>
                  </tr>
                </thead>
                <tbody>
                  {dossier.trials.map((t) => (
                    <tr key={t.nct_id} className="hairline-b last:border-0">
                      <td className="p-2 font-mono text-ink-muted-light">{t.nct_id}</td>
                      <td className="p-2"><StagePill phase={t.phase} /></td>
                      <td className="p-2 text-ink-light">{t.status ?? "—"}</td>
                      <td className="p-2 text-right font-mono text-ink-light">
                        {t.enrollment?.toLocaleString() ?? "—"}
                      </td>
                      <td className="p-2 text-ink-muted-light">{t.countries.length}</td>
                      <td className="p-2">
                        {t.has_results ? (
                          <Icon name="check_circle" size={15} className="text-risk-low" label="has results" />
                        ) : (
                          <span className="text-outline-variant">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
        </>
      )}
    </div>
  );
}
