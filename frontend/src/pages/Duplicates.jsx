import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, apiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

export default function Duplicates() {
  const [dups, setDups] = useState([]);
  const [keep, setKeep] = useState({});

  const load = () => api.get("/duplicates").then((r) => setDups(r.data));
  useEffect(() => { load(); }, []);

  const merge = async (d) => {
    const keepId = keep[d.id] || d.candidate_ids[0];
    try {
      await api.post("/duplicates/merge", { duplicate_id: d.id, keep_id: keepId, merge_ids: d.candidate_ids });
      toast.success("Дубликаты объединены"); load();
    } catch (e) { toast.error(apiError(e)); }
  };
  const dismiss = async (id) => { await api.post(`/duplicates/${id}/dismiss`); toast.success("Отклонено"); load(); };

  return (
    <div className="space-y-3" data-testid="duplicates-page">
      <h1 className="text-lg font-semibold tracking-tight">Ручная проверка дублей</h1>
      {dups.length === 0 && <div className="text-center text-muted-foreground py-8">Дублей на проверку нет</div>}
      <div className="space-y-3">
        {dups.map((d) => (
          <Card key={d.id} className="p-3 rounded-sm border shadow-none" data-testid={`dup-${d.id}`}>
            <div className="text-sm font-medium mb-2">Возможный дубль: {d.name}</div>
            <div className="grid md:grid-cols-2 gap-2">
              {(d.candidates || []).map((c) => (
                <label key={c.id} className={`border rounded-sm p-2 text-sm cursor-pointer ${(keep[d.id] || d.candidate_ids[0]) === c.id ? "border-primary bg-primary/5" : "border-border"}`}>
                  <input type="radio" name={`keep-${d.id}`} className="mr-2" checked={(keep[d.id] || d.candidate_ids[0]) === c.id} onChange={() => setKeep({ ...keep, [d.id]: c.id })} data-testid={`keep-${c.id}`} />
                  <b>{c.name}</b> {c.do_not_contact && <span className="text-red-600">(ЧС)</span>}
                  <div className="text-xs text-muted-foreground mt-1">{c.city} · {c.phone} · {c.email} · {c.telegram} · статус: {c.status}</div>
                </label>
              ))}
            </div>
            <div className="flex gap-2 mt-2">
              <AlertDialog>
                <AlertDialogTrigger asChild><Button size="sm" className="h-8" data-testid={`merge-${d.id}`}>Объединить</Button></AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Объединить дубли?</AlertDialogTitle>
                    <AlertDialogDescription>Выбранная запись останется, остальные будут архивированы, история перенесена. Отменить нельзя.</AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Отмена</AlertDialogCancel>
                    <AlertDialogAction onClick={() => merge(d)} data-testid={`confirm-merge-${d.id}`}>Объединить</AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
              <Button size="sm" variant="outline" className="h-8" onClick={() => dismiss(d.id)} data-testid={`dismiss-${d.id}`}>Не дубль</Button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
