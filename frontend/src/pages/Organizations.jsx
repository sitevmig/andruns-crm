import { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import { api, apiError, API } from "@/lib/api";
import { StatusBadge, fmtDate } from "@/components/StatusBadge";
import OrgDrawer from "@/components/OrgDrawer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger,
} from "@/components/ui/dialog";
import { Search, Download } from "lucide-react";

const ALL = "__all__";

export default function Organizations() {
  const [meta, setMeta] = useState({ statuses: [], categories: [], cities: [], saved_filters: [] });
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState(new Set());
  const [openId, setOpenId] = useState(null);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({ search: "", status: "", category: "", city: "", has_email: "", has_telegram: "", do_not_contact: "" });
  const [sortBy, setSortBy] = useState("updated_at");
  const [templates, setTemplates] = useState([]);
  const [enqueueChannel, setEnqueueChannel] = useState("email");
  const [enqueueTpl, setEnqueueTpl] = useState("");
  const [bulkStatus, setBulkStatus] = useState("");

  useEffect(() => {
    api.get("/organizations/meta").then((r) => setMeta(r.data));
    api.get("/templates").then((r) => setTemplates(r.data));
  }, []);

  const load = useCallback(() => {
    const params = { ...filters, sort_by: sortBy, sort_dir: -1, page, page_size: 50 };
    Object.keys(params).forEach((k) => { if (params[k] === "" || params[k] == null) delete params[k]; });
    api.get("/organizations", { params }).then((r) => { setItems(r.data.items); setTotal(r.data.total); });
  }, [filters, sortBy, page]);

  useEffect(() => { load(); }, [load]);

  const applySaved = (sf) => {
    setFilters({ search: "", status: "", category: "", city: "", has_email: "", has_telegram: "", do_not_contact: "", ...sf.filters });
    setPage(1);
  };

  const toggleAll = () => {
    if (selected.size === items.length) setSelected(new Set());
    else setSelected(new Set(items.map((i) => i.id)));
  };
  const toggle = (id) => {
    const s = new Set(selected);
    s.has(id) ? s.delete(id) : s.add(id);
    setSelected(s);
  };

  const ids = [...selected];

  const doBulkStatus = async () => {
    if (!bulkStatus || ids.length === 0) return;
    try { await api.post("/organizations/bulk/status", { ids, status: bulkStatus }); toast.success("Статус обновлён"); setSelected(new Set()); load(); }
    catch (e) { toast.error(apiError(e)); }
  };
  const doArchive = async () => {
    try { await api.post("/organizations/bulk/archive", { ids }); toast.success("Архивировано"); setSelected(new Set()); load(); }
    catch (e) { toast.error(apiError(e)); }
  };
  const doEnqueue = async () => {
    if (!enqueueTpl) { toast.error("Выберите шаблон"); return; }
    try {
      const { data } = await api.post("/queue/enqueue", { org_ids: ids, channel: enqueueChannel, template_id: enqueueTpl });
      toast.success(`Добавлено в очередь: ${data.added}, пропущено: ${data.skipped}`);
      setSelected(new Set());
    } catch (e) { toast.error(apiError(e)); }
  };
  const doRemoveQueue = async () => {
    try { await api.post("/queue/remove", { ids }); toast.success("Исключено из очереди"); }
    catch (e) { toast.error(apiError(e)); }
  };
  const exportSelected = async () => {
    // export filtered current view
    const res = await api.post("/export/filtered", { filters }, { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a"); a.href = url; a.download = "crm_filtered.xlsx"; a.click();
  };

  const filteredTemplates = templates.filter((t) => t.channel === enqueueChannel);

  return (
    <div className="space-y-3" data-testid="organizations-page">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold tracking-tight">Организации <span className="text-muted-foreground font-normal">({total})</span></h1>
        <Button size="sm" variant="outline" className="h-8" onClick={exportSelected} data-testid="export-view-btn"><Download size={14} className="mr-1" />Экспорт вида</Button>
      </div>

      {/* Saved filters */}
      <div className="flex flex-wrap gap-1">
        {meta.saved_filters.map((sf) => (
          <Button key={sf.key} size="sm" variant="secondary" className="h-7 text-xs" onClick={() => applySaved(sf)} data-testid={`saved-filter-${sf.key}`}>
            {sf.label}
          </Button>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 items-center bg-white border border-border rounded-sm p-2">
        <div className="relative">
          <Search size={14} className="absolute left-2 top-2 text-muted-foreground" />
          <Input placeholder="Поиск…" value={filters.search} onChange={(e) => setFilters({ ...filters, search: e.target.value })} className="h-8 pl-7 w-56" data-testid="search-input" />
        </div>
        <FilterSelect value={filters.status} onChange={(v) => setFilters({ ...filters, status: v })} options={meta.statuses} placeholder="Статус" testid="filter-status" />
        <FilterSelect value={filters.category} onChange={(v) => setFilters({ ...filters, category: v })} options={meta.categories} placeholder="Категория" testid="filter-category" />
        <FilterSelect value={filters.city} onChange={(v) => setFilters({ ...filters, city: v })} options={meta.cities} placeholder="Город" testid="filter-city" />
        <FilterSelect value={filters.has_email} onChange={(v) => setFilters({ ...filters, has_email: v })} options={["yes", "no"]} labels={{ yes: "Есть email", no: "Нет email" }} placeholder="Email" testid="filter-email" />
        <FilterSelect value={filters.has_telegram} onChange={(v) => setFilters({ ...filters, has_telegram: v })} options={["yes", "no"]} labels={{ yes: "Есть TG", no: "Нет TG" }} placeholder="Telegram" testid="filter-tg" />
        <FilterSelect value={filters.do_not_contact} onChange={(v) => setFilters({ ...filters, do_not_contact: v })} options={["yes", "no"]} labels={{ yes: "Не связываться", no: "Можно писать" }} placeholder="ЧС" testid="filter-dnc" />
        <Button size="sm" variant="ghost" className="h-8" onClick={() => setFilters({ search: "", status: "", category: "", city: "", has_email: "", has_telegram: "", do_not_contact: "" })}>Сброс</Button>
      </div>

      {/* Bulk actions */}
      {selected.size > 0 && (
        <div className="flex flex-wrap items-center gap-2 bg-primary/5 border border-primary/20 rounded-sm p-2" data-testid="bulk-bar">
          <span className="text-sm font-medium">Выбрано: {selected.size}</span>
          <Select value={bulkStatus} onValueChange={setBulkStatus}>
            <SelectTrigger className="h-8 w-44" data-testid="bulk-status-select"><SelectValue placeholder="Изменить статус" /></SelectTrigger>
            <SelectContent>{meta.statuses.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
          </Select>
          <Button size="sm" className="h-8" onClick={doBulkStatus} data-testid="apply-bulk-status">Применить</Button>

          <Dialog>
            <DialogTrigger asChild>
              <Button size="sm" variant="outline" className="h-8" data-testid="bulk-enqueue-btn">В очередь</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>Добавить {selected.size} в очередь</DialogTitle></DialogHeader>
              <div className="space-y-2">
                <Select value={enqueueChannel} onValueChange={(v) => { setEnqueueChannel(v); setEnqueueTpl(""); }}>
                  <SelectTrigger className="h-8" data-testid="enqueue-channel"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="email">Email</SelectItem>
                    <SelectItem value="telegram">Telegram</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={enqueueTpl} onValueChange={setEnqueueTpl}>
                  <SelectTrigger className="h-8" data-testid="enqueue-template"><SelectValue placeholder="Шаблон" /></SelectTrigger>
                  <SelectContent>{filteredTemplates.map((t) => <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <DialogFooter><Button onClick={doEnqueue} data-testid="confirm-enqueue">Добавить</Button></DialogFooter>
            </DialogContent>
          </Dialog>

          <Button size="sm" variant="outline" className="h-8" onClick={doRemoveQueue} data-testid="bulk-remove-queue">Исключить из очереди</Button>
          <Button size="sm" variant="outline" className="h-8" onClick={doArchive} data-testid="bulk-archive">Архивировать</Button>
        </div>
      )}

      {/* Table */}
      <div className="bg-white border border-border rounded-sm overflow-auto">
        <table className="crm-table w-full text-sm border-collapse">
          <thead>
            <tr>
              <th className="w-8"><Checkbox checked={selected.size > 0 && selected.size === items.length} onCheckedChange={toggleAll} data-testid="select-all" /></th>
              <th className="cursor-pointer" onClick={() => setSortBy("name")}>Организация</th>
              <th>Категория</th>
              <th>Город</th>
              <th>Телефон</th>
              <th>Email</th>
              <th>Telegram</th>
              <th>Статус</th>
              <th>Канал</th>
              <th className="cursor-pointer" onClick={() => setSortBy("last_message_at")}>Последнее сообщение</th>
              <th>След. действие</th>
              <th>Комментарий</th>
              <th>ЧС</th>
            </tr>
          </thead>
          <tbody>
            {items.map((o) => (
              <tr key={o.id} className="cursor-pointer" data-testid={`org-row-${o.id}`}>
                <td onClick={(e) => e.stopPropagation()}><Checkbox checked={selected.has(o.id)} onCheckedChange={() => toggle(o.id)} data-testid={`select-${o.id}`} /></td>
                <td className="font-medium text-primary" onClick={() => setOpenId(o.id)} data-testid={`org-name-${o.id}`}>{o.name}</td>
                <td onClick={() => setOpenId(o.id)}>{o.category || "—"}</td>
                <td onClick={() => setOpenId(o.id)}>{o.city || "—"}</td>
                <td onClick={() => setOpenId(o.id)}>{o.phone || "—"}</td>
                <td onClick={() => setOpenId(o.id)}>{o.email || "—"}</td>
                <td onClick={() => setOpenId(o.id)}>{o.telegram || "—"}</td>
                <td onClick={() => setOpenId(o.id)}><StatusBadge status={o.status} /></td>
                <td onClick={() => setOpenId(o.id)}>{o.last_channel || "—"}</td>
                <td onClick={() => setOpenId(o.id)}>{fmtDate(o.last_message_at)}</td>
                <td onClick={() => setOpenId(o.id)}>{o.next_action_at ? fmtDate(o.next_action_at) : "—"}</td>
                <td onClick={() => setOpenId(o.id)} className="max-w-[160px] truncate">{o.comment || "—"}</td>
                <td onClick={() => setOpenId(o.id)}>{o.do_not_contact ? <span className="text-red-600 font-bold">✕</span> : ""}</td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr><td colSpan={13} className="text-center text-muted-foreground py-6">Нет данных</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">Стр. {page} · всего {total}</span>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" className="h-8" disabled={page <= 1} onClick={() => setPage(page - 1)}>Назад</Button>
          <Button size="sm" variant="outline" className="h-8" disabled={page * 50 >= total} onClick={() => setPage(page + 1)}>Вперёд</Button>
        </div>
      </div>

      {openId && <OrgDrawer orgId={openId} statuses={meta.statuses} onClose={() => setOpenId(null)} onChanged={load} />}
    </div>
  );
}

function FilterSelect({ value, onChange, options, labels = {}, placeholder, testid }) {
  return (
    <Select value={value || ALL} onValueChange={(v) => onChange(v === ALL ? "" : v)}>
      <SelectTrigger className="h-8 w-36" data-testid={testid}><SelectValue placeholder={placeholder} /></SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL}>{placeholder}: все</SelectItem>
        {options.map((o) => <SelectItem key={o} value={o}>{labels[o] || o}</SelectItem>)}
      </SelectContent>
    </Select>
  );
}
