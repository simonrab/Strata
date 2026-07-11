import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { getAssetDossier } from "../lib/api";
import type {
  AssetDossier as Dossier,
  Source,
  SubIndicationGroup,
  TrialDetail,
} from "../lib/types";
import { Icon } from "../components/Icon";
import { StagePill } from "../components/StagePill";
import { SourceToggle, loadSources } from "../components/SourceToggle";
import { ApprovalsList } from "../components/ApprovalsList";
import { LoadingState } from "../components/Loading";

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

function SubIndicationCard({
  group,
  trialsById,
}: {
  group: SubIndicationGroup;
  trialsById: Map<string, TrialDetail>;
}) {
  const [open, setOpen] = useState(false);
  const trials = group.trial_ids.map((id) => trialsById.get(id) ?? { nct_id: id });

  return (
    <div className="rounded-md hairline bg-card-light">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 p-3 text-left"
      >
        <span className="flex items-center gap-1.5">
          <Icon
            name="chevron_right"
            size={16}
            className={`text-ink-muted-light transition-transform ${open ? "rotate-90" : ""}`}
          />
          <span className="text-[14px] font-medium text-ink-light">{group.label}</span>
        </span>
        <span className="font-mono text-[12px] text-ink-muted-light">
          {group.trial_ids.length} trials
        </span>
      </button>

      <div className="px-3 pb-3">
        <div className="flex flex-wrap gap-1">
          {group.phases.map((p) => (
            <StagePill key={p} phase={p as never} />
          ))}
        </div>

        {open && (
          <ul
            data-testid={`subind-trials-${group.signature}`}
            className="mt-3 space-y-1 border-t border-hairline-light pt-3"
          >
            {trials.map((t) => {
              const detail = "phase" in t ? (t as TrialDetail) : null;
              return (
                <li
                  key={t.nct_id}
                  className="flex items-center gap-2 text-[13px] text-ink-light"
                >
                  <span className="font-mono text-ink-muted-light">{t.nct_id}</span>
                  {detail && <StagePill phase={detail.phase} />}
                  {detail?.status && (
                    <span className="text-[11px] uppercase tracking-wider text-outline">
                      {detail.status}
                    </span>
                  )}
                  <span className="truncate">{detail?.title ?? "—"}</span>
                  {detail?.has_results && (
                    <Icon
                      name="check_circle"
                      size={14}
                      className="ml-auto shrink-0 text-risk-low"
                      label="has results"
                    />
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
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
  const trialsById = useMemo(
    () => new Map((dossier?.trials ?? []).map((t) => [t.nct_id, t])),
    [dossier]
  );

  return (
    <div className="mx-auto max-w-6xl px-8 py-10">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-sans text-display-lg text-ink-light">{decodeURIComponent(name)}</h1>
          <p className="mt-1 font-serif text-[16px] text-ink-muted-light">
            {dossier?.asset.sponsor && (
              <>
                <Link
                  to={`/company/${encodeURIComponent(dossier.asset.sponsor)}`}
                  className="text-accent hover:underline"
                  title={`See ${dossier.asset.sponsor}'s entire pipeline`}
                >
                  {dossier.asset.sponsor}
                </Link>
                {" · "}
              </>
            )}
            {dossier?.trials.length ?? 0} trials across {dossier?.countries.length ?? 0} countries.
          </p>
        </div>
        <SourceToggle value={sources} onChange={setSources} />
      </div>

      {error && <p className="mt-6 font-mono text-[13px] text-risk-high">Could not load the dossier.</p>}
      {loading && !dossier && <LoadingState label="Building dossier…" />}

      {dossier && (
        <>
          <Section title="Sub-indications" icon="account_tree">
            <div className="grid items-start gap-3 md:grid-cols-2">
              {dossier.sub_indications.map((g) => (
                <SubIndicationCard key={g.signature} group={g} trialsById={trialsById} />
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
            <p className="mb-2 text-[12px] text-ink-muted-light">
              <Icon name="flag" size={13} className="mr-1 align-[-2px] text-ink-muted-light" />
              Source: openFDA — <span className="font-medium text-ink-light">US FDA only</span>.
              Absence here does not imply the drug is unapproved elsewhere (e.g. EMA, PMDA).
            </p>
            {dossier.approvals.length === 0 ? (
              <p className="text-[13px] text-ink-muted-light">
                No US FDA approvals found
                {sources.includes("openfda") ? "." : " (openFDA source is off)."}
              </p>
            ) : (
              <ApprovalsList approvals={dossier.approvals} />
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
