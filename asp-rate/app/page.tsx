"use client";

import { getRaterId } from "@/lib/rater-id";
import { getSupabaseAnonKey, getSupabaseUrl, supabase } from "@/lib/supabase";
import type { Task, TasksManifest } from "@/lib/types";
import { useCallback, useEffect, useMemo, useState } from "react";

type RatingRow = { task_id: string; rater_uuid: string };

const DIFFICULTY_LABELS = [
  "",
  "Trivijalan",
  "Lagan",
  "Srednji",
  "Težak",
  "Vrlo težak",
];

function describeSupabaseError(err: unknown): string {
  const msg = err instanceof Error ? err.message : String(err);
  const url = getSupabaseUrl();
  const keySet = getSupabaseAnonKey().length > 0;
  let host = "(nije postavljen)";
  try {
    if (url) host = new URL(url).host;
  } catch {
    host = `(neispravan URL: "${url}")`;
  }
  const hints: string[] = [];
  if (!url || !keySet)
    hints.push(
      "NEXT_PUBLIC_SUPABASE_URL / ANON_KEY nisu postavljeni u .env.local",
    );
  if (msg.toLowerCase().includes("failed to fetch")) {
    hints.push(
      "Failed to fetch obično znači jedno od: pogrešan URL, projekt pauziran, ad-blocker, ili CORS.",
    );
    hints.push(
      "Otvori DevTools → Network, klikni neuspješni request prema " +
        host +
        " i vidi status / response.",
    );
    hints.push(
      "Ako si tek editirao .env.local — restartaj `npm run dev` (env varijable se peku u bundle).",
    );
  }
  return `Supabase greška (${host}): ${msg}\n• ` + hints.join("\n• ");
}

