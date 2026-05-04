import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AlertTriangle,
  Archive,
  Bell,
  CalendarClock,
  Check,
  CheckCircle2,
  ChevronRight,
  Download,
  Eye,
  EyeOff,
  GripVertical,
  Home,
  ListOrdered,
  MessageCircle,
  Moon,
  Pencil,
  Plus,
  RefreshCcw,
  Search,
  Send,
  Settings,
  Sun,
  Tag,
  Trash2,
  WalletCards,
  XCircle,
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
} from "./utils";
import "./styles.css";

const nav = [
  { id: "overview",      label: "Overview",       icon: Home },
  { id: "cards",         label: "Cards",           icon: WalletCards },
  { id: "bonuses",       label: "Bonuses",         icon: Check },
  { id: "fees",          label: "Fees",            icon: CalendarClock },
  { id: "sort",          label: "Sort order",      icon: ListOrdered },
  { id: "tags",          label: "Tags",            icon: Tag },
  { id: "notifications", label: "Notifications",   icon: MessageCircle },
  { id: "settings",      label: "Settings",        icon: Settings },
];

function App() {
  const [cards, setCards]         = useState([]);
  const [tags, setTags]           = useState([]);
  const [page, setPage]           = useState("overview");
  const [selectedId, setSelectedId] = useState(null);
  const [editing, setEditing]     = useState(null);
  const [query, setQuery]         = useState("");
  const [showCancelled, setShowCancelled] = useState(true);
  const [hideLast4, setHideLast4] = useState(false);
  const [theme, setTheme]         = useState(() => localStorage.getItem("card-tracker-theme") || "light");
  const [density, setDensity]     = useState(() => localStorage.getItem("card-tracker-density") || "comfortable");
  const [loading, setLoading]     = useState(true);
  const [toast, setToast]         = useState("");
  const [diagData, setDiagData]   = useState(null);
  const [botStatus, setBotStatus] = useState(null);

  async function refresh() {
    const [nextCards, nextTags, nextDiag] = await Promise.all([
      api.cards(),
      api.tags(),
      api.diagnostics().catch(() => null),
    ]);
    setCards(nextCards);
    setTags(nextTags);
    setDiagData(nextDiag);
    setLoading(false);
    api.botStatus().then(setBotStatus).catch(() => setBotStatus(null));
  }

  useEffect(() => {
    refresh().catch((err) => { setToast(err.message); setLoading(false); });
  }, []);

  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(""), 2800);
    return () => clearTimeout(id);
  }, [toast]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("card-tracker-theme", theme);
  }, [theme]);

  useEffect(() => {
    document.documentElement.dataset.density = density;
    localStorage.setItem("card-tracker-density", density);
  }, [density]);

  const selected = cards.find((c) => c.id === selectedId);

  async function mutate(fn, message) {
    try {
      const next = await fn();
      if (Array.isArray(next)) setCards(next);
      else await refresh();
      if (message) setToast(message);
    } catch (err) {
      setToast(err.message);
    }
  }

  const counts = useMemo(() => {
    const active    = cards.filter((c) => c.status === "active");
    const cancelled = cards.filter((c) => c.status === "cancelled");
    const urgentFees = active.filter((c) => daysUntilMonth(c.feeMonth) <= 30).length;
    const bonuses    = active.filter(isBonusActive);
    return { active, cancelled, urgentFees, bonuses };
  }, [cards]);

  function navigate(p) { setSelectedId(null); setPage(p); }
  function openCard(id) { setSelectedId(id); setPage("details"); }

  return (
    <div className="app">
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <button className="sidebar-brand" onClick={() => navigate("overview")} title="Go to overview">
          <div className="mark">CC</div>
          <div>
            <div className="name">Card Tracker</div>
            <div className="sub">Private finance console</div>
          </div>
        </button>

        <div className="nav-group">
          <div className="nav-label">Tracking</div>
          {nav.slice(0, 4).map((item) => (
            <NavButton key={item.id} item={item} page={page} setPage={navigate} count={navCount(item.id, counts)} />
          ))}
        </div>
        <div className="nav-group">
          <div className="nav-label">Manage</div>
          {nav.slice(4).map((item) => (
            <NavButton key={item.id} item={item} page={page} setPage={navigate} count={navCount(item.id, counts)} />
          ))}
        </div>

        <div className="sidebar-footer">
          <div className="footer-vault">
            <div>
              <div style={{ fontSize: 12, fontWeight: 600 }}>Local vault</div>
              <div className="footer-vault-counts">{counts.active.length} active · {counts.cancelled.length} cancelled</div>
            </div>
            <button className="icon-btn" title="Toggle theme" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
              {theme === "dark" ? <Sun size={14} /> : <Moon size={14} />}
            </button>
          </div>
          <div className="footer-toggle">
            <span>Hide last 4</span>
            <Toggle checked={hideLast4} onChange={setHideLast4} />
          </div>
          <div className="footer-toggle">
            <span>Show cancelled</span>
            <Toggle checked={showCancelled} onChange={setShowCancelled} />
          </div>
          <div className="footer-toggle">
            <span>Compact density</span>
            <Toggle checked={density === "compact"} onChange={(v) => setDensity(v ? "compact" : "comfortable")} />
          </div>
        </div>
      </aside>

      {/* ── Main ── */}
      <main className="main">
        <header className="topbar">
          <div className="crumbs">
            Dashboard / <span className="here">{nav.find((n) => n.id === page)?.label}</span>
          </div>
          <div className="topbar-right">
            <div className="search">
              <Search size={14} />
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search cards, banks, tags…" />
            </div>
            <button className="btn primary" onClick={() => setEditing(emptyCard())}>
              <Plus size={14} /> Add card
            </button>
            <button className="icon-btn" title="Toggle theme" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
              {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
            </button>
          </div>
        </header>

        {loading ? (
          <div className="content"><div className="panel empty">Loading tracker…</div></div>
        ) : (
          <Router
            page={page}
            cards={cards}
            tags={tags}
            query={query}
            showCancelled={showCancelled}
            hideLast4={hideLast4}
            theme={theme}
            density={density}
            diagData={diagData}
            botStatus={botStatus}
            setTheme={setTheme}
            setDensity={setDensity}
            setHideLast4={setHideLast4}
            selected={selected}
            setPage={navigate}
            setSelectedId={openCard}
            closeDetails={() => { setSelectedId(null); setPage("cards"); }}
            setEditing={setEditing}
            mutate={mutate}
            refresh={refresh}
          />
        )}
      </main>

      {/* ── Card editor drawer ── */}
      {editing && (
        <CardEditor
          card={editing}
          tags={tags}
          onClose={() => setEditing(null)}
          onSave={(payload) =>
            mutate(
              () => payload.id ? api.updateCard(payload.id, payload) : api.createCard(payload),
              payload.id ? "Card updated" : "Card added"
            ).then(() => setEditing(null))
          }
        />
      )}

      {toast && <div className="toast show">{toast}</div>}
    </div>
  );
}

