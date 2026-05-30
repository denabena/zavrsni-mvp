"use client";

import { sendEmailCode, verifyEmailCode, type VerifyMode } from "@/lib/auth";
import { useState } from "react";

const ONBOARDED_KEY = "asp_rate_onboarded";

export function isOnboarded(): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(ONBOARDED_KEY) === "1";
}

export function markOnboarded(): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ONBOARDED_KEY, "1");
}

export function clearOnboarded(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(ONBOARDED_KEY);
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

type Props = {
  onDone: () => void;
};

export default function Onboarding({ onDone }: Props) {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [phase, setPhase] = useState<"email" | "code">("email");
  const [mode, setMode] = useState<VerifyMode>("link");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const finishAnon = () => {
    markOnboarded();
    onDone();
  };

  const sendCode = async () => {
    if (busy) return;
    const trimmed = email.trim();
    if (!EMAIL_RE.test(trimmed)) {
      setError("Email ne izgleda valjano.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const m = await sendEmailCode(trimmed);
      setMode(m);
      setPhase("code");
      setInfo(
        m === "signin"
          ? "Ovaj email već ima račun. Poslali smo kod za prijavu, tvoj napredak će se vratiti. Ako ne stigne u Inbox, provjeri spam/junk."
          : "Poslali smo ti 6-znamenkasti kod na email. Ako ne stigne u Inbox, provjeri spam/junk.",
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const verify = async () => {
    if (busy) return;
    const c = code.trim();
    if (!c) {
      setError("Unesi kod iz emaila.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await verifyEmailCode(email.trim(), c, mode);
      markOnboarded();
      onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="mb-1 text-2xl font-semibold tracking-tight">asp-rate</h1>
      <p className="mb-5 text-sm text-gray-600">
        Ocjenjivanje težine zadataka iz Algoritama i struktura podataka.
      </p>

      <section className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm leading-relaxed text-blue-900">
        <p className="mb-1 font-medium">O čemu se radi</p>
        <ul className="list-inside list-disc space-y-1">
          <li>
            Prikupljaju se ocjene težine zadataka i estimacije vremena iz
            kolegija "Algoritmi i strukture podataka" za potrebe završnog rada.
          </li>
          <li>
            Podaci se koriste za izgradnju recommendera koji predlaže zadatke za
            vježbu.
          </li>
          <li>Sve je anonimno.</li>
          <li>
            Nema fiksne kvote ni roka - ocijenite koliko želite, možete se
            vratiti kad god.
          </li>
          <li>
            Prolaženje kroz zadatke ne bi Vam trebalo oduzeti previše vremena.
            Ne morate detaljno iščitavati zadatke, slobodno ocjenjujte na osnovu
            osjećaja.
          </li>
          <li>
            Postoji mogućnost da će se sličan alat napraviti i za druge
            predmete. Osobe koje{" "}
            <strong>
              ocijene sve zadatke imat će pristup svim budućim verzijama.
            </strong>
          </li>
          <li>
            Kad ocjenjujete težinu, ne morate previše razmišljati,{" "}
            <strong>dovoljno je uzeti prvi okvirni broj</strong> koji vam padne
            na pamet. Nažalost vam ne mogu reći da bi, primjerice, bilo prirodno
            da quick sort dobije manju težinu od nekog zadatka s rekurzijom jer
            je ovo sve subjektivno i ne smijem sugerirat ni na koji način.
          </li>
          <li>
            Što se tiče estimacije vremena, iste stvari vrijede kao i za
            ocjenjivanje težine (<strong>prvi okvirni broj</strong>, bez previše
            razmišljanja). Estimacija vremena ne odnosi se na vrijeme koje bi
            vam bilo potrebno za riješiti zadatak, već na vrijeme koje bi vam
            trebalo da prođete kroz zadatak bez da ste ga znali. Dakle, to
            uključuje rješavanje zadatka te potencijalno proučavanje rješenja.
            Na primjer, zadatak koji uključuje pitanje o složenosti u prosjeku
            će zahtijevati manje vremena od nekog zadatka koji zahtijeva da se
            piše konkretan programski kod.
          </li>
          <li>
            Ocjena <strong>i samo par zadataka</strong> stvarno pomaže. Hvala!
          </li>
        </ul>
      </section>

      <section className="mt-5 rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm text-gray-800">
        <label htmlFor="email" className="mb-1 block font-medium">
          Email (opcionalno)
        </label>
        <p className="mb-3 text-xs text-gray-500">
          Unosom emaila dobivaš kod na koji se prijavljuješ. To ti omogućuje da
          sačuvaš napredak i nastaviš na drugom uređaju ili browseru, te da
          budeš kontaktiran/a za nagradu. Ako preskočiš, ostaješ anoniman/na i
          napredak se pamti samo u ovom browseru.
        </p>

        {phase === "email" && (
          <>
            <input
              id="email"
              type="email"
              inputMode="email"
              autoComplete="email"
              placeholder="ime.prezime@fer.hr"
              value={email}
              disabled={busy}
              onChange={(e) => {
                setEmail(e.target.value);
                if (error) setError(null);
              }}
              className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:border-gray-900 focus:outline-none disabled:opacity-50"
            />
            {error && <p className="mt-1 text-xs text-red-700">{error}</p>}
            <div className="mt-3 flex items-center justify-between gap-2">
              <button
                type="button"
                onClick={finishAnon}
                disabled={busy}
                className="text-xs text-gray-500 underline underline-offset-2 hover:text-gray-800 disabled:opacity-50"
              >
                Preskoči (ostani anoniman/na)
              </button>
              <button
                type="button"
                onClick={sendCode}
                disabled={busy}
                className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-black disabled:opacity-50"
              >
                {busy ? "Šaljem..." : "Pošalji kod"}
              </button>
            </div>
          </>
        )}

        {phase === "code" && (
          <>
            {info && <p className="mb-2 text-xs text-emerald-700">{info}</p>}
            <input
              id="code"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              placeholder="123456"
              value={code}
              disabled={busy}
              onChange={(e) => {
                setCode(e.target.value);
                if (error) setError(null);
              }}
              className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-center text-lg tracking-widest focus:border-gray-900 focus:outline-none disabled:opacity-50"
            />
            {error && <p className="mt-1 text-xs text-red-700">{error}</p>}
            <div className="mt-3 flex items-center justify-between gap-2">
              <button
                type="button"
                onClick={() => {
                  setPhase("email");
                  setCode("");
                  setError(null);
                  setInfo(null);
                }}
                disabled={busy}
                className="text-xs text-gray-500 underline underline-offset-2 hover:text-gray-800 disabled:opacity-50"
              >
                Natrag
              </button>
              <button
                type="button"
                onClick={verify}
                disabled={busy}
                className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-black disabled:opacity-50"
              >
                {busy ? "Provjeravam..." : "Potvrdi kod"}
              </button>
            </div>
          </>
        )}
      </section>

      {phase === "email" && (
        <div className="mt-5 flex justify-end">
          <button
            type="button"
            disabled={busy}
            onClick={finishAnon}
            className="rounded-md bg-gray-900 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-black disabled:opacity-50"
          >
            Idemo →
          </button>
        </div>
      )}
    </main>
  );
}