export default function Page() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [ratings, setRatings] = useState<RatingRow[]>([]);
  const [raterId, setRaterId] = useState<string>("");
  const [current, setCurrent] = useState<Task | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [zoomed, setZoomed] = useState(false);
  const [pulseValue, setPulseValue] = useState<number | null>(null);
  const [toastKey, setToastKey] = useState(0);

  useEffect(() => {
    setRaterId(getRaterId());

    fetch("/tasks.json")
      .then((r) => r.json() as Promise<TasksManifest>)
      .then((m) => setTasks(m.tasks))
      .catch((e) => setError(`Ne mogu učitati zadatke: ${e.message}`));

    refreshRatings();
  }, []);

  const refreshRatings = useCallback(async () => {
    try {
      const { data, error } = await supabase
        .from("ratings")
        .select("task_id, rater_uuid");
      if (error) {
        setError(describeSupabaseError(error));
        return;
      }
      setRatings((data ?? []) as RatingRow[]);
      setError(null);
    } catch (e) {
      setError(describeSupabaseError(e));
    }
  }, []);

  const pickNext = useCallback(
    (allTasks: Task[], allRatings: RatingRow[], myId: string): Task | null => {
      if (allTasks.length === 0) return null;
      const counts = new Map<string, number>();
      const mine = new Set<string>();
      for (const r of allRatings) {
        counts.set(r.task_id, (counts.get(r.task_id) ?? 0) + 1);
        if (r.rater_uuid === myId) mine.add(r.task_id);
      }
      const pool = allTasks.filter((t) => !mine.has(t.task_id));
      if (pool.length === 0) return null;
      pool.sort((a, b) => {
        const ca = counts.get(a.task_id) ?? 0;
        const cb = counts.get(b.task_id) ?? 0;
        if (ca !== cb) return ca - cb;
        return a.task_id < b.task_id ? -1 : 1;
      });
      return pool[0];
    },
    [],
  );

  useEffect(() => {
    if (!raterId || tasks.length === 0) return;
    setCurrent(pickNext(tasks, ratings, raterId));
    setZoomed(false);
  }, [tasks, ratings, raterId, pickNext]);

  const myCount = useMemo(
    () => ratings.filter((r) => r.rater_uuid === raterId).length,
    [ratings, raterId],
  );

  const submit = useCallback(
    async (difficulty: number) => {
      if (!current || submitting) return;
      setSubmitting(true);
      setError(null);
      setPulseValue(difficulty);
      try {
        const { error } = await supabase.from("ratings").insert({
          task_id: current.task_id,
          rater_uuid: raterId,
          difficulty,
        });
        if (error) {
          setError(describeSupabaseError(error));
          setSubmitting(false);
          setPulseValue(null);
          return;
        }
        // Toast + small delay so the user sees the rating registered before
        // the next card slides in.
        setToastKey((k) => k + 1);
        await new Promise((r) => setTimeout(r, 240));
        setRatings((prev) => [
          ...prev,
          { task_id: current.task_id, rater_uuid: raterId },
        ]);
      } catch (e) {
        setError(describeSupabaseError(e));
      } finally {
        setSubmitting(false);
        setPulseValue(null);
      }
    },
    [current, raterId, submitting],
  );

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (zoomed && e.key === "Escape") {
        setZoomed(false);
        return;
      }
      if (!current || zoomed) return;
      if (e.key >= "1" && e.key <= "5") {
        e.preventDefault();
        submit(Number(e.key));
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [current, submit, zoomed]);

  return (
    <main className="mx-auto max-w-3xl px-4 py-6">
      <header className="mb-4 flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">asp-rate</h1>
        <div className="text-sm text-gray-600">
          Ocijenjenih: <span className="font-mono">{myCount}</span> /{" "}
          {tasks.length}
        </div>
      </header>

      <aside className="mb-5 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm leading-relaxed text-blue-900">
        <p className="mb-1 font-medium">O čemu se radi</p>
        <ul className="list-inside list-disc space-y-1">
          <li>
            Prikupljaju se ocjene težine zadataka iz kolegija "Algoritmi i
            strukture podataka" za potrebe završnog rada.
          </li>
          <li>
            Podaci se koriste za izgradnju recommendera koji predlaže zadatke za
            vježbu.
          </li>
          <li>Sve je anonimno.</li>
          <li>
            Nema fiksne kvote ni roka - ocijeni koliko želiš i možeš se vratiti
            kad god.
          </li>
          <li>
            Postoji mogućnost da će se sličan alat napraviti i za druge
            predmete. Osobe koje ocijene više od 50% zadataka imat će pristup
            svim budućim verzijama.
          </li>
          <li>
            Kad ocjenjujete težinu, ne morate previše razmišljati, dovoljno je
            uzeti prvi okvirni broj koji vam padne na pamet. Nažalost vam ne
            mogu reć da bi, primjerice, bilo prirodno da quick sort dobije manju
            težinu od nekog zadatka s rekurzijom jer je ovo sve subjektivno i ne
            smijem u uputama sugestirat ni na koji način.
          </li>
          <li>Što se tiče estimacije vremena, također, </li>
          <li>
            Ocjena <strong>i samo jednog zadatka</strong> stvarno pomaže. Hvala!
          </li>
        </ul>
      </aside>

      {error && (
        <div className="mb-4 whitespace-pre-line rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {!current && tasks.length > 0 && !error && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-6 text-center">
          <p className="text-lg font-medium text-green-900">
            🎉 Ocijenio si sve dostupne zadatke. Hvala!
          </p>
          <p className="mt-1 text-sm text-green-800">
            Možeš zatvoriti karticu.
          </p>
        </div>
      )}

      {current && (
        <section
          key={current.task_id}
          className="animate-card-in rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
        >
          <div className="mb-3 flex items-center justify-between text-sm text-gray-600">
            <div>
              <span className="font-medium text-gray-900">
                {current.exam_type}
              </span>{" "}
              · {current.exam_date} · Zadatak {current.task_no}
            </div>
            <div className="text-xs text-gray-400">str. {current.pdf_page}</div>
          </div>

          <button
            type="button"
            onClick={() => setZoomed(true)}
            className="block w-full overflow-hidden rounded border border-gray-200 bg-gray-50 transition hover:border-gray-400"
            aria-label="Otvori sliku u punoj veličini"
          >
            <img
              src={current.image_path}
              alt={`Stranica ${current.pdf_page} (${current.exam_type})`}
              className="block max-h-[70vh] w-full cursor-zoom-in object-contain"
            />
          </button>
          <p className="mt-1 text-center text-xs text-gray-400">
            Klikni sliku za zoom · na mobitelu pinch-to-zoom unutar zoom prikaza
          </p>

          <div className="mt-4">
            <p className="mb-2 text-sm text-gray-700">
              Koliko je <strong>zadatak {current.task_no}</strong> težak prema
              tvojoj procjeni?
            </p>
            <div className="grid grid-cols-5 gap-2">
              {[1, 2, 3, 4, 5].map((n) => {
                const isPulsing = pulseValue === n;
                return (
                  <button
                    key={n}
                    disabled={submitting}
                    onClick={() => submit(n)}
                    className={
                      "rounded-md border border-gray-300 bg-white px-3 py-3 text-center text-sm font-medium text-gray-900 transition hover:border-gray-900 hover:bg-gray-900 hover:text-white disabled:opacity-50 " +
                      (isPulsing ? "animate-btn-pulse" : "")
                    }
                    aria-label={`Ocjena ${n} — ${DIFFICULTY_LABELS[n]}`}
                  >
                    <div className="text-lg font-semibold">{n}</div>
                    <div className="text-xs font-normal opacity-75">
                      {DIFFICULTY_LABELS[n]}
                    </div>
                  </button>
                );
              })}
            </div>
            <p className="mt-2 text-xs text-gray-500">
              Tipke 1–5 funkcioniraju kao prečaci.
            </p>
          </div>
        </section>
      )}

      <footer className="mt-6 text-center text-xs text-gray-400">
        Anonimno · ratings idu u Supabase · {raterId.slice(0, 8) || "..."}
      </footer>

      {toastKey > 0 && (
        <div
          key={toastKey}
          className="animate-toast pointer-events-none fixed left-1/2 top-4 z-40 -translate-x-1/2 rounded-full bg-emerald-600 px-4 py-1.5 text-sm font-medium text-white shadow-lg"
        >
          ✓ Spremljeno
        </div>
      )}

      {zoomed && current && (
        <div
          className="fixed inset-0 z-50 overflow-auto bg-black/90"
          onClick={() => setZoomed(false)}
          role="dialog"
          aria-modal="true"
        >
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setZoomed(false);
            }}
            className="fixed right-3 top-3 z-10 rounded-full bg-white/90 px-4 py-2 text-sm font-medium text-gray-900 shadow-md"
          >
            Zatvori ✕
          </button>
          <div
            className="mx-auto p-4"
            style={{ width: "min(180vw, 1600px)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <img
              src={current.image_path}
              alt={`Stranica ${current.pdf_page} (${current.exam_type}) — uvećano`}
              className="block h-auto w-full cursor-zoom-out"
              onClick={() => setZoomed(false)}
            />
          </div>
        </div>
      )}
    </main>
  );
}