/* ── Toggle switch ── */
function Toggle({ checked, onChange }) {
  return (
    <button
      className={`toggle ${checked ? "on" : ""}`}
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
    />
  );
}

/* ── Nav helpers ── */
function navCount(id, counts) {
  if (id === "cards")         return counts.active.length;
  if (id === "fees")          return counts.urgentFees;
  if (id === "bonuses")       return counts.bonuses.length;
  if (id === "sort")          return counts.active.length;
  if (id === "notifications") return counts.urgentFees + counts.bonuses.length;
  if (id === "tags")          return "";
  return null;
}

function NavButton({ item, page, setPage, count }) {
  const Icon = item.icon;
  return (
    <button className={`nav-item ${page === item.id ? "active" : ""}`} onClick={() => setPage(item.id)}>
      <span className="nav-icon"><Icon size={15} /></span>
      <span>{item.label}</span>
      {count !== null && count !== "" && <span className="nav-count">{count}</span>}
    </button>
  );
}

/* ── Router ── */
function Router(props) {
  if (props.page === "details" && props.selected) return <Details {...props} />;
  if (props.page === "cards")     return <CardsPage {...props} />;
  if (props.page === "bonuses")   return <BonusesPage {...props} />;
  if (props.page === "fees")      return <FeesPage {...props} />;
  if (props.page === "sort")      return <SortPage {...props} />;
  if (props.page === "tags")      return <TagsPage {...props} />;
  if (props.page === "notifications") return <NotificationsPage {...props} />;
  if (props.page === "settings")  return <SettingsPage {...props} />;
  return <Overview {...props} />;
}

/* ── Overview ── */
function Overview({ cards, hideLast4, diagData, setPage, setSelectedId, setEditing, mutate }) {
  const active    = cards.filter((c) => c.status === "active");
  const cancelled = cards.filter((c) => c.status === "cancelled");
  const upcomingFees = active
    .map((c) => ({ card: c, days: daysUntilMonth(c.feeMonth), tone: feeTone(c) }))
    .filter((x) => x.days <= 60)
    .sort((a, b) => a.days - b.days);
  const activeBonuses = active.filter(isBonusActive);
  const ready      = cancelled.filter((c) => c.dates?.reapply && new Date(c.dates.reapply) <= new Date());
  const totalFees  = active.reduce((s, c) => s + Number(c.annualFee || 0), 0);
  const urgent     = upcomingFees.filter((x) => x.days <= 30).length +
                     activeBonuses.filter((c) => bonusProgress(c).days <= 30).length;
  const calendar   = MONTHS.map((month) => {
    const due = active.filter((c) => c.feeMonth === month);
    return { month, count: due.length, total: due.reduce((s, c) => s + Number(c.annualFee || 0), 0) };
  });

  return (
    <div className="content">
      <PageHeader
        title="Overview"
        sub={`${active.length} active · ${cancelled.length} cancelled · ${new Date().toLocaleDateString("en-GB", { dateStyle: "full" })}`}
      >
        <a className="btn" href="/api/export"><Download size={14} /> Export CSV</a>
        <button className="btn" onClick={() => mutate(api.backup, "Backup created")}><Archive size={14} /> Backup</button>
        <button className="btn primary" onClick={() => setEditing(emptyCard())}><Plus size={14} /> Add card</button>
      </PageHeader>

      {diagData?.counts.issues > 0 && (
        <button className="diag-bar" onClick={() => setPage("settings")}>
          <AlertTriangle size={14} />
          <span>{diagData.counts.issues} data health issue{diagData.counts.issues !== 1 ? "s" : ""} detected</span>
          <ChevronRight size={13} />
        </button>
      )}

      <section className="metrics">
        <Metric label="Active cards"       value={active.length}            foot={`${new Set(active.map((c) => c.bank)).size} banks`} />
        <Metric label="Total annual fees"  value={fmtMoneyShort(totalFees)} foot={`${active.filter((c) => c.annualFee > 0).length} fee-bearing`} />
        <Metric label="Due next 60 days"   value={upcomingFees.length}      foot={`${upcomingFees.filter((x) => x.days <= 30).length} due this month`} urgent />
        <Metric label="Bonuses in progress" value={activeBonuses.length}    foot={`${cards.filter((c) => c.bonus?.status === "Met").length} met`} />
        <Metric label="Urgent deadlines"   value={urgent}                   foot="need attention" urgent />
      </section>

      <section className="grid two">
        <Panel
          title="Annual fee alerts"
          sub="Charges in the next 60 days"
          action={<button className="link-btn" onClick={() => setPage("fees")}>View all <ChevronRight size={13} /></button>}
        >
          {upcomingFees.length
            ? upcomingFees.slice(0, 6).map(({ card, days, tone }) => (
                <CardRow key={card.id} card={card} hideLast4={hideLast4} compact onOpen={() => setSelectedId(card.id)}>
                  <div className="money">{fmtMoney(card.annualFee)}</div>
                  <span className={`pill ${tone}`}>{days}d</span>
                </CardRow>
              ))
            : <Empty>No fees due soon.</Empty>}
        </Panel>

        <Panel title="Re-apply ready" sub="Cancelled cards eligible again">
          {ready.length
            ? ready.map((card) => (
                <CardRow key={card.id} card={card} hideLast4 compact onOpen={() => setSelectedId(card.id)}>
                  <button
                    className="btn small"
                    onClick={(e) => { e.stopPropagation(); setEditing({ ...card, id: undefined, status: "active", dates: {} }); }}
                  >Re-add</button>
                </CardRow>
              ))
            : <Empty>Nothing eligible right now.</Empty>}
        </Panel>
      </section>

      <Panel title="12-month fee calendar" sub="Annual fee density by month">
        <div className="calendar-strip">
          {calendar.map(({ month, count, total }) => (
            <button key={month} className={`month-cell ${count ? "has-fees" : ""}`} onClick={() => setPage("fees")}>
              <span>{month.slice(0, 3)}</span>
              <strong>{count}</strong>
              <small>{total ? fmtMoneyShort(total) : "—"}</small>
            </button>
          ))}
        </div>
      </Panel>

      <Panel title="Welcome bonus tracker" sub={`${activeBonuses.length} active bonus windows`}>
        {activeBonuses.length
          ? activeBonuses
              .sort((a, b) => (bonusProgress(a).days || 999) - (bonusProgress(b).days || 999))
              .map((card) => <BonusRow key={card.id} card={card} onOpen={() => setSelectedId(card.id)} />)
          : <Empty>No active minimum spend deadlines.</Empty>}
      </Panel>
    </div>
  );
}

