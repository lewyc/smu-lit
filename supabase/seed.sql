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

insert into public.authority_passages (
  authority_id, external_id, paragraph_label, passage_text, supported_propositions, limitations
) values
  ((select id from public.authorities where normalised_citation_key = '2007SGCA53'), 'man-70', '[70]', 'A restraint must protect a legitimate proprietary interest before its reasonableness is considered.', array['legitimate_proprietary_interest'], array['Two-stage inquiry; enforceability remains fact-sensitive.']),
  ((select id from public.authorities where normalised_citation_key = '2007SGCA53'), 'man-74', '[74]', 'Reasonableness is assessed both between the contracting parties and with reference to the public interest.', array['reasonableness_between_parties','reasonableness_public_interest'], array['No single factor determines reasonableness.']),
  ((select id from public.authorities where normalised_citation_key = '2010SGCA3'), 'claas-59', '[59]-[60]', 'A Singapore-wide geographic restraint was not unreasonable on the particular evidence concerning the clinic patient goodwill.', array['geographic_scope','customer_connections'], array['Conclusion depended on the nature and geographic reach of the goodwill.','It does not establish that every Singapore-wide restraint is reasonable.']),
  ((select id from public.authorities where normalised_citation_key = '2010SGCA3'), 'claas-61', '[61]', 'Reasonableness is assessed in the circumstances existing when the parties entered the covenant.', array['reasonableness_between_parties','duration_scope'], array['Duration remains fact-sensitive.']),
  ((select id from public.authorities where normalised_citation_key = '2019SGHC96'), 'ht-82', '[82]-[84]', 'The activity prohibition, lack of geographic limit, and one-year duration were assessed together and found unreasonable on those facts.', array['activity_scope','geographic_scope','duration_scope'], array['Fact-specific result; it is not an automatic rule for all worldwide restraints.','The clause combined breadth mattered.']),
  ((select id from public.authorities where normalised_citation_key = '2024SGHC29'), 'shopee-18', '[18]', 'Employment restraint clauses are prima facie void and unenforceable unless the restraint-of-trade requirements are satisfied.', array['prima_facie_unenforceable'], array['Prima facie is not the same as automatically or invariably void.']),
  ((select id from public.authorities where normalised_citation_key = '2024SGHC29'), 'shopee-27', '[27]-[29]', 'Recognised interests may include trade secrets, trade connections, and maintaining a stable and trained workforce.', array['confidential_information','customer_connections','stable_trained_workforce','legitimate_proprietary_interest'], array['The asserted interest must exist on the facts and fit the clause.'])
on conflict (external_id) do nothing;

insert into public.citation_registry_checks (
  corpus_id, citation_string, normalised_citation_key, authority_exists,
  official_source_url, checker, verification_note, checked_at
) values (
  (select id from public.authority_corpora where version = 'sg-employment-restraints-2026.09-pilot.1'),
  '[2099] SGCA 999',
  '2099SGCA999',
  false,
  'https://www.elitigation.sg/gd/',
  'ProofMark adversarial-fixture curator',
  'Future-dated adversarial fixture; re-run an official registry search before non-demo use.',
  '2026-09-05T00:00:00+08:00'
) on conflict (corpus_id, normalised_citation_key, checked_at) do nothing;
