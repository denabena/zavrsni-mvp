"use client";

import { ensureSession } from "@/lib/auth";
import { supabase } from "@/lib/supabase";
import type { Task, TasksManifest, TimeEstMinutes } from "@/lib/types";
import { useCallback, useEffect, useMemo, useState } from "react";
import { TransformComponent, TransformWrapper } from "react-zoom-pan-pinch";
import Onboarding, { clearOnboarded, isOnboarded } from "./onboarding";

type RatingRow = { task_id: string; rater_uuid: string };

const DIFFICULTY_LABELS = [
  "",
  "Trivijalan",
  "Lagan",
  "Srednji",
  "Težak",
  "Vrlo težak",
];

const TIME_OPTIONS: TimeEstMinutes[] = [15, 30, 45, 60];

function userFacingError(err: unknown): string {
  const msg = err instanceof Error ? err.message : String(err);
  return `Greška kod spremanja. Pokušaj ponovno za par sekundi. (${msg})`;
}

export default function Page() {
  const [onboarded, setOnboarded] = useState<boolean | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [ratings, setRatings] = useState<RatingRow[]>([]);
  const [raterId, setRaterId] = useState<string>("");
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [isAnon, setIsAnon] = useState(true);
  const [current, setCurrent] = useState<Task | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [zoomed, setZoomed] = useState(false);
  const [isTouch, setIsTouch] = useState(false);

  // Sequential rating state
  const [pickedDifficulty, setPickedDifficulty] = useState<number | null>(null);
  const [pulseDifficulty, setPulseDifficulty] = useState<number | null>(null);
  const [pulseTime, setPulseTime] = useState<TimeEstMinutes | null>(null);
  const [toastKey, setToastKey] = useState(0);

  useEffect(() => {
    setOnboarded(isOnboarded());
    setIsTouch(window.matchMedia("(pointer: coarse)").matches);

    fetch("/tasks.json")
      .then((r) => r.json() as Promise<TasksManifest>)
      .then((m) => setTasks(m.tasks))
      .catch((e) => setError(`Ne mogu učitati zadatke: ${e.message}`));

    ensureSession().then((user) => {
      if (user) {
        setRaterId(user.id);
        setUserEmail(user.email ?? null);
        setIsAnon(Boolean(user.is_anonymous));
      }
      refreshRatings();
    });

    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      const u = session?.user ?? null;
      setRaterId(u?.id ?? "");
      setUserEmail(u?.email ?? null);
      setIsAnon(Boolean(u?.is_anonymous));
      refreshRatings();
    });
    return () => data.subscription.unsubscribe();
  }, []);

  const refreshRatings = useCallback(async () => {
    try {
      const { data, error } = await supabase
        .from("ratings")
        .select("task_id, rater_uuid");
      if (error) {
        setError(userFacingError(error));
        return;
      }
      setRatings((data ?? []) as RatingRow[]);
      setError(null);
    } catch (e) {
      setError(userFacingError(e));
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
    setPickedDifficulty(null);
  }, [tasks, ratings, raterId, pickNext]);

  const myCount = useMemo(
    () => ratings.filter((r) => r.rater_uuid === raterId).length,
    [ratings, raterId],
  );

  const progressPct = tasks.length > 0 ? (myCount / tasks.length) * 100 : 0;

  const submit = useCallback(
    async (difficulty: number, time_est_minutes: TimeEstMinutes) => {
      if (!current || submitting) return;
      setSubmitting(true);
      setError(null);
      setPulseTime(time_est_minutes);
      try {
        const { error } = await supabase.from("ratings").insert({
          task_id: current.task_id,
          rater_uuid: raterId,
          difficulty,
          time_est_minutes,
        });
        if (error) {
          setError(userFacingError(error));
          setSubmitting(false);
          setPulseTime(null);
          return;
        }
        setToastKey((k) => k + 1);
        await new Promise((r) => setTimeout(r, 240));
        setRatings((prev) => [
          ...prev,
          { task_id: current.task_id, rater_uuid: raterId },
        ]);
      } catch (e) {
        setError(userFacingError(e));
      } finally {
        setSubmitting(false);
        setPulseTime(null);
        setPickedDifficulty(null);
      }
    },
    [current, raterId, submitting],
  );

  const pickDifficulty = useCallback((n: number) => {
    setPulseDifficulty(n);
    setPickedDifficulty(n);
    window.setTimeout(() => setPulseDifficulty(null), 360);
  }, []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (zoomed && e.key === "Escape") {
        setZoomed(false);
        return;
      }
      if (!current || zoomed) return;

      // Escape: undo difficulty selection
      if (pickedDifficulty !== null && e.key === "Escape") {
        e.preventDefault();
        setPickedDifficulty(null);
        return;
      }

      // Phase 1: difficulty selection (1-5)
      if (pickedDifficulty === null && e.key >= "1" && e.key <= "5") {
        e.preventDefault();
        pickDifficulty(Number(e.key));
        return;
      }

      // Phase 2: time selection (1-4 -> 15/30/45/60)
      if (pickedDifficulty !== null && e.key >= "1" && e.key <= "4") {
        e.preventDefault();
        const idx = Number(e.key) - 1;
        submit(pickedDifficulty, TIME_OPTIONS[idx]);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [current, submit, zoomed, pickedDifficulty, pickDifficulty]);

  // Render onboarding until completed
  if (onboarded === null) return null; // SSR / first hydration
  if (!onboarded) {
    return (
      <Onboarding
        onDone={() => {
          setOnboarded(true);
          refreshRatings();
        }}
      />
    );
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-6">
      <header className="mb-3 flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">asp-rate</h1>
        <div className="text-sm text-gray-600">
          Ocijenjenih: <span className="font-mono">{myCount}</span> /{" "}
          {tasks.length}
        </div>
      </header>

      <div
        className="mb-5 h-2 w-full overflow-hidden rounded-full bg-gray-200"
        aria-label="Napredak"
      >
        <div
          className="h-full bg-emerald-500 transition-all duration-500 ease-out"
          style={{ width: `${progressPct}%` }}
        />
      </div>

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

          {/* Phase 1: difficulty */}
          <div className="mt-4">
            <p className="mb-2 text-sm text-gray-700">
              1. Koliko je <strong>zadatak {current.task_no}</strong> težak
              prema tvojoj procjeni?
            </p>
            <div className="grid grid-cols-5 gap-2">
              {[1, 2, 3, 4, 5].map((n) => {
                const isPulsing = pulseDifficulty === n;
                const isPicked = pickedDifficulty === n;
                const isLocked = pickedDifficulty !== null && !isPicked;
                return (
                  <button
                    key={n}
                    disabled={pickedDifficulty !== null || submitting}
                    onClick={() => pickDifficulty(n)}
                    className={
                      "rounded-md border px-3 py-3 text-center text-sm font-medium transition " +
                      (isPicked
                        ? "border-emerald-600 bg-emerald-600 text-white"
                        : isLocked
                          ? "border-gray-200 bg-gray-50 text-gray-400"
                          : "border-gray-300 bg-white text-gray-900 hover:border-gray-900 hover:bg-gray-900 hover:text-white") +
                      (isPulsing ? " animate-btn-pulse" : "")
                    }
                    aria-label={`Ocjena ${n}: ${DIFFICULTY_LABELS[n]}`}
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
              {pickedDifficulty === null
                ? "Tipke 1-5 funkcioniraju kao prečaci."
                : "Ocjena spremljena. Esc za promjenu."}
            </p>
          </div>

          {/* Phase 2: time estimate */}
          {pickedDifficulty !== null && (
            <div className="mt-5 animate-card-in">
              <p className="mb-2 text-sm text-gray-700">
                2. Procijeni vrijeme: koliko bi otprilike trebalo da se prođe
                kroz ovaj zadatak (rješavanje + proučavanje rješenja)?
              </p>
              <div className="grid grid-cols-4 gap-2">
                {TIME_OPTIONS.map((t, i) => {
                  const isPulsing = pulseTime === t;
                  return (
                    <button
                      key={t}
                      disabled={submitting}
                      onClick={() => submit(pickedDifficulty, t)}
                      className={
                        "rounded-md border border-gray-300 bg-white px-3 py-3 text-center text-sm font-medium text-gray-900 transition hover:border-gray-900 hover:bg-gray-900 hover:text-white disabled:opacity-50 " +
                        (isPulsing ? "animate-btn-pulse" : "")
                      }
                      aria-label={`${t} minuta`}
                    >
                      <div className="text-lg font-semibold">{t} min</div>
                      <div className="text-xs font-normal opacity-60">
                        ({i + 1})
                      </div>
                    </button>
                  );
                })}
              </div>
              <p className="mt-2 text-xs text-gray-500">
                Tipke 1-4 funkcioniraju kao prečaci za 15 / 30 / 45 / 60 min.
              </p>
            </div>
          )}
        </section>
      )}

      <footer className="mt-6 flex items-center justify-between text-xs text-gray-400">
        <span>
          {isAnon
            ? "Anoniman/na (ovaj browser)"
            : `Prijavljen/a: ${userEmail ?? ""}`}
        </span>
        <button
          type="button"
          onClick={() => {
            clearOnboarded();
            setOnboarded(false);
          }}
          className="underline underline-offset-2 hover:text-gray-700"
        >
          Info / upute
        </button>
      </footer>

      {toastKey > 0 && (
        <div
          key={toastKey}
          className="animate-toast pointer-events-none fixed left-1/2 top-4 z-40 -translate-x-1/2 rounded-full bg-emerald-600 px-4 py-1.5 text-sm font-medium text-white shadow-lg"
        >
          ✓ Spremljeno
        </div>
      )}

      {zoomed && current && isTouch && (
        <div
          className="fixed inset-0 z-50 bg-black/90"
          role="dialog"
          aria-modal="true"
        >
          <button
            type="button"
            onClick={() => setZoomed(false)}
            className="fixed right-3 top-3 z-10 rounded-full bg-white/90 px-4 py-2 text-sm font-medium text-gray-900 shadow-md"
          >
            Zatvori ✕
          </button>
          <p className="pointer-events-none fixed bottom-3 left-1/2 z-10 -translate-x-1/2 rounded-full bg-white/80 px-3 py-1 text-xs text-gray-700">
            Pinch ili dvostruki dodir za zoom · povuci za pomak
          </p>
          <TransformWrapper
            initialScale={1}
            minScale={1}
            maxScale={6}
            centerOnInit
            doubleClick={{ mode: "zoomIn", step: 1 }}
            wheel={{ step: 0.2 }}
          >
            <TransformComponent
              wrapperStyle={{ width: "100%", height: "100%" }}
              contentStyle={{
                width: "100%",
                height: "100%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <img
                src={current.image_path}
                alt={`Stranica ${current.pdf_page} (${current.exam_type}), uvećano`}
                className="max-h-screen max-w-full object-contain"
              />
            </TransformComponent>
          </TransformWrapper>
        </div>
      )}

      {zoomed && current && !isTouch && (
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
              alt={`Stranica ${current.pdf_page} (${current.exam_type}), uvećano`}
              className="block h-auto w-full cursor-zoom-out"
              onClick={() => setZoomed(false)}
            />
          </div>
        </div>
      )}
    </main>
  );
}
