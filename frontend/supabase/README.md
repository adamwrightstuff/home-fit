# Supabase setup

## Create the `saved_scores` table

Save (My places) will fail with **"Could not find the table 'public.saved_scores' in the schema cache"** until the table exists in your Supabase project.

**Run the migration once per Supabase project:**

1. Open [Supabase Dashboard](https://supabase.com/dashboard) and select your project.
2. Go to **SQL Editor**.
3. Open `migrations/001_saved_scores.sql` in this repo, copy its contents, paste into the SQL Editor, and click **Run**.

That creates the `saved_scores` table, indexes, RLS policies, and the `updated_at` trigger. After it runs successfully, sign in and **Save this place** will work.
