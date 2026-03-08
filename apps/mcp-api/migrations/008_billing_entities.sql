create table if not exists billing_contacts (
  project_id text primary key references projects(id) on delete cascade,
  email text null,
  tax_id text null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists billing_payment_methods (
  payment_method_id text primary key,
  project_id text not null references projects(id) on delete cascade,
  brand text not null,
  last4 text not null,
  exp_month smallint not null,
  exp_year smallint not null,
  is_default boolean not null default true,
  created_at timestamptz not null default now()
);

create index if not exists idx_billing_payment_methods_project_id
  on billing_payment_methods (project_id);

create unique index if not exists idx_billing_payment_methods_default_per_project
  on billing_payment_methods (project_id)
  where is_default = true;

create table if not exists billing_invoices (
  invoice_id text primary key,
  project_id text not null references projects(id) on delete cascade,
  invoice_date timestamptz not null,
  description text not null,
  amount_cents integer not null,
  currency text not null default 'usd',
  status text not null check (status in ('paid', 'open', 'void', 'failed')),
  pdf_url text null,
  created_at timestamptz not null default now()
);

create index if not exists idx_billing_invoices_project_id_date_desc
  on billing_invoices (project_id, invoice_date desc);
