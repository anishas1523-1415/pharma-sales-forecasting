-- recommendation_acknowledgments
-- Backs the "acknowledge/dismiss" state on the Recommendations page.
-- Previously localStorage-only (single device, no real identity); this
-- makes it real, per-user, server-side state, secured by Row Level
-- Security rather than by trusting the client.

create table public.recommendation_acknowledgments (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade not null,
  category text not null,
  signal text not null,
  acknowledged_at timestamptz not null default now(),
  unique (user_id, category, signal)
);

alter table public.recommendation_acknowledgments enable row level security;

create policy "Users can view their own acknowledgments"
  on public.recommendation_acknowledgments for select
  using (auth.uid() = user_id);

create policy "Users can insert their own acknowledgments"
  on public.recommendation_acknowledgments for insert
  with check (auth.uid() = user_id);

create policy "Users can delete their own acknowledgments"
  on public.recommendation_acknowledgments for delete
  using (auth.uid() = user_id);
