insert into public.authority_corpora (
  version, jurisdiction, name, scope_statement, content_hash, source_status, is_active
) values (
  'sg-employment-restraints-2026.09-pilot.1',
  'Singapore',
  'Singapore employment restraints pilot',
  'Selected Singapore employment restraint-of-trade propositions. Not a comprehensive case-law database.',
  '30e24f3bbc0281f5a99a4f14b44d479f531c79dfd93b3b34380aa77886895fb4',
  'gold_fixture',
  false
) on conflict (version) do nothing;

insert into public.authorities (
  corpus_id, canonical_citation, normalised_citation_key, case_name, court,
  decision_date, official_url, source_status
) values
  ((select id from public.authority_corpora where version = 'sg-employment-restraints-2026.09-pilot.1'), '[2007] SGCA 53', '2007SGCA53', 'Man Financial (S) Pte Ltd v Wong Bark Chuan David', 'Court of Appeal', '2007-11-30', 'https://www.elitigation.sg/gdviewer/s/2007_SGCA_53', 'gold_fixture'),
  ((select id from public.authority_corpora where version = 'sg-employment-restraints-2026.09-pilot.1'), '[2010] SGCA 3', '2010SGCA3', 'CLAAS Medical Centre Pte Ltd v Ng Boon Ching', 'Court of Appeal', '2010-01-28', 'https://www.elitigation.sg/gd/s/2010_SGCA_3', 'gold_fixture'),
  ((select id from public.authority_corpora where version = 'sg-employment-restraints-2026.09-pilot.1'), '[2019] SGHC 96', '2019SGHC96', 'HT SRL v Wee Shuo Woon', 'High Court', '2019-04-16', 'https://www.elitigation.sg/gdviewer/s/2019_SGHC_96', 'gold_fixture'),
  ((select id from public.authority_corpora where version = 'sg-employment-restraints-2026.09-pilot.1'), '[2024] SGHC 29', '2024SGHC29', 'Shopee Singapore Pte Ltd v Lim Teck Yong', 'High Court', '2024-02-01', 'https://www.elitigation.sg/gdviewer/s/2024_SGHC_29', 'gold_fixture')
on conflict (corpus_id, normalised_citation_key) do nothing;

-- Deliberately no authority_passages or negative-registry fixtures are seeded.
-- Exact judgment text must enter through the source-hashed official refresh
-- pipeline. A missing passage or negative check must fail loudly instead of
-- being replaced with a paraphrase or synthetic citation.
