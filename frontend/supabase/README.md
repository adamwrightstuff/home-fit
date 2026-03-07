# Supabase setup

## Create the `saved_scores` table

Save (My places) will fail with **"Could not find the table 'public.saved_scores' in the schema cache"** until the table exists and Supabase has picked it up.

### 1. Run the migration

1. Open [Supabase Dashboard](https://supabase.com/dashboard) and select the **same project** your app uses (check `NEXT_PUBLIC_SUPABASE_URL` in `.env.local`).
2. Go to **SQL Editor** → **New query**.
3. Copy the **entire** contents of `migrations/001_saved_scores.sql` from this repo, paste into the editor, and click **Run**.
4. Confirm you see "Success. No rows returned" (or similar).

### 2. Confirm the table exists

- In the left sidebar open **Table Editor**. You should see **`saved_scores`** under the `public` schema.
- If you don't see it, the SQL may have run in a different project or failed silently; run it again and check for red error text.

### 3. If the error persists

- **Reload schema cache:** In SQL Editor run: `NOTIFY pgrst, 'reload schema';` then try **Save this place** again (works within seconds).
- **Schema cache (alternative):** After creating the table, wait 30-60 seconds and retry.
- **Same project:** Ensure the app's Supabase URL is the project where you ran the SQL (Dashboard → Project Settings → API → Project URL should match `NEXT_PUBLIC_SUPABASE_URL`).
- **Policies:** The migration creates RLS policies. If you edited them or the table was created by hand, re-run the full `001_saved_scores.sql` script (it now ends with `NOTIFY pgrst, 'reload schema';` so the API picks up the table).

After the table exists and the cache has updated, sign in and **Save this place** should work.
