import type { User } from "@supabase/supabase-js";
import { supabase } from "./supabase";

// Concurrent-call lock: bez ovoga, Odjavi handler i onAuthStateChange listener
// oba reagiraju na signOut i oba pozovu signInAnonymously paralelno. Supabase
// uslužuje jedan, drugog odbije s 422. S lockom dijele istu in-flight obecanu.
let pendingAnon: Promise<User | null> | null = null;

// Osigurava da uvijek postoji sesija. Ako nema, kreira anonimnog korisnika
// (bez signupa). Vraća trenutnog usera ili null ako anon sign-in padne.
export async function ensureSession(): Promise<User | null> {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (session?.user) return session.user;

  if (pendingAnon) return pendingAnon;

  pendingAnon = (async () => {
    try {
      const { data, error } = await supabase.auth.signInAnonymously();
      if (error) {
        console.error("Anonymous sign-in failed:", error.message);
        return null;
      }
      return data.user ?? null;
    } finally {
      pendingAnon = null;
    }
  })();
  return pendingAnon;
}

export function isAnonymous(user: User | null): boolean {
  return Boolean(user?.is_anonymous);
}

// Korisnik je "potvrđen" tek kad ima verificirani email (nije anoniman i
// email_confirmed_at je postavljen). Updaterana e-pošta bez OTP potvrde se ne
// računa kao prijava.
export function isConfirmedUser(user: User | null): boolean {
  if (!user) return false;
  if (user.is_anonymous) return false;
  return Boolean(user.email_confirmed_at);
}

// Odjavljuje trenutnog korisnika i ostavlja stranicu spremnu za fresh anon
// sesiju (ensureSession kreira novu pri sljedećem mountu / pozivu).
export async function signOut(): Promise<void> {
  await supabase.auth.signOut();
}

export type VerifyMode = "link" | "signin";

function emailAlreadyTaken(message: string): boolean {
  return /already|registered|exists|in use/i.test(message);
}

// Šalje 6-znamenkasti kod na email.
//  - "link":   trenutni (anonimni) user dobiva email -> potvrdom postaje trajan
//              i zadržava sve svoje dosadašnje ratinge.
//  - "signin": email već pripada postojećem računu -> prijava na taj račun
//              (recovery na novom browseru/uređaju).
export async function sendEmailCode(email: string): Promise<VerifyMode> {
  const { error } = await supabase.auth.updateUser({ email });
  if (!error) return "link";

  if (emailAlreadyTaken(error.message)) {
    const { error: signinErr } = await supabase.auth.signInWithOtp({
      email,
      options: { shouldCreateUser: false },
    });
    if (signinErr) throw signinErr;
    return "signin";
  }
  throw error;
}

export async function verifyEmailCode(
  email: string,
  token: string,
  mode: VerifyMode,
): Promise<User | null> {
  const type = mode === "link" ? "email_change" : "email";

  // Uvijek zapamti trenutni anon UID prije verifyOtp, neovisno o mode-u.
  // Supabase u nekim slučajevima i u "link" modu (updateUser nije erroral)
  // svejedno završi prebacivanjem sesije na postojeći račun s tim emailom,
  // pa se anon user ostavlja iza. Ako se UID promijeni nakon verifyOtp,
  // prebacujemo ratinge.
  let priorAnonId: string | null = null;
  const {
    data: { user: priorUser },
  } = await supabase.auth.getUser();
  if (priorUser?.is_anonymous) priorAnonId = priorUser.id;

  const { data, error } = await supabase.auth.verifyOtp({ email, token, type });
  if (error) throw error;

  const newUser = data.user ?? null;
  if (priorAnonId && newUser && priorAnonId !== newUser.id) {
    await migrateRatings(priorAnonId);
  }
  return newUser;
}

// Prebacuje ratinge s napuštenog anonimnog usera na trenutno prijavljenog.
// Atomski Postgres RPC: insert with ON CONFLICT DO NOTHING + delete starih
// anon redaka, da ne ostanu duplikati pod mrtvim UID-om.
async function migrateRatings(fromUid: string): Promise<void> {
  const { data, error } = await supabase.rpc("merge_anon_ratings", {
    p_anon_uid: fromUid,
  });
  if (error) {
    console.error("merge_anon_ratings failed:", error.message);
    return;
  }
  console.info("merge_anon_ratings ok, inserted:", data);
}
