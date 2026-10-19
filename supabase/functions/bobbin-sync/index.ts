// Zgodny z npoint endpoint synchronizacji dla index_bobina_migracja.html.
// Wdrożenie: supabase functions deploy bobbin-sync --no-verify-jwt
// Nie umieszczaj SUPABASE_SERVICE_ROLE_KEY w HTML — jest dostępny wyłącznie
// jako sekret środowiskowy Edge Function.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const STATE_KEY = "operational_json:rozliczenie_bobin.json";
const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Cache-Control": "no-store",
};

const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json; charset=utf-8" },
  });

const emptyState = {
  format: "system-produkcji/bobbin-settlement",
  version: 1,
  data: { orders: [], entries: [], settings: {} },
  sync: { users: [], log: [], deleted_users: [], deleted_entries: [], deleted_orders: [], cfg_updated: 0, last_modified: "—" },
};

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response(null, { headers: corsHeaders });
  if (request.method !== "GET" && request.method !== "POST") return response({ error: "Method not allowed" }, 405);

  const url = Deno.env.get("SUPABASE_URL");
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!url || !serviceRoleKey) return response({ error: "Function is not configured" }, 500);
  const supabase = createClient(url, serviceRoleKey, { auth: { persistSession: false } });

  if (request.method === "GET") {
    const { data, error } = await supabase.from("application_state")
      .select("payload").eq("state_key", STATE_KEY).maybeSingle();
    if (error) return response({ error: "Storage read failed" }, 500);
    return response(data?.payload ?? emptyState);
  }

  let payload: unknown;
  try { payload = await request.json(); } catch { return response({ error: "Invalid JSON" }, 400); }
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) return response({ error: "Invalid module state" }, 400);
  const state = payload as Record<string, unknown>;
  if (state.format !== "system-produkcji/bobbin-settlement" || state.version !== 1) {
    return response({ error: "Unsupported module state" }, 400);
  }
  const { error } = await supabase.from("application_state").upsert(
    { state_key: STATE_KEY, payload: state, updated_at: new Date().toISOString() },
    { onConflict: "state_key" },
  );
  if (error) return response({ error: "Storage write failed" }, 500);
  return response({ ok: true });
});
