import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Archive,
  Bell,
  CalendarClock,
  Check,
  ChevronRight,
  CreditCard,
  Download,
  Eye,
  EyeOff,
  GripVertical,
  Home,
  Pencil,
  Plus,
  RefreshCcw,
  Search,
  Settings,
  Tag,
  Trash2,
  Upload,
  WalletCards,
} from "lucide-react";
import { api, imageUrl } from "./api";
import {
  MONTHS,
  bankColor,
  bonusProgress,
  daysUntilMonth,
  emptyCard,
  feeTone,
  fmtDate,
  fmtMoney,
  fmtMoneyShort,
  isBonusActive,
  monthIndex,
} from "./utils";
import "./styles.css";

const nav = [
  { id: "overview", label: "Overview", icon: Home },
  { id: "cards", label: "Cards", icon: WalletCards },
  { id: "bonuses", label: "Bonuses", icon: Check },
  { id: "fees", label: "Fees", icon: CalendarClock },
  { id: "tags", label: "Tags", icon: Tag },
  { id: "settings", label: "Settings", icon: Settings },
];

function App() {
  const [cards, setCards] = useState([]);
  const [tags, setTags] = useState([]);
  const [page, setPage] = useState("overview");
  const [selectedId, setSelectedId] = useState(null);
  const [editing, setEditing] = useState(null);
  const [query, setQuery] = useState("");
  const [showCancelled, setShowCancelled] = useState(true);
  const [hideLast4, setHideLast4] = useState(false);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState("");

  async function refresh() {
    const [nextCards, nextTags] = await Promise.all([api.cards(), api.tags()]);
    setCards(nextCards);
    setTags(nextTags);
    setLoading(false);
  }

  useEffect(() => {
    refresh().catch((error) => {
      setToast(error.message);
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(""), 2600);
    return () => clearTimeout(id);
  }, [toast]);

  const selected = cards.find((card) => card.id === selectedId);

  async function mutate(fn, message) {
    try {
      const next = await fn();
      if (Array.isArray(next)) setCards(next);
      else await refresh();
      if (message) setToast(message);
    } catch (error) {
      setToast(error.message);
    }
  }

  const counts = useMemo(() => {
    const active = cards.filter((card) => card.status === "active");
    const cancelled = cards.filter((card) => card.status === "cancelled");
    const urgentFees = active.filter((card) => daysUntilMonth(card.feeMonth) <= 30).length;
    const bonuses = active.filter(isBonusActive);
    return { active, cancelled, urgentFees, bonuses };
  }, [cards]);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">CC</div>
          <div>
            <div className="brand-name">Card Tracker</div>
            <div className="brand-sub">Private finance console</div>
          </div>
        </div>

        <div className="nav-label">Tracking</div>
        {nav.slice(0, 4).map((item) => (
          <NavButton key={item.id} item={item} page={page} setPage={setPage} count={navCount(item.id, counts)} />
        ))}
        <div className="nav-label">Manage</div>
        {nav.slice(4).map((item) => (
          <NavButton key={item.id} item={item} page={page} setPage={setPage} count={navCount(item.id, counts)} />
        ))}

        <div className="sidebar-footer">
          <label className="switch-row">
            <input type="checkbox" checked={hideLast4} onChange={(event) => setHideLast4(event.target.checked)} />
            {hideLast4 ? <EyeOff size={15} /> : <Eye size={15} />}
            Hide last 4
          </label>
          <label className="switch-row">
            <input type="checkbox" checked={showCancelled} onChange={(event) => setShowCancelled(event.target.checked)} />
            Show cancelled
          </label>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <div className="crumb">Dashboard / <span>{nav.find((item) => item.id === page)?.label}</span></div>
          </div>
          <div className="search">
            <Search size={15} />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search cards, banks, tags..." />
          </div>
          <button className="btn primary" onClick={() => setEditing(emptyCard())}>
            <Plus size={15} /> Add card
          </button>
        </header>

        {loading ? (
          <div className="content"><div className="panel empty">Loading tracker...</div></div>
        ) : (
          <Router
            page={page}
            cards={cards}
            tags={tags}
            query={query}
            showCancelled={showCancelled}
            hideLast4={hideLast4}
            selected={selected}
            setPage={setPage}
            setSelectedId={setSelectedId}
            setEditing={setEditing}
            mutate={mutate}
            refresh={refresh}
          />
        )}
      </main>

      {editing && (
        <CardEditor
          card={editing}
          tags={tags}
          onClose={() => setEditing(null)}
          onSave={(payload) => mutate(
            () => payload.id ? api.updateCard(payload.id, payload) : api.createCard(payload),
            payload.id ? "Card updated" : "Card added"
          ).then(() => setEditing(null))}
        />
      )}

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}

function navCount(id, counts) {
  if (id === "cards") return counts.active.length;
  if (id === "fees") return counts.urgentFees;
  if (id === "bonuses") return counts.bonuses.length;
  if (id === "tags") return "";
  return null;
}

function NavButton({ item, page, setPage, count }) {
  const Icon = item.icon;
  return (
    <button className={`nav-item ${page === item.id ? "active" : ""}`} onClick={() => setPage(item.id)}>
      <Icon size={16} />
      <span>{item.label}</span>
      {count !== null && count !== "" && <span className="nav-count">{count}</span>}
    </button>
  );
}

function Router(props) {
  if (props.selected) return <Details {...props} />;
  if (props.page === "cards") return <CardsPage {...props} />;
  if (props.page === "bonuses") return <BonusesPage {...props} />;
  if (props.page === "fees") return <FeesPage {...props} />;
  if (props.page === "tags") return <TagsPage {...props} />;
  if (props.page === "settings") return <SettingsPage {...props} />;
  return <Overview {...props} />;
}

function Overview({ cards, hideLast4, setPage, setSelectedId, setEditing, mutate }) {
  const active = cards.filter((card) => card.status === "active");
  const cancelled = cards.filter((card) => card.status === "cancelled");
  const upcomingFees = active
    .map((card) => ({ card, days: daysUntilMonth(card.feeMonth), tone: feeTone(card) }))
    .filter((item) => item.days <= 60)
    .sort((a, b) => a.days - b.days);
  const activeBonuses = active.filter(isBonusActive);
  const ready = cancelled.filter((card) => card.dates?.reapply && new Date(card.dates.reapply) <= new Date());
  const totalFees = active.reduce((sum, card) => sum + Number(card.annualFee || 0), 0);
  const urgent = upcomingFees.filter((item) => item.days <= 30).length + activeBonuses.filter((card) => bonusProgress(card).days <= 30).length;

  return (
    <div className="content">
      <PageHeader title="Overview" sub={`${active.length} active cards · ${cancelled.length} cancelled · ${new Date().toLocaleDateString("en-GB", { dateStyle: "full" })}`}>
        <a className="btn" href="/api/export"><Download size={14} /> Export CSV</a>
        <button className="btn" onClick={() => mutate(api.backup, "Backup created")}><Archive size={14} /> Backup</button>
        <button className="btn primary" onClick={() => setEditing(emptyCard())}><Plus size={14} /> Add card</button>
      </PageHeader>

      <section className="metrics">
        <Metric label="Active cards" value={active.length} foot={`${new Set(active.map((card) => card.bank)).size} banks`} />
        <Metric label="Total annual fees" value={fmtMoneyShort(totalFees)} foot={`${active.filter((card) => card.annualFee > 0).length} fee-bearing`} />
        <Metric label="Due next 60 days" value={upcomingFees.length} foot={`${upcomingFees.filter((item) => item.days <= 30).length} due this month`} urgent />
        <Metric label="Bonuses in progress" value={activeBonuses.length} foot={`${cards.filter((card) => card.bonus?.status === "Met").length} met`} />
        <Metric label="Urgent deadlines" value={urgent} foot="need attention" urgent />
      </section>

      <section className="grid two">
        <Panel title="Annual fee alerts" sub="Charges in the next 60 days" action={<button className="link-btn" onClick={() => setPage("fees")}>View all <ChevronRight size={13} /></button>}>
          {upcomingFees.length ? upcomingFees.slice(0, 6).map(({ card, days, tone }) => (
            <CardRow key={card.id} card={card} hideLast4={hideLast4} compact onOpen={() => setSelectedId(card.id)}>
              <div className="money">{fmtMoney(card.annualFee)}</div>
              <span className={`pill ${tone}`}>{days}d</span>
            </CardRow>
          )) : <Empty>No fees due soon.</Empty>}
        </Panel>

        <Panel title="Re-apply ready" sub="Cancelled cards eligible again">
          {ready.length ? ready.map((card) => (
            <CardRow key={card.id} card={card} hideLast4 compact onOpen={() => setSelectedId(card.id)}>
              <button className="btn small" onClick={(event) => { event.stopPropagation(); setEditing({ ...card, id: undefined, status: "active", dates: {} }); }}>Re-add</button>
            </CardRow>
          )) : <Empty>Nothing eligible right now.</Empty>}
        </Panel>
      </section>

      <Panel title="Welcome bonus tracker" sub={`${activeBonuses.length} active bonus windows`}>
        {activeBonuses.length ? activeBonuses
          .sort((a, b) => (bonusProgress(a).days || 999) - (bonusProgress(b).days || 999))
          .map((card) => <BonusRow key={card.id} card={card} onOpen={() => setSelectedId(card.id)} />) : <Empty>No active minimum spend deadlines.</Empty>}
      </Panel>
    </div>
  );
}

function CardsPage({ cards, tags, query, showCancelled, hideLast4, setSelectedId, setEditing, mutate }) {
  const [bank, setBank] = useState("");
  const [tag, setTag] = useState("");
  const [sort, setSort] = useState("manual");
  const banks = [...new Set(cards.map((card) => card.bank).filter(Boolean))].sort();
  const visible = filterCards(cards, { query, showCancelled, bank, tag, sort });

  return (
    <div className="content">
      <PageHeader title="Cards" sub={`${visible.length} cards shown`}>
        <button className="btn primary" onClick={() => setEditing(emptyCard())}><Plus size={14} /> Add card</button>
      </PageHeader>
      <div className="filterbar">
        <Select value={bank} onChange={setBank} options={["", ...banks]} label="Bank" />
        <Select value={tag} onChange={setTag} options={["", ...tags]} label="Tag" />
        <Select value={sort} onChange={setSort} options={["manual", "due", "fee-desc", "fee-asc"]} label="Sort" />
      </div>
      <Panel flush>
        <div className="table-head">
          <span>Card</span><span>Annual fee</span><span>Fee month</span><span>Status</span><span></span>
        </div>
        {visible.map((card) => (
          <CardRow key={card.id} card={card} hideLast4={hideLast4} onOpen={() => setSelectedId(card.id)}>
            <div className="money">{fmtMoney(card.annualFee)}</div>
            <div className="mono">{card.feeMonth || "N/A"}</div>
            <Status card={card} />
            <RowActions card={card} setEditing={setEditing} mutate={mutate} />
          </CardRow>
        ))}
      </Panel>
    </div>
  );
}

function BonusesPage({ cards, setSelectedId, mutate }) {
  const bonuses = cards.filter((card) => card.bonus?.deadline);
  return (
    <div className="content">
      <PageHeader title="Bonuses" sub={`${bonuses.length} welcome offers tracked`} />
      <Panel title="Bonus progress">
        {bonuses.length ? bonuses.map((card) => (
          <BonusRow key={card.id} card={card} onOpen={() => setSelectedId(card.id)}>
            <button className="btn small" onClick={(event) => {
              event.stopPropagation();
              const amount = Number(prompt("Add spend amount"));
              if (amount > 0) mutate(() => api.addSpend(card.id, amount), "Spend updated");
            }}>Add spend</button>
          </BonusRow>
        )) : <Empty>No welcome bonuses recorded.</Empty>}
      </Panel>
    </div>
  );
}

function FeesPage({ cards, hideLast4, setSelectedId, mutate }) {
  const active = cards.filter((card) => card.status === "active");
  const byDue = active.map((card) => ({ card, days: daysUntilMonth(card.feeMonth) })).sort((a, b) => a.days - b.days);
  return (
    <div className="content">
      <PageHeader title="Annual fees" sub="Waiver and payment tracking" />
      <Panel title="Fee queue">
        {byDue.map(({ card, days }) => (
          <CardRow key={card.id} card={card} hideLast4={hideLast4} onOpen={() => setSelectedId(card.id)}>
            <div className="money">{fmtMoney(card.annualFee)}</div>
            <span className={`pill ${days <= 30 ? "rose" : days <= 60 ? "amber" : "teal"}`}>{days}d</span>
            <button className="btn small" onClick={(event) => { event.stopPropagation(); mutate(() => api.feeAction(card.id, "Waived"), "Marked waived"); }}>Waived</button>
            <button className="btn small" onClick={(event) => { event.stopPropagation(); mutate(() => api.feeAction(card.id, "Paid"), "Marked paid"); }}>Paid</button>
          </CardRow>
        ))}
      </Panel>
    </div>
  );
}

function TagsPage({ cards, tags, refresh, mutate }) {
  const [newTag, setNewTag] = useState("");
  const counts = Object.fromEntries(tags.map((tag) => [tag, cards.filter((card) => card.tags.includes(tag)).length]));
  return (
    <div className="content">
      <PageHeader title="Tags" sub="Manage card labels" />
      <Panel title="Existing tags">
        <div className="tag-grid">
          {tags.map((tag) => (
            <span className="tag-chip" key={tag}>{tag}<b>{counts[tag]}</b><button onClick={() => mutate(() => api.deleteTag(tag).then(refresh), "Tag deleted")}><Trash2 size={12} /></button></span>
          ))}
        </div>
        <div className="inline-form">
          <input value={newTag} onChange={(event) => setNewTag(event.target.value)} placeholder="New tag" />
          <button className="btn primary" onClick={() => {
            if (!newTag.trim()) return;
            mutate(() => api.saveTags([...tags, newTag.trim()]).then(refresh), "Tag added");
            setNewTag("");
          }}>Add tag</button>
        </div>
      </Panel>
    </div>
  );
}

function SettingsPage({ mutate }) {
  return (
    <div className="content">
      <PageHeader title="Settings" sub="Export, backups, and bot reference" />
      <section className="grid two">
        <Panel title="Data">
          <div className="setting-row"><span>Download CSV export</span><a className="btn" href="/api/export"><Download size={14} /> Export</a></div>
          <div className="setting-row"><span>Create local backup</span><button className="btn" onClick={() => mutate(api.backup, "Backup created")}><Archive size={14} /> Backup</button></div>
        </Panel>
        <Panel title="Telegram commands">
          <div className="command-list">
            {["/cards", "/info", "/fees", "/bonus", "/track", "/stats", "/backup", "/export"].map((cmd) => <code key={cmd}>{cmd}</code>)}
          </div>
        </Panel>
      </section>
    </div>
  );
}

function Details({ selected, hideLast4, setSelectedId, setEditing, mutate }) {
  const progress = bonusProgress(selected);
  return (
    <div className="content">
      <PageHeader title={`${selected.bank} ${selected.name}`} sub={selected.status === "cancelled" ? "Cancelled card" : "Active card"}>
        <button className="btn" onClick={() => setSelectedId(null)}>Back</button>
        <button className="btn primary" onClick={() => setEditing(selected)}><Pencil size={14} /> Edit</button>
      </PageHeader>
      <section className="detail-grid">
        <Panel>
          <CardArt card={selected} large hideLast4={hideLast4} />
          <div className="detail-actions">
            {selected.status === "cancelled" ? (
              <button className="btn" onClick={() => mutate(() => api.reactivateCard(selected.id), "Card reactivated")}>Reactivate</button>
            ) : (
              <button className="btn danger" onClick={() => window.confirm("Cancel this card?") && mutate(() => api.cancelCard(selected.id), "Card cancelled")}>Cancel card</button>
            )}
            <button className="btn danger" onClick={() => window.confirm("Permanently delete this card?") && mutate(() => api.deleteCard(selected.id), "Card deleted").then(() => setSelectedId(null))}>Delete</button>
          </div>
        </Panel>
        <Panel title="Card details">
          <dl className="details">
            <dt>Annual fee</dt><dd>{fmtMoney(selected.annualFee)}</dd>
            <dt>Fee month</dt><dd>{selected.feeMonth || "N/A"}</dd>
            <dt>Expiry</dt><dd>{selected.expiry || "N/A"}</dd>
            <dt>Last 4</dt><dd>{hideLast4 ? "••••" : selected.last4 || "N/A"}</dd>
            <dt>Tags</dt><dd>{selected.tags.length ? selected.tags.join(", ") : "N/A"}</dd>
            <dt>Notes</dt><dd>{selected.notes || "N/A"}</dd>
          </dl>
        </Panel>
        <Panel title="Welcome offer">
          <div className="bonus-name">{selected.bonus?.offer || "No offer recorded"}</div>
          <div className="progress"><span style={{ width: `${progress.percent}%` }} /></div>
          <div className="bonus-meta">{fmtMoney(selected.bonus?.currentSpend)} / {fmtMoney(selected.bonus?.minSpend)} · {progress.days ?? "N/A"} days left</div>
          <button className="btn small" onClick={() => {
            const amount = Number(prompt("Add spend amount"));
            if (amount > 0) mutate(() => api.addSpend(selected.id, amount), "Spend updated");
          }}>Add spend</button>
        </Panel>
        <Panel title="Timeline">
          <dl className="details">
            <dt>Applied</dt><dd>{fmtDate(selected.dates?.applied)}</dd>
            <dt>Approved</dt><dd>{fmtDate(selected.dates?.approved)}</dd>
            <dt>Received</dt><dd>{fmtDate(selected.dates?.received)}</dd>
            <dt>Activated</dt><dd>{fmtDate(selected.dates?.activated)}</dd>
            <dt>First charge</dt><dd>{fmtDate(selected.dates?.firstCharge)}</dd>
            <dt>Cancelled</dt><dd>{fmtDate(selected.dates?.cancelled)}</dd>
            <dt>Re-apply</dt><dd>{fmtDate(selected.dates?.reapply)}</dd>
          </dl>
        </Panel>
      </section>
    </div>
  );
}

function CardEditor({ card, tags, onClose, onSave }) {
  const [draft, setDraft] = useState(() => JSON.parse(JSON.stringify(card)));
  const [uploading, setUploading] = useState(false);
  const set = (path, value) => {
    setDraft((current) => {
      const next = { ...current, dates: { ...(current.dates || {}) }, bonus: { ...(current.bonus || {}) }, feeHistory: { ...(current.feeHistory || {}) } };
      if (path.includes(".")) {
        const [group, key] = path.split(".");
        next[group][key] = value;
      } else {
        next[path] = value;
      }
      return next;
    });
  };

  async function upload(file) {
    if (!file) return;
    setUploading(true);
    try {
      const result = await api.uploadImage(file);
      set("imageFilename", result.filename);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="scrim">
      <div className="drawer">
        <div className="drawer-head">
          <div><h2>{draft.id ? "Edit card" : "Add card"}</h2><p>Organized sections keep the card record complete.</p></div>
          <button className="icon-btn" onClick={onClose}>×</button>
        </div>
        <div className="drawer-body">
          <FormSection number="01" title="Card identity">
            <Input label="Bank" value={draft.bank} onChange={(value) => set("bank", value)} />
            <Input label="Card name" value={draft.name} onChange={(value) => set("name", value)} />
            <Input label="Last 4 digits" value={draft.last4} maxLength={4} onChange={(value) => set("last4", value.replace(/\D/g, ""))} />
            <Input label="Expiry MM/YY" value={draft.expiry} placeholder="05/27" onChange={(value) => set("expiry", value)} />
            <Input label="Annual fee" type="number" value={draft.annualFee} onChange={(value) => set("annualFee", Number(value))} />
            <label className="field"><span>Card image</span><input type="file" accept="image/png,image/jpeg" onChange={(event) => upload(event.target.files?.[0])} />{uploading && <small>Uploading...</small>}</label>
          </FormSection>
          <FormSection number="02" title="Tags and notes">
            <label className="field span"><span>Tags</span><select multiple value={draft.tags || []} onChange={(event) => set("tags", [...event.target.selectedOptions].map((option) => option.value))}>{tags.map((tag) => <option key={tag}>{tag}</option>)}</select></label>
            <label className="field span"><span>Notes</span><textarea value={draft.notes || ""} onChange={(event) => set("notes", event.target.value)} /></label>
          </FormSection>
          <FormSection number="03" title="Welcome offer">
            <Input label="Offer" value={draft.bonus?.offer} onChange={(value) => set("bonus.offer", value)} />
            <Input label="Min spend" type="number" value={draft.bonus?.minSpend} onChange={(value) => set("bonus.minSpend", Number(value))} />
            <Input label="Current spend" type="number" value={draft.bonus?.currentSpend} onChange={(value) => set("bonus.currentSpend", Number(value))} />
            <Input label="Deadline" type="date" value={draft.bonus?.deadline || ""} onChange={(value) => set("bonus.deadline", value)} />
            <label className="field"><span>Status</span><select value={draft.bonus?.status || "Not Started"} onChange={(event) => set("bonus.status", event.target.value)}>{["Not Started", "In Progress", "Met", "Received"].map((item) => <option key={item}>{item}</option>)}</select></label>
          </FormSection>
          <FormSection number="04" title="Dates">
            {[
              ["Applied", "dates.applied"],
              ["Approved", "dates.approved"],
              ["Received", "dates.received"],
              ["Activated", "dates.activated"],
              ["First charge", "dates.firstCharge"],
            ].map(([label, path]) => <Input key={path} label={label} type="date" value={path.split(".").reduce((obj, key) => obj?.[key], draft) || ""} onChange={(value) => set(path, value)} />)}
          </FormSection>
        </div>
        <div className="drawer-foot">
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn primary" onClick={() => onSave(draft)}>Save card</button>
        </div>
      </div>
    </div>
  );
}

function filterCards(cards, { query, showCancelled, bank, tag, sort }) {
  const q = query.trim().toLowerCase();
  let result = cards.filter((card) => showCancelled || card.status !== "cancelled");
  if (bank) result = result.filter((card) => card.bank === bank);
  if (tag) result = result.filter((card) => card.tags.includes(tag));
  if (q) result = result.filter((card) => [card.bank, card.name, card.notes, card.tags.join(" ")].join(" ").toLowerCase().includes(q));
  if (sort === "due") result = [...result].sort((a, b) => daysUntilMonth(a.feeMonth) - daysUntilMonth(b.feeMonth));
  else if (sort === "fee-desc") result = [...result].sort((a, b) => b.annualFee - a.annualFee);
  else if (sort === "fee-asc") result = [...result].sort((a, b) => a.annualFee - b.annualFee);
  else result = [...result].sort((a, b) => a.sortOrder - b.sortOrder);
  return result;
}

function PageHeader({ title, sub, children }) {
  return <div className="page-header"><div><h1>{title}</h1><p>{sub}</p></div><div className="actions">{children}</div></div>;
}

function Metric({ label, value, foot, urgent }) {
  return <div className={`metric ${urgent ? "urgent" : ""}`}><span>{label}</span><strong>{value}</strong><small>{foot}</small></div>;
}

function Panel({ title, sub, action, children, flush }) {
  return <section className={`panel ${flush ? "flush" : ""}`}>{title && <header><div><h3>{title}</h3>{sub && <p>{sub}</p>}</div>{action}</header>}<div className="panel-body">{children}</div></section>;
}

function Empty({ children }) {
  return <div className="empty">{children}</div>;
}

function Select({ label, value, onChange, options }) {
  return <label className="select-field"><span>{label}</span><select value={value} onChange={(event) => onChange(event.target.value)}>{options.map((option) => <option key={option} value={option}>{option || "All"}</option>)}</select></label>;
}

function Input({ label, value, onChange, ...props }) {
  return <label className="field"><span>{label}</span><input value={value ?? ""} onChange={(event) => onChange(event.target.value)} {...props} /></label>;
}

function FormSection({ number, title, children }) {
  return <section className="form-section"><h3><span>{number}</span>{title}</h3><div className="form-grid">{children}</div></section>;
}

function CardRow({ card, hideLast4, onOpen, compact, children }) {
  return (
    <div className={`card-row ${compact ? "compact" : ""}`} onClick={onOpen}>
      <CardArt card={card} />
      <div className="card-main">
        <strong>{card.name}</strong>
        <span>{card.bank} · <code>{hideLast4 ? "••••" : card.last4 || "no last 4"}</code></span>
        {!!card.tags.length && <div className="chips">{card.tags.map((tag) => <em key={tag}>{tag}</em>)}</div>}
      </div>
      {children}
    </div>
  );
}

function CardArt({ card, large, hideLast4 }) {
  const [from, to] = bankColor(card.bank);
  return (
    <div className={`card-art ${large ? "large" : ""}`} style={{ background: `linear-gradient(135deg, ${from}, ${to})` }}>
      {large ? (
        <>
          <span>{card.bank}</span>
          <b>{hideLast4 ? "•••• •••• •••• ••••" : `•••• •••• •••• ${card.last4 || "0000"}`}</b>
          <strong>{card.name}</strong>
        </>
      ) : null}
    </div>
  );
}

function Status({ card }) {
  if (card.status === "cancelled") return <span className="pill muted">Cancelled</span>;
  const tone = feeTone(card);
  const days = daysUntilMonth(card.feeMonth);
  return <span className={`pill ${tone}`}>{days <= 30 ? "Due this month" : days <= 60 ? "Due next month" : "Active"}</span>;
}

function RowActions({ card, setEditing, mutate }) {
  return (
    <div className="row-actions" onClick={(event) => event.stopPropagation()}>
      <button className="icon-btn" title="Edit" onClick={() => setEditing(card)}><Pencil size={15} /></button>
      {card.status === "cancelled" ? (
        <button className="icon-btn" title="Reactivate" onClick={() => mutate(() => api.reactivateCard(card.id), "Card reactivated")}><RefreshCcw size={15} /></button>
      ) : (
        <button className="icon-btn" title="Cancel" onClick={() => window.confirm("Cancel this card?") && mutate(() => api.cancelCard(card.id), "Card cancelled")}><Archive size={15} /></button>
      )}
      <button className="icon-btn danger" title="Delete" onClick={() => window.confirm("Permanently delete this card?") && mutate(() => api.deleteCard(card.id), "Card deleted")}><Trash2 size={15} /></button>
    </div>
  );
}

function BonusRow({ card, onOpen, children }) {
  const progress = bonusProgress(card);
  const tone = progress.days !== null && progress.days <= 30 ? "rose" : progress.days !== null && progress.days <= 90 ? "amber" : "teal";
  return (
    <div className="bonus-row" onClick={onOpen}>
      <CardArt card={card} />
      <div>
        <strong>{card.name}<span>{card.bonus?.offer ? ` · ${card.bonus.offer}` : ""}</span></strong>
        <div className="bonus-meta"><span className={`pill ${tone}`}>{progress.days ?? "N/A"}d</span><span>{fmtMoney(card.bonus?.currentSpend)} / {fmtMoney(card.bonus?.minSpend)}</span><span>{fmtMoney(progress.remaining)} left</span></div>
        <div className="progress"><span style={{ width: `${progress.percent}%` }} /></div>
      </div>
      {children}
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