/* ── Cards page ── */
function CardsPage({ cards, tags, query, showCancelled, hideLast4, setSelectedId, setEditing, mutate }) {
  const [bank, setBank] = useState("");
  const [tag, setTag]   = useState("");
  const [sort, setSort] = useState("manual");
  const [status, setStatus] = useState("active");
  const banks   = [...new Set(cards.map((c) => c.bank).filter(Boolean))].sort();
  const visible = filterCards(cards, { query, showCancelled, bank, tag, sort, status });
  const hasFilters = bank || tag || status !== "active" || query;

  return (
    <div className="content">
      <PageHeader title="Cards" sub={`${visible.length} of ${cards.length} cards shown`}>
        <button className="btn primary" onClick={() => setEditing(emptyCard())}><Plus size={14} /> Add card</button>
      </PageHeader>

      <div className="filterbar">
        <span className="filterbar-label">Status</span>
        <div className="segmented">
          {["active", "cancelled", "all"].map((item) => (
            <button key={item} className={status === item ? "active" : ""} onClick={() => setStatus(item)}>
              {item[0].toUpperCase() + item.slice(1)}
            </button>
          ))}
        </div>
        <div className="filterbar-sep" />
        <span className="filterbar-label">Bank</span>
        <select className="select" value={bank} onChange={(e) => setBank(e.target.value)}>
          <option value="">All banks</option>
          {banks.map((b) => <option key={b} value={b}>{b}</option>)}
        </select>
        <span className="filterbar-label">Tag</span>
        <select className="select" value={tag} onChange={(e) => setTag(e.target.value)}>
          <option value="">All tags</option>
          {tags.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <div className="filterbar-spacer" />
        <div className="filterbar-sep" />
        <span className="filterbar-label">Sort</span>
        <select className="select" value={sort} onChange={(e) => setSort(e.target.value)}>
          <option value="manual">Manual</option>
          <option value="due">Fee due date</option>
          <option value="fee-desc">Fee ↓</option>
          <option value="fee-asc">Fee ↑</option>
          <option value="bank">Bank</option>
        </select>
        {hasFilters && (
          <button className="btn small" onClick={() => { setBank(""); setTag(""); setStatus("active"); }}>
            Clear
          </button>
        )}
      </div>

      <Panel flush>
        <div className="table-head">
          <span>Card</span><span>Annual fee</span><span>Fee month</span><span>Status</span><span />
        </div>
        {visible.map((card) => (
          <CardRow key={card.id} card={card} hideLast4={hideLast4} onOpen={() => setSelectedId(card.id)}>
            <div className="money">{fmtMoney(card.annualFee)}</div>
            <div className="mono">{card.feeMonth || "N/A"}</div>
            <Status card={card} />
            <RowActions card={card} setEditing={setEditing} mutate={mutate} />
          </CardRow>
        ))}
        {visible.length === 0 && <Empty>No cards match your filters.</Empty>}
      </Panel>
    </div>
  );
}

/* ── Bonuses page ── */
function BonusesPage({ cards, setSelectedId, mutate }) {
  const bonuses = cards.filter((c) => c.bonus?.deadline);
  return (
    <div className="content">
      <PageHeader title="Bonuses" sub={`${bonuses.length} welcome offers tracked`} />
      <Panel title="Bonus progress">
        {bonuses.length
          ? bonuses.map((card) => (
              <BonusRow key={card.id} card={card} onOpen={() => setSelectedId(card.id)}>
                <button
                  className="btn small"
                  onClick={(e) => {
                    e.stopPropagation();
                    const amount = Number(prompt("Add spend amount"));
                    if (amount > 0) mutate(() => api.addSpend(card.id, amount), "Spend updated");
                  }}
                >Add spend</button>
              </BonusRow>
            ))
          : <Empty>No welcome bonuses recorded.</Empty>}
      </Panel>
    </div>
  );
}

/* ── Fees page ── */
function FeesPage({ cards, hideLast4, setSelectedId, mutate }) {
  const active = cards.filter((c) => c.status === "active");
  const byDue  = active.map((c) => ({ card: c, days: daysUntilMonth(c.feeMonth) })).sort((a, b) => a.days - b.days);
  return (
    <div className="content">
      <PageHeader title="Annual fees" sub="Waiver and payment tracking" />
      <Panel title="Fee queue">
        {byDue.map(({ card, days }) => (
          <CardRow key={card.id} card={card} hideLast4={hideLast4} compact onOpen={() => setSelectedId(card.id)}>
            <div className="money">{fmtMoney(card.annualFee)}</div>
            <span className={`pill ${days <= 30 ? "rose" : days <= 60 ? "amber" : "teal"}`}>{days}d</span>
            <button className="btn small fee-action" onClick={(e) => { e.stopPropagation(); mutate(() => api.feeAction(card.id, "Waived"), "Marked waived"); }}>Waived</button>
            <button className="btn small fee-action" onClick={(e) => { e.stopPropagation(); mutate(() => api.feeAction(card.id, "Paid"),   "Marked paid");   }}>Paid</button>
          </CardRow>
        ))}
        {byDue.length === 0 && <Empty>No active cards with fees.</Empty>}
      </Panel>
    </div>
  );
}

/* ── Tags page ── */
function TagsPage({ cards, tags, refresh, mutate }) {
  const [newTag, setNewTag] = useState("");
  const counts = Object.fromEntries(tags.map((t) => [t, cards.filter((c) => c.tags.includes(t)).length]));
  const cardsByTag = Object.fromEntries(tags.map((t) => [t, cards.filter((c) => c.tags.includes(t))]));

  function addTag() {
    if (!newTag.trim()) return;
    mutate(() => api.saveTags([...tags, newTag.trim()]).then(refresh), "Tag added");
    setNewTag("");
  }

  return (
    <div className="content">
      <PageHeader title="Tags" sub="Organize cards by purpose, perks, or strategy" />
      <section className="grid two tags-top">
        <Panel title={<>All tags <span className="panel-count">{tags.length}</span></>}>
          <div className="tag-grid rich">
            {tags.map((t) => (
              <span className={`tag-chip ${tagTone(t)}`} key={t}>
                {t}<b>{counts[t]}</b>
                <button title={`Delete ${t}`} onClick={() => mutate(() => api.deleteTag(t).then(refresh), "Tag deleted")}><Trash2 size={12} /></button>
              </span>
            ))}
            {tags.length === 0 && <span className="muted-note">No tags yet.</span>}
          </div>
        </Panel>
        <Panel title="Add tag">
          <div className="inline-form compact">
            <input
              value={newTag}
              onChange={(e) => setNewTag(e.target.value)}
              placeholder="e.g. Groceries"
              onKeyDown={(e) => e.key === "Enter" && addTag()}
            />
            <button className="btn primary" onClick={addTag}><Plus size={14} /> Add</button>
          </div>
          <p className="helper-copy">Tags appear as filters on the Cards list and as labels on each card. Removing a tag also strips it from all cards using it.</p>
        </Panel>
      </section>

      <Panel title="Cards per tag">
        <div className="tag-card-list">
          {tags.map((t) => {
            const matching = cardsByTag[t] || [];
            return (
              <div className="tag-card-row" key={t}>
                <span className={`tag-chip ${tagTone(t)}`}>{t}</span>
                <span className="tag-count">{matching.length} card{matching.length === 1 ? "" : "s"}</span>
                <div className="tag-card-names">
                  {matching.slice(0, 6).map((card) => <span key={card.id}>{card.name}</span>)}
                  {matching.length > 6 && <span>+{matching.length - 6}</span>}
                  {matching.length === 0 && <em>No cards</em>}
                </div>
              </div>
            );
          })}
        </div>
      </Panel>
    </div>
  );
}

function tagTone(tag) {
  const tones = ["teal", "emerald", "amber", "rose", "muted"];
  return tones[Math.abs([...tag].reduce((sum, char) => sum + char.charCodeAt(0), 0)) % tones.length];
}

/* ── Sort page ── */
function SortPage({ cards, hideLast4, setSelectedId, mutate }) {
  const active = cards.filter((c) => c.status === "active").sort((a, b) => a.sortOrder - b.sortOrder);
  const [orders, setOrders] = useState(() =>
    Object.fromEntries(active.map((c, i) => [c.id, c.sortOrder || i + 1]))
  );

  useEffect(() => {
    setOrders(Object.fromEntries(active.map((c, i) => [c.id, c.sortOrder || i + 1])));
  }, [cards.length]);

  const values     = Object.values(orders).map(Number).filter(Boolean);
  const duplicates = values.filter((v, i) => values.indexOf(v) !== i);

  function renumber() {
    setOrders(Object.fromEntries(active.map((c, i) => [c.id, i + 1])));
  }

  function bump(id, delta) {
    const sorted = active
      .map((c) => ({ id: c.id, order: Number(orders[c.id] || c.sortOrder || 99) }))
      .sort((a, b) => a.order - b.order);
    const idx = sorted.findIndex((x) => x.id === id);
    const swap = idx + delta;
    if (swap < 0 || swap >= sorted.length) return;
    [sorted[idx], sorted[swap]] = [sorted[swap], sorted[idx]];
    setOrders(Object.fromEntries(sorted.map((x, i) => [x.id, i + 1])));
  }

  return (
    <div className="content">
      <PageHeader title="Sort order" sub="Manual order for card list and bot responses">
        {duplicates.length > 0 && <span className="pill rose">Duplicate order values</span>}
        <button className="btn" onClick={renumber}><ListOrdered size={14} /> Renumber</button>
        <button className="btn primary" onClick={() => mutate(() => api.sortOrder(orders), "Sort order saved")}>Save order</button>
      </PageHeader>
      <Panel title="Active cards" sub="Use arrows or type an order number">
        {active.map((card, i) => (
          <div className="sort-row" key={card.id}>
            <GripVertical size={15} />
            <CardRow card={card} hideLast4={hideLast4} compact onOpen={() => setSelectedId(card.id)}>
              <button className="btn small" disabled={i === 0}              onClick={(e) => { e.stopPropagation(); bump(card.id, -1); }}>↑</button>
              <button className="btn small" disabled={i === active.length - 1} onClick={(e) => { e.stopPropagation(); bump(card.id,  1); }}>↓</button>
            </CardRow>
            <input
              className={`order-input ${duplicates.includes(Number(orders[card.id])) ? "duplicate" : ""}`}
              type="number"
              min="1"
              value={orders[card.id] || ""}
              onChange={(e) => setOrders({ ...orders, [card.id]: Number(e.target.value) })}
            />
          </div>
        ))}
      </Panel>
    </div>
  );
}

/* ── Notifications page ── */
function NotificationsPage({ cards, hideLast4, setSelectedId, botStatus, mutate }) {
  const [feedFilter, setFeedFilter] = useState("all");
  const active = cards.filter((c) => c.status === "active");
  const events = [
    ...active
      .map((c) => ({ card: c, type: "Annual fee", days: daysUntilMonth(c.feeMonth), tone: feeTone(c), detail: `${fmtMoney(c.annualFee)} due in ${c.feeMonth || "N/A"}` }))
      .filter((e) => e.days <= 60),
    ...active
      .filter(isBonusActive)
      .map((c) => ({
        card: c,
        type: "Welcome bonus",
        days: bonusProgress(c).days ?? 999,
        tone: (bonusProgress(c).days ?? 999) <= 30 ? "rose" : "amber",
        detail: `${fmtMoney(bonusProgress(c).remaining)} remaining`,
      })),
  ].sort((a, b) => a.days - b.days);
  const activity = buildActivityFeed(cards);
  const filteredActivity = feedFilter === "all" ? activity : activity.filter((item) => item.kind === feedFilter);
  const connected = !!botStatus?.connected;

  return (
    <div className="content">
      <PageHeader title="Notifications" sub={`${activity.filter((item) => !item.read).length} unread · delivered via Telegram bot`}>
        <button className="btn" onClick={() => mutate(() => api.testBot(), "Telegram test message sent")}>
          <Send size={14} /> Test connection
        </button>
      </PageHeader>
      <section className="grid two">
        <Panel
          title="Activity feed"
          action={
            <div className="feed-filters">
              {["all", "fee", "bonus", "reapply"].map((item) => (
                <button key={item} className={feedFilter === item ? "active" : ""} onClick={() => setFeedFilter(item)}>
                  {item === "all" ? "All" : item[0].toUpperCase() + item.slice(1)}
                </button>
              ))}
            </div>
          }
        >
          <div className="activity-list">
            {filteredActivity.map((item) => (
              <div className={`activity-row ${item.read ? "" : "unread"}`} key={item.id}>
                <CardArt card={item.card} />
                <div>
                  <div className="activity-meta">
                    <span className={`pill ${item.tone}`}>{item.label}</span>
                    {!item.read && <span className="unread-dot" />}
                    <span className="mono">{item.when}</span>
                  </div>
                  <div className="activity-message">{item.message}</div>
                </div>
                {item.read ? <Eye size={14} /> : <Check size={14} />}
              </div>
            ))}
          </div>
        </Panel>

        <div className="notification-side">
          <Panel
            title={<><MessageCircle size={14} /> Telegram bot</>}
            action={<span className={`pill ${connected ? "emerald" : "muted"}`}>{connected ? <CheckCircle2 size={12} /> : <XCircle size={12} />}{connected ? "Connected" : "Disconnected"}</span>}
          >
            <div className="bot-details">
              <div><span>Username</span><strong className="mono">{botStatus?.username || "Unknown"}</strong></div>
              <div><span>Chat ID</span><strong className="mono">{botStatus?.chatId || "Not configured"}</strong></div>
              <div><span>RUN_BOT</span><strong className="mono">{botStatus?.runBot || "auto"}</strong></div>
              <div><span>Required</span><strong className="mono">{botStatus?.botRequired || "false"}</strong></div>
            </div>
            {botStatus?.error && <div className="bot-error">{botStatus.error}</div>}
            <button className="btn primary full" onClick={() => mutate(() => api.testBot(), "Telegram test message sent")}>
              <Send size={14} /> Send test message
            </button>
          </Panel>

          <Panel title="Daily digest">
            {[
              ["Fees due ≤30 days", true],
              ["Bonuses ≤30 days", true],
              ["Re-apply eligible", true],
              ["Card expiry ≤60 days", false],
              ["Bonus progress weekly", false],
            ].map(([label, on]) => (
              <div className="digest-row" key={label}>
                <span>{label}</span>
                <Toggle checked={on} onChange={() => {}} />
              </div>
            ))}
          </Panel>

          <Panel title="Bot commands">
            <div className="command-list stacked">
              {[
                ["/fees", "list upcoming fees"],
                ["/bonus", "bonuses in progress"],
                ["/cards", "list active cards"],
                ["/info", "card details"],
                ["/backup", "create backup"],
              ].map(([cmd, label]) => (
                <div key={cmd}><code>{cmd}</code><span>{label}</span></div>
              ))}
            </div>
          </Panel>
        </div>

        <Panel title="Upcoming notification queue" sub={`${events.length} reminders from real card data`}>
          <div className="queue-list">
            {events.length
              ? events.map((event) => (
                  <button key={`${event.type}-${event.card.id}`} className="queue-row" onClick={() => setSelectedId(event.card.id)}>
                    <CardArt card={event.card} />
                    <div>
                      <strong>{event.card.name}</strong>
                      <span>{event.type} · {event.detail}</span>
                    </div>
                    <span className={`pill ${event.tone}`}>{event.days}d</span>
                  </button>
                ))
              : <Empty>No notifications due in the next 60 days.</Empty>}
          </div>
        </Panel>
      </section>
    </div>
  );
}

function buildActivityFeed(cards) {
  const active = cards.filter((card) => card.status === "active");
  const cancelled = cards.filter((card) => card.status === "cancelled");
  return [
    ...active
      .map((card) => ({ card, days: daysUntilMonth(card.feeMonth) }))
      .filter((item) => item.days <= 60)
      .map(({ card, days }) => ({
        id: `fee-${card.id}`,
        card,
        kind: "fee",
        label: "Fee",
        tone: days <= 30 ? "rose" : "amber",
        when: `${days}d`,
        read: days > 30,
        message: `${card.name} annual fee ${fmtMoney(card.annualFee)} is due in ${card.feeMonth || "N/A"}.`,
      })),
    ...active
      .filter(isBonusActive)
      .map((card) => {
        const progress = bonusProgress(card);
        return {
          id: `bonus-${card.id}`,
          card,
          kind: "bonus",
          label: "Bonus",
          tone: (progress.days ?? 999) <= 30 ? "rose" : "amber",
          when: `${progress.days ?? "N/A"}d`,
          read: (progress.days ?? 999) > 30,
          message: `${card.name} has ${fmtMoney(progress.remaining)} remaining for its welcome offer.`,
        };
      }),
    ...cancelled
      .filter((card) => card.dates?.reapply && new Date(card.dates.reapply) <= new Date())
      .map((card) => ({
        id: `reapply-${card.id}`,
        card,
        kind: "reapply",
        label: "Re-apply",
        tone: "emerald",
        when: "ready",
        read: false,
        message: `${card.name} is eligible to re-apply.`,
      })),
  ];
}

/* ── Settings page ── */
function SettingsPage({ mutate, theme, density, hideLast4, setTheme, setDensity, setHideLast4, diagData }) {
  return (
    <div className="content">
      <PageHeader title="Settings" sub="Display preferences, data export, and health" />
      <section className="grid two">
        <Panel title="Display">
          <div className="setting-row">
            <span>Theme</span>
            <button className="btn" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
              {theme === "dark" ? <><Sun size={14} /> Dark</> : <><Moon size={14} /> Light</>}
            </button>
          </div>
          <div className="setting-row">
            <span>Privacy</span>
            <button className="btn" onClick={() => setHideLast4(!hideLast4)}>
              {hideLast4 ? <><EyeOff size={14} /> Last 4 hidden</> : <><Eye size={14} /> Last 4 visible</>}
            </button>
          </div>
          <div className="setting-row">
            <span>Density</span>
            <select value={density} onChange={(e) => setDensity(e.target.value)}>
              <option value="comfortable">Comfortable</option>
              <option value="compact">Compact</option>
            </select>
          </div>
        </Panel>
        <Panel title="Data">
          <div className="setting-row">
            <span>Download CSV export</span>
            <a className="btn" href="/api/export"><Download size={14} /> Export</a>
          </div>
          <div className="setting-row">
            <span>Create local backup</span>
            <button className="btn" onClick={() => mutate(api.backup, "Backup created")}><Archive size={14} /> Backup</button>
          </div>
        </Panel>
        <Panel title="Telegram commands">
          <div className="command-list">
            {["/cards", "/info", "/fees", "/bonus", "/track", "/stats", "/backup", "/export"].map((cmd) => (
              <code key={cmd}>{cmd}</code>
            ))}
          </div>
        </Panel>
      </section>

      <DiagnosticsPanel data={diagData} />
    </div>
  );
}

/* ── Diagnostics panel ── */
function DiagnosticsPanel({ data }) {
  if (!data) return null;
  const { counts, issues } = data;
  return (
    <Panel
      title="Data health"
      sub={`${counts.cards} cards checked · ${counts.issues} issue${counts.issues !== 1 ? "s" : ""} found`}
    >
      {issues.length === 0 ? (
        <div className="diag-ok">
          <Check size={15} /> All {counts.cards} cards look healthy.
        </div>
      ) : (
        <>
          <div className="diag-summary">
            {counts.errors   > 0 && <span className="pill rose">{counts.errors} error{counts.errors !== 1 ? "s" : ""}</span>}
            {counts.warnings > 0 && <span className="pill amber">{counts.warnings} warning{counts.warnings !== 1 ? "s" : ""}</span>}
          </div>
          {issues.map((issue, i) => (
            <div key={i} className={`diag-issue ${issue.severity}`}>
              <div className="diag-dot" />
              <div>{issue.message}</div>
            </div>
          ))}
        </>
      )}
    </Panel>
  );
}

/* ── Card detail view ── */
function Details({ selected, hideLast4, closeDetails, setEditing, mutate }) {
  const progress = bonusProgress(selected);
  const [tab, setTab] = useState("overview");

  return (
    <div className="content">
      <PageHeader title={`${selected.bank} ${selected.name}`} sub={selected.status === "cancelled" ? "Cancelled card" : "Active card"}>
        <button className="btn" onClick={closeDetails}>← Back</button>
        <button className="btn primary" onClick={() => setEditing(selected)}><Pencil size={14} /> Edit</button>
      </PageHeader>

      <section className="detail-grid">
        <Panel>
          <CardArt card={selected} large hideLast4={hideLast4} />
          <div className="detail-actions">
            {selected.status === "cancelled" ? (
              <button className="btn" onClick={() => mutate(() => api.reactivateCard(selected.id), "Card reactivated")}>
                <RefreshCcw size={14} /> Reactivate
              </button>
            ) : (
              <button className="btn danger" onClick={() => window.confirm("Cancel this card?") && mutate(() => api.cancelCard(selected.id), "Card cancelled")}>
                <Archive size={14} /> Cancel card
              </button>
            )}
            <button
              className="btn danger"
              onClick={() => window.confirm("Permanently delete this card?") && mutate(() => api.deleteCard(selected.id), "Card deleted").then(() => setSelectedId(null))}
            >
              <Trash2 size={14} /> Delete
            </button>
          </div>
        </Panel>

        <Panel title="Card workspace">
          <div className="tabs">
            {["overview", "fee history", "welcome offer", "timeline"].map((t) => (
              <button key={t} className={tab === t ? "active" : ""} onClick={() => setTab(t)}>{t}</button>
            ))}
          </div>

          {tab === "overview" && (
            <dl className="details">
              <dt>Annual fee</dt><dd>{fmtMoney(selected.annualFee)}</dd>
              <dt>Fee month</dt><dd>{selected.feeMonth || "N/A"}</dd>
              <dt>Expiry</dt>   <dd>{selected.expiry || "N/A"}</dd>
              <dt>Last 4</dt>   <dd>{hideLast4 ? "••••" : selected.last4 || "N/A"}</dd>
              <dt>Tags</dt>     <dd>{selected.tags.length ? selected.tags.join(", ") : "N/A"}</dd>
              <dt>Notes</dt>    <dd>{selected.notes || "N/A"}</dd>
            </dl>
          )}

          {tab === "fee history" && (
            <dl className="details">
              <dt>Waived</dt>      <dd>{selected.feeHistory?.waivedCount || 0} times</dd>
              <dt>Paid</dt>        <dd>{selected.feeHistory?.paidCount   || 0} times</dd>
              <dt>Last action</dt> <dd>{selected.feeHistory?.lastAction || "N/A"} {selected.feeHistory?.lastActionYear || ""}</dd>
              <dt>Next step</dt>   <dd>{daysUntilMonth(selected.feeMonth) <= 60 ? "Call for waiver or decide whether to keep." : "No immediate fee action."}</dd>
            </dl>
          )}

          {tab === "welcome offer" && (
            <div>
              <div className="bonus-name">{selected.bonus?.offer || "No offer recorded"}</div>
              <div className="progress"><span style={{ width: `${progress.percent}%` }} /></div>
              <div className="bonus-meta">
                {fmtMoney(selected.bonus?.currentSpend)} / {fmtMoney(selected.bonus?.minSpend)} · {progress.days ?? "N/A"} days left
              </div>
              <button
                className="btn small"
                style={{ marginTop: 12 }}
                onClick={() => {
                  const amount = Number(prompt("Add spend amount"));
                  if (amount > 0) mutate(() => api.addSpend(selected.id, amount), "Spend updated");
                }}
              >Add spend</button>
            </div>
          )}

          {tab === "timeline" && (
            <dl className="details">
              <dt>Applied</dt>     <dd>{fmtDate(selected.dates?.applied)}</dd>
              <dt>Approved</dt>    <dd>{fmtDate(selected.dates?.approved)}</dd>
              <dt>Received</dt>    <dd>{fmtDate(selected.dates?.received)}</dd>
              <dt>Activated</dt>   <dd>{fmtDate(selected.dates?.activated)}</dd>
              <dt>First charge</dt><dd>{fmtDate(selected.dates?.firstCharge)}</dd>
              <dt>Cancelled</dt>   <dd>{fmtDate(selected.dates?.cancelled)}</dd>
              <dt>Re-apply</dt>    <dd>{fmtDate(selected.dates?.reapply)}</dd>
            </dl>
          )}
        </Panel>
      </section>
    </div>
  );
}

/* ── Card editor drawer ── */
function CardEditor({ card, tags, onClose, onSave }) {
  const [draft, setDraft]     = useState(() => JSON.parse(JSON.stringify(card)));
  const [uploading, setUploading] = useState(false);

  const set = (path, value) => {
    setDraft((cur) => {
      const next = {
        ...cur,
        dates:      { ...(cur.dates      || {}) },
        bonus:      { ...(cur.bonus      || {}) },
        feeHistory: { ...(cur.feeHistory || {}) },
      };
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
    <div className="scrim" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="drawer">
        <div className="drawer-head">
          <div>
            <h2>{draft.id ? "Edit card" : "Add card"}</h2>
            <p>Fill in as much detail as you have.</p>
          </div>
          <button className="icon-btn" onClick={onClose}>✕</button>
        </div>

        <div className="drawer-body">
          <FormSection number="01" title="Card identity">
            <Input label="Bank"          value={draft.bank}   onChange={(v) => set("bank", v)} />
            <Input label="Card name"     value={draft.name}   onChange={(v) => set("name", v)} />
            <Input label="Last 4 digits" value={draft.last4}  maxLength={4} onChange={(v) => set("last4", v.replace(/\D/g, ""))} />
            <Input label="Expiry MM/YY"  value={draft.expiry} placeholder="05/27" onChange={(v) => set("expiry", v)} />
            <Input label="Annual fee"    value={draft.annualFee} type="number" onChange={(v) => set("annualFee", Number(v))} />
          </FormSection>

          <FormSection number="02" title="Card image">
            <div className="image-preview"><CardArt card={draft} large hideLast4={false} /></div>
            <label className="field span">
              <span>Upload image</span>
              <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => upload(e.target.files?.[0])} />
              {uploading && <small>Uploading…</small>}
            </label>
          </FormSection>

          <FormSection number="03" title="Tags and notes">
            <label className="field span">
              <span>Tags</span>
              <select multiple value={draft.tags || []} onChange={(e) => set("tags", [...e.target.selectedOptions].map((o) => o.value))}>
                {tags.map((t) => <option key={t}>{t}</option>)}
              </select>
            </label>
            <label className="field span">
              <span>Notes</span>
              <textarea value={draft.notes || ""} onChange={(e) => set("notes", e.target.value)} />
            </label>
          </FormSection>

          <FormSection number="04" title="Welcome offer">
            <Input label="Offer"         value={draft.bonus?.offer}        onChange={(v) => set("bonus.offer", v)} />
            <Input label="Min spend"     value={draft.bonus?.minSpend}     type="number" onChange={(v) => set("bonus.minSpend",     Number(v))} />
            <Input label="Current spend" value={draft.bonus?.currentSpend} type="number" onChange={(v) => set("bonus.currentSpend", Number(v))} />
            <Input label="Deadline"      value={draft.bonus?.deadline || ""} type="date" onChange={(v) => set("bonus.deadline", v)} />
            <label className="field">
              <span>Status</span>
              <select value={draft.bonus?.status || "Not Started"} onChange={(e) => set("bonus.status", e.target.value)}>
                {["Not Started", "In Progress", "Met", "Received"].map((s) => <option key={s}>{s}</option>)}
              </select>
            </label>
          </FormSection>

          <FormSection number="05" title="Dates">
            {[
              ["Applied",      "dates.applied"],
              ["Approved",     "dates.approved"],
              ["Received",     "dates.received"],
              ["Activated",    "dates.activated"],
              ["First charge", "dates.firstCharge"],
            ].map(([label, path]) => (
              <Input key={path} label={label} type="date"
                value={path.split(".").reduce((o, k) => o?.[k], draft) || ""}
                onChange={(v) => set(path, v)}
              />
            ))}
          </FormSection>

          <FormSection number="06" title="Fee and cancellation">
            <label className="field">
              <span>Fee month</span>
              <select value={draft.feeMonth || ""} onChange={(e) => set("feeMonth", e.target.value)}>
                <option value="">N/A</option>
                {MONTHS.map((m) => <option key={m}>{m}</option>)}
              </select>
            </label>
            <Input label="Waived count" value={draft.feeHistory?.waivedCount || 0} type="number" onChange={(v) => set("feeHistory.waivedCount", Number(v))} />
            <Input label="Paid count"   value={draft.feeHistory?.paidCount   || 0} type="number" onChange={(v) => set("feeHistory.paidCount",   Number(v))} />
            <Input label="Cancelled"    value={draft.dates?.cancelled || ""} type="date" onChange={(v) => set("dates.cancelled", v)} />
            <Input label="Re-apply"     value={draft.dates?.reapply   || ""} type="date" onChange={(v) => set("dates.reapply",   v)} />
            <label className="field">
              <span>Status</span>
              <select value={draft.status || "active"} onChange={(e) => set("status", e.target.value)}>
                <option value="active">Active</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </label>
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

/* ── Shared filter logic ── */
function filterCards(cards, { query, showCancelled, bank, tag, sort, status = "all" }) {
  const q = query.trim().toLowerCase();
  let result = cards.filter((c) => showCancelled || c.status !== "cancelled");
  if (status !== "all") result = result.filter((c) => c.status === status);
  if (bank) result = result.filter((c) => c.bank === bank);
  if (tag)  result = result.filter((c) => c.tags.includes(tag));
  if (q)    result = result.filter((c) => [c.bank, c.name, c.notes, c.tags.join(" ")].join(" ").toLowerCase().includes(q));
  if (sort === "due")      result = [...result].sort((a, b) => daysUntilMonth(a.feeMonth) - daysUntilMonth(b.feeMonth));
  else if (sort === "fee-desc") result = [...result].sort((a, b) => b.annualFee - a.annualFee);
  else if (sort === "fee-asc")  result = [...result].sort((a, b) => a.annualFee - b.annualFee);
  else if (sort === "bank")     result = [...result].sort((a, b) => `${a.bank} ${a.name}`.localeCompare(`${b.bank} ${b.name}`));
  else result = [...result].sort((a, b) => a.sortOrder - b.sortOrder);
  return result;
}

/* ── Shared UI primitives ── */
function PageHeader({ title, sub, children }) {
  return (
    <div className="page-header">
      <div>
        <h1 className="page-title">{title}</h1>
        {sub && <p className="page-sub">{sub}</p>}
      </div>
      {children && <div className="page-actions">{children}</div>}
    </div>
  );
}

function Metric({ label, value, foot, urgent }) {
  return (
    <div className={`metric ${urgent ? "urgent" : ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{foot}</small>
    </div>
  );
}

function Panel({ title, sub, action, children, flush }) {
  return (
    <section className={`panel ${flush ? "flush" : ""}`}>
      {title && (
        <header>
          <div><h3>{title}</h3>{sub && <p>{sub}</p>}</div>
          {action}
        </header>
      )}
      <div className="panel-body">{children}</div>
    </section>
  );
}

function Empty({ children }) {
  return <div className="empty">{children}</div>;
}

function Input({ label, value, onChange, ...props }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input value={value ?? ""} onChange={(e) => onChange(e.target.value)} {...props} />
    </label>
  );
}

function FormSection({ number, title, children }) {
  return (
    <section className="form-section">
      <h3><span>{number}</span>{title}</h3>
      <div className="form-grid">{children}</div>
    </section>
  );
}

function CardRow({ card, hideLast4, onOpen, compact, children }) {
  return (
    <div className={`card-row ${compact ? "compact" : ""}`} onClick={onOpen}>
      <CardArt card={card} />
      <div className="card-main">
        <strong>{card.name}</strong>
        <span>{card.bank} · <code>{hideLast4 ? "••••" : card.last4 || "no last 4"}</code></span>
        {card.tags.length > 0 && (
          <div className="chips">{card.tags.map((t) => <em key={t}>{t}</em>)}</div>
        )}
      </div>
      {children}
    </div>
  );
}

function CardArt({ card, large, hideLast4 }) {
  const [from, to] = bankColor(card.bank);
  const hasImage   = card.imageFilename && card.imageFilename !== "default.png";
  return (
    <div
      className={`card-art ${large ? "large" : ""}`}
      style={{ background: `linear-gradient(135deg, ${from}, ${to})` }}
    >
      {hasImage && <img src={imageUrl(card.imageFilename)} alt={`${card.bank} ${card.name}`} />}
      {large && (
        <>
          <span>{card.bank}</span>
          <b>{hideLast4 ? "•••• •••• •••• ••••" : `•••• •••• •••• ${card.last4 || "0000"}`}</b>
          <strong>{card.name}</strong>
        </>
      )}
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
    <div className="row-actions" onClick={(e) => e.stopPropagation()}>
      <button className="icon-btn" title="Edit" onClick={() => setEditing(card)}><Pencil size={14} /></button>
      {card.status === "cancelled" ? (
        <button className="icon-btn" title="Reactivate" onClick={() => mutate(() => api.reactivateCard(card.id), "Card reactivated")}><RefreshCcw size={14} /></button>
      ) : (
        <button className="icon-btn" title="Cancel" onClick={() => window.confirm("Cancel this card?") && mutate(() => api.cancelCard(card.id), "Card cancelled")}><Archive size={14} /></button>
      )}
      <button className="icon-btn danger" title="Delete" onClick={() => window.confirm("Permanently delete?") && mutate(() => api.deleteCard(card.id), "Card deleted")}><Trash2 size={14} /></button>
    </div>
  );
}

function BonusRow({ card, onOpen, children }) {
  const progress = bonusProgress(card);
  const tone     = (progress.days ?? 999) <= 30 ? "rose" : (progress.days ?? 999) <= 90 ? "amber" : "teal";
  return (
    <div className="bonus-row" onClick={onOpen}>
      <CardArt card={card} />
      <div>
        <strong>{card.name}<span>{card.bonus?.offer ? ` · ${card.bonus.offer}` : ""}</span></strong>
        <div className="bonus-meta">
          <span className={`pill ${tone}`}>{progress.days ?? "N/A"}d</span>
          <span>{fmtMoney(card.bonus?.currentSpend)} / {fmtMoney(card.bonus?.minSpend)}</span>
          <span>{fmtMoney(progress.remaining)} left</span>
        </div>
        <div className="progress"><span style={{ width: `${progress.percent}%` }} /></div>
      </div>
      {children}
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
