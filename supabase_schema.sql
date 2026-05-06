create table if not exists public.app_users (
    username text primary key,
    password_hash text not null,
    role text not null default 'user' check (role in ('admin', 'user')),
    active boolean not null default true,
    created_at timestamptz not null default now()
);

alter table public.app_users enable row level security;
