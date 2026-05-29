import type { User } from "@supabase/supabase-js";
import { supabase } from "./supabase";

// Osigurava da uvijek postoji sesija. Ako nema, kreira anonimnog korisnika
// (bez signupa). Vraća trenutnog usera ili null ako anon sign-in padne.
export async function ensureSession(): Promise<User | null> {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (session?.user) return session.user;

  const { data, error } = await supabase.auth.signInAnonymously();
  if (error) {
    console.error("Anonymous sign-in failed:", error.message);
    return null;
  }
  return data.user ?? null;
}

export function isAnonymous(user: User | null): boolean {
  return Boolean(user?.is_anonymous);
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

  // U "signin" modu prelazimo na postojeći račun, pa anonimni user ostaje iza.
  // Zapamti njegov id prije prebacivanja da prebacimo njegove ratinge.
  let priorAnonId: string | null = null;
  if (mode === "signin") {
    const {
      data: { user },
    } = await supabase.auth.getUser();
    if (user?.is_anonymous) priorAnonId = user.id;
  }

  const { data, error } = await supabase.auth.verifyOtp({ email, token, type });
  if (error) throw error;

  const newUser = data.user ?? null;
  if (priorAnonId && newUser && priorAnonId !== newUser.id) {
    await migrateRatings(priorAnonId, newUser.id);
  }
  return newUser;
}

// Prebacuje ratinge s napuštenog anonimnog usera na račun u koji se korisnik
// upravo prijavio. Duplikati (zadatak već ocijenjen na tom računu) se preskaču.
async function migrateRatings(fromUid: string, toUid: string): Promise<void> {
  const { data, error } = await supabase
    .from("ratings")
    .select("task_id, difficulty, time_est_minutes")
    .eq("rater_uuid", fromUid);
  if (error || !data || data.length === 0) return;

  const rows = data.map((r) => ({
    task_id: r.task_id,
    rater_uuid: toUid,
    difficulty: r.difficulty,
    time_est_minutes: r.time_est_minutes,
  }));

  await supabase
    .from("ratings")
    .upsert(rows, { onConflict: "task_id,rater_uuid", ignoreDuplicates: true });
}
