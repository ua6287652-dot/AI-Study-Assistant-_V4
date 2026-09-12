
-- AI Study Assistant V4 - Supabase schema
-- Run this in Supabase SQL Editor.

create extension if not exists pgcrypto;

create table if not exists public.materials (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null,
  pages integer default 0,
  words integer default 0,
  text_content text not null,
  storage_path text,
  created_at timestamptz default now()
);

create table if not exists public.topics (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  material_id uuid references public.materials(id) on delete cascade,
  name text not null,
  description text default '',
  created_at timestamptz default now()
);

create table if not exists public.quiz_attempts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  material_id uuid references public.materials(id) on delete set null,
  topic text not null,
  score integer not null,
  total integer not null,
  difficulty text,
  created_at timestamptz default now()
);

create table if not exists public.weak_topics (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  topic text not null,
  score numeric default 0,
  attempts integer default 0,
  updated_at timestamptz default now(),
  unique(user_id, topic)
);

alter table public.materials enable row level security;
alter table public.topics enable row level security;
alter table public.quiz_attempts enable row level security;
alter table public.weak_topics enable row level security;

drop policy if exists "materials_owner_select" on public.materials;
drop policy if exists "materials_owner_insert" on public.materials;
drop policy if exists "materials_owner_delete" on public.materials;
create policy "materials_owner_select" on public.materials for select using (auth.uid() = user_id);
create policy "materials_owner_insert" on public.materials for insert with check (auth.uid() = user_id);
create policy "materials_owner_delete" on public.materials for delete using (auth.uid() = user_id);

drop policy if exists "topics_owner_all" on public.topics;
create policy "topics_owner_all" on public.topics for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "quiz_owner_all" on public.quiz_attempts;
create policy "quiz_owner_all" on public.quiz_attempts for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "weak_owner_all" on public.weak_topics;
create policy "weak_owner_all" on public.weak_topics for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- Private storage bucket for original PDFs.
insert into storage.buckets (id, name, public)
values ('study-materials', 'study-materials', false)
on conflict (id) do nothing;

drop policy if exists "study_materials_insert_own_folder" on storage.objects;
drop policy if exists "study_materials_select_own_folder" on storage.objects;
drop policy if exists "study_materials_delete_own_folder" on storage.objects;

create policy "study_materials_insert_own_folder"
on storage.objects for insert to authenticated
with check (bucket_id = 'study-materials' and (storage.foldername(name))[1] = (select auth.uid()::text));

create policy "study_materials_select_own_folder"
on storage.objects for select to authenticated
using (bucket_id = 'study-materials' and (storage.foldername(name))[1] = (select auth.uid()::text));

create policy "study_materials_delete_own_folder"
on storage.objects for delete to authenticated
using (bucket_id = 'study-materials' and (storage.foldername(name))[1] = (select auth.uid()::text));
