-- Synthetic local identities only. Password login is not used by the fixture API.
insert into auth.users (
  instance_id, id, aud, role, email, encrypted_password, email_confirmed_at,
  raw_app_meta_data, raw_user_meta_data, created_at, updated_at,
  confirmation_token, recovery_token, email_change_token_new, email_change
)
values
  ('00000000-0000-0000-0000-000000000000', 'aaaaaaaa-0000-4000-8000-000000000001', 'authenticated', 'authenticated', 'admin@vouch.test', crypt('fixture-only', gen_salt('bf')), now(), '{"provider":"email","providers":["email"]}', '{}', now(), now(), '', '', '', ''),
  ('00000000-0000-0000-0000-000000000000', 'aaaaaaaa-0000-4000-8000-000000000002', 'authenticated', 'authenticated', 'marketer@vouch.test', crypt('fixture-only', gen_salt('bf')), now(), '{"provider":"email","providers":["email"]}', '{}', now(), now(), '', '', '', ''),
  ('00000000-0000-0000-0000-000000000000', 'aaaaaaaa-0000-4000-8000-000000000003', 'authenticated', 'authenticated', 'reviewer@vouch.test', crypt('fixture-only', gen_salt('bf')), now(), '{"provider":"email","providers":["email"]}', '{}', now(), now(), '', '', '', ''),
  ('00000000-0000-0000-0000-000000000000', 'aaaaaaaa-0000-4000-8000-000000000004', 'authenticated', 'authenticated', 'viewer@vouch.test', crypt('fixture-only', gen_salt('bf')), now(), '{"provider":"email","providers":["email"]}', '{}', now(), now(), '', '', '', ''),
  ('00000000-0000-0000-0000-000000000000', 'bbbbbbbb-0000-4000-8000-000000000001', 'authenticated', 'authenticated', 'beta@vouch.test', crypt('fixture-only', gen_salt('bf')), now(), '{"provider":"email","providers":["email"]}', '{}', now(), now(), '', '', '', '')
on conflict (id) do nothing;

insert into public.organizations (id, name, slug, created_by)
values
  ('11111111-1111-4111-8111-111111111111', 'Acme Eyewear', 'acme-eyewear', 'aaaaaaaa-0000-4000-8000-000000000001'),
  ('22222222-2222-4222-8222-222222222222', 'Beta Outdoors', 'beta-outdoors', 'bbbbbbbb-0000-4000-8000-000000000001')
on conflict (id) do nothing;

insert into public.memberships (id, organization_id, user_id, status)
values
  ('aaaaaaaa-1000-4000-8000-000000000001', '11111111-1111-4111-8111-111111111111', 'aaaaaaaa-0000-4000-8000-000000000001', 'active'),
  ('aaaaaaaa-1000-4000-8000-000000000002', '11111111-1111-4111-8111-111111111111', 'aaaaaaaa-0000-4000-8000-000000000002', 'active'),
  ('aaaaaaaa-1000-4000-8000-000000000003', '11111111-1111-4111-8111-111111111111', 'aaaaaaaa-0000-4000-8000-000000000003', 'active'),
  ('aaaaaaaa-1000-4000-8000-000000000004', '11111111-1111-4111-8111-111111111111', 'aaaaaaaa-0000-4000-8000-000000000004', 'active'),
  ('bbbbbbbb-1000-4000-8000-000000000001', '22222222-2222-4222-8222-222222222222', 'bbbbbbbb-0000-4000-8000-000000000001', 'active')
on conflict (id) do nothing;

insert into public.membership_roles (organization_id, membership_id, role, granted_by)
values
  ('11111111-1111-4111-8111-111111111111', 'aaaaaaaa-1000-4000-8000-000000000001', 'admin', 'aaaaaaaa-0000-4000-8000-000000000001'),
  ('11111111-1111-4111-8111-111111111111', 'aaaaaaaa-1000-4000-8000-000000000002', 'marketer', 'aaaaaaaa-0000-4000-8000-000000000001'),
  ('11111111-1111-4111-8111-111111111111', 'aaaaaaaa-1000-4000-8000-000000000003', 'reviewer', 'aaaaaaaa-0000-4000-8000-000000000001'),
  ('11111111-1111-4111-8111-111111111111', 'aaaaaaaa-1000-4000-8000-000000000004', 'viewer', 'aaaaaaaa-0000-4000-8000-000000000001'),
  ('22222222-2222-4222-8222-222222222222', 'bbbbbbbb-1000-4000-8000-000000000001', 'marketer', 'bbbbbbbb-0000-4000-8000-000000000001')
on conflict do nothing;

insert into public.brands (id, organization_id, name)
values
  ('10000000-0000-4000-8000-000000000001', '11111111-1111-4111-8111-111111111111', 'Acme Eyewear'),
  ('20000000-0000-4000-8000-000000000001', '22222222-2222-4222-8222-222222222222', 'Beta Outdoors')
on conflict (id) do nothing;
