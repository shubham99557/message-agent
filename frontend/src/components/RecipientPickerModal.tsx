import React, { useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import { Search, RefreshCw } from 'lucide-react';

type Candidate = Awaited<ReturnType<typeof api.getCampaignCandidates>>['items'][number];
type SkippedItem = Awaited<ReturnType<typeof api.addCampaignRecipients>>['skipped'][number];

interface RecipientPickerModalProps {
  campaign: { id: number; name: string };
  onClose: () => void;
  onAdded: () => void;
  onGoToDiscovery?: () => void;
}

export const RecipientPickerModal: React.FC<RecipientPickerModalProps> = ({ campaign, onClose, onAdded, onGoToDiscovery }) => {
  const [scope, setScope] = useState<'campaign' | 'all'>('campaign');
  const [showBlocked, setShowBlocked] = useState(false);
  const [search, setSearch] = useState('');
  const [items, setItems] = useState<Candidate[]>([]);
  const [campaignLeadCount, setCampaignLeadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState<{ added: number; skipped: SkippedItem[] } | null>(null);

  const load = async (nextScope = scope) => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getCampaignCandidates(campaign.id, { scope: nextScope });
      setItems(res.items);
      setCampaignLeadCount(res.campaign_lead_count);
      // Drop selections that are no longer eligible / visible
      const eligibleIds = new Set(res.items.filter((i) => i.eligible).map((i) => i.id));
      setSelected((prev) => new Set([...prev].filter((id) => eligibleIds.has(id))));
    } catch (err: any) {
      setError(err.message || 'Could not load leads.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load('campaign');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaign.id]);

  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    return items.filter((c) => {
      if (!showBlocked && !c.eligible) return false;
      if (!q) return true;
      return [c.name, c.city, c.email, c.industry].some((v) => (v || '').toLowerCase().includes(q));
    });
  }, [items, search, showBlocked]);

  const visibleEligible = visible.filter((c) => c.eligible);
  const blockedCount = items.filter((c) => !c.eligible).length;
  const allVisibleSelected = visibleEligible.length > 0 && visibleEligible.every((c) => selected.has(c.id));

  const toggle = (id: number) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const toggleAllVisible = () =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (allVisibleSelected) visibleEligible.forEach((c) => next.delete(c.id));
      else visibleEligible.forEach((c) => next.add(c.id));
      return next;
    });

  const switchScope = (next: 'campaign' | 'all') => {
    setScope(next);
    load(next);
  };

  const handleAdd = async () => {
    if (selected.size === 0) return;
    setSaving(true);
    setError(null);
    try {
      const res = await api.addCampaignRecipients(campaign.id, [...selected]);
      setResult({ added: res.added_count, skipped: res.skipped || [] });
      setSelected(new Set());
      onAdded();
      await load();
    } catch (err: any) {
      setError(`Add failed: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 z-50">
      <div className="bg-cobalt-900 border border-cobalt-700 rounded-lg p-5 w-full max-w-2xl space-y-3 text-xs">
        <div className="flex items-center justify-between border-b border-cobalt-800 pb-3">
          <h3 className="font-bold text-slate-100 text-sm">Add Companies to "{campaign.name}"</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-white" aria-label="Close">✕</button>
        </div>

        {/* Scope + filters */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded border border-cobalt-700 overflow-hidden">
            <button
              onClick={() => switchScope('campaign')}
              className={`px-2.5 py-1 ${scope === 'campaign' ? 'bg-cobalt-600 text-white' : 'bg-cobalt-950 text-slate-300'}`}
            >
              This campaign's discoveries ({campaignLeadCount})
            </button>
            <button
              onClick={() => switchScope('all')}
              className={`px-2.5 py-1 ${scope === 'all' ? 'bg-cobalt-600 text-white' : 'bg-cobalt-950 text-slate-300'}`}
            >
              All CRM leads
            </button>
          </div>
          <div className="relative flex-1 min-w-[160px]">
            <Search className="w-3.5 h-3.5 absolute left-2 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search name, city, email…"
              className="w-full bg-cobalt-950 border border-cobalt-800 rounded pl-7 pr-2 py-1 text-slate-200 focus:outline-none focus:border-cobalt-600"
            />
          </div>
          <label className="flex items-center gap-1.5 text-slate-400 cursor-pointer">
            <input type="checkbox" checked={showBlocked} onChange={(e) => setShowBlocked(e.target.checked)} />
            Show blocked ({blockedCount})
          </label>
        </div>

        {scope === 'all' && (
          <div className="rounded border border-amber-700/50 bg-amber-900/20 px-2.5 py-1.5 text-amber-200">
            Showing every lead in the CRM. Leads already in another active campaign or contacted in the last 30 days are still blocked.
          </div>
        )}

        {/* Select all bar */}
        <div className="flex items-center justify-between px-2 py-1.5 rounded bg-cobalt-950/70 border border-cobalt-800">
          <label className="flex items-center gap-2 cursor-pointer text-slate-200 font-medium">
            <input type="checkbox" checked={allVisibleSelected} disabled={visibleEligible.length === 0} onChange={toggleAllVisible} />
            Select all {visibleEligible.length} addable{search ? ' matching' : ''} leads
          </label>
          <span className="text-slate-400">{selected.size} selected</span>
        </div>

        {/* List */}
        <div className="max-h-80 overflow-y-auto space-y-1.5 pr-1">
          {loading ? (
            <div className="flex items-center justify-center py-8 text-slate-400 gap-2">
              <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Loading leads…
            </div>
          ) : visible.length === 0 ? (
            <div className="py-6 text-center text-slate-400 space-y-2">
              {scope === 'campaign' && campaignLeadCount === 0 ? (
                <>
                  <div>No leads have been discovered for this campaign yet.</div>
                  <div>
                    Run Lead Discovery with this campaign selected
                    {onGoToDiscovery && (
                      <> (<button className="text-cobalt-300 underline" onClick={onGoToDiscovery}>open Discovery</button>)</>
                    )}
                    , or switch to <button className="text-cobalt-300 underline" onClick={() => switchScope('all')}>All CRM leads</button>.
                  </div>
                </>
              ) : (
                <div>No addable leads{search ? ' match your search' : ''}.{!showBlocked && blockedCount > 0 ? ` ${blockedCount} blocked lead(s) hidden.` : ''}</div>
              )}
            </div>
          ) : (
            visible.map((c) => {
              const checked = selected.has(c.id);
              return (
                <label
                  key={c.id}
                  className={`flex items-center justify-between gap-3 p-2 rounded border ${
                    c.eligible
                      ? 'bg-cobalt-950/70 border-cobalt-800 cursor-pointer hover:border-cobalt-600'
                      : 'bg-cobalt-950/30 border-cobalt-900 opacity-60 cursor-not-allowed'
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <input type="checkbox" checked={checked} disabled={!c.eligible} onChange={() => toggle(c.id)} />
                    <div className="min-w-0">
                      <div className="font-semibold text-slate-200 truncate">
                        {c.name}
                        {scope === 'all' && c.from_this_campaign && (
                          <span className="ml-1.5 text-[9px] px-1 py-0.5 rounded bg-cobalt-700 text-cobalt-100 align-middle">this campaign</span>
                        )}
                      </div>
                      <div className="text-[10px] text-slate-400 truncate">{c.city} • {c.email || 'No email'}</div>
                      {!c.eligible && (
                        <div className="text-[10px] text-rose-300">{c.reasons.map((r) => r.message).join(' · ')}</div>
                      )}
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className="font-mono text-[10px] text-emerald-400">{c.laptop_count_verified ?? '?'} laptops</div>
                    {typeof c.qualification_score === 'number' && (
                      <div className="font-mono text-[10px] text-slate-400">score {Math.round(c.qualification_score)}</div>
                    )}
                  </div>
                </label>
              );
            })
          )}
        </div>

        {error && <div className="text-rose-300">{error}</div>}

        {result && (
          <div className="rounded border border-cobalt-700 bg-cobalt-950/70 px-2.5 py-2 space-y-1">
            <div className="text-emerald-300 font-medium">Added {result.added} lead(s).</div>
            {result.skipped.length > 0 && (
              <>
                <div className="text-amber-300">Skipped {result.skipped.length}:</div>
                <ul className="list-disc pl-4 text-slate-300 max-h-24 overflow-y-auto">
                  {result.skipped.map((s) => (
                    <li key={s.company_id}>
                      {s.name || `#${s.company_id}`}: {s.reasons.map((r) => r.message).join(' · ')}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        )}

        <div className="flex justify-end space-x-2 pt-2 border-t border-cobalt-800">
          <button onClick={onClose} className="px-3 py-1.5 bg-cobalt-950 text-slate-300 rounded">
            {result ? 'Done' : 'Cancel'}
          </button>
          <button
            onClick={handleAdd}
            disabled={selected.size === 0 || saving}
            className="px-3.5 py-1.5 bg-cobalt-600 hover:bg-cobalt-500 disabled:opacity-40 text-white rounded font-medium"
          >
            {saving ? 'Adding…' : `Add Selected (${selected.size})`}
          </button>
        </div>
      </div>
    </div>
  );
};
