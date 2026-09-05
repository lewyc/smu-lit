


SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;


CREATE SCHEMA IF NOT EXISTS "public";


ALTER SCHEMA "public" OWNER TO "pg_database_owner";


COMMENT ON SCHEMA "public" IS 'standard public schema';


SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "public"."audit_claims" (
    "id" bigint NOT NULL,
    "audit_run_id" bigint NOT NULL,
    "claim_order" bigint NOT NULL,
    "claim_text" "text" NOT NULL,
    "citation" "text",
    "pinpoint" "text",
    "proposition_code" "text" NOT NULL,
    "parser_confidence" numeric(4,3) NOT NULL,
    "parser_used" "text" NOT NULL,
    "verdict" "text" NOT NULL,
    "rationale" "text" NOT NULL,
    "missing_evidence" "text",
    "escalation_required" boolean NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "audit_claims_claim_order_check" CHECK (("claim_order" > 0)),
    CONSTRAINT "audit_claims_parser_confidence_check" CHECK ((("parser_confidence" >= (0)::numeric) AND ("parser_confidence" <= (1)::numeric))),
    CONSTRAINT "audit_claims_parser_used_check" CHECK (("parser_used" = ANY (ARRAY['local'::"text", 'gemini'::"text"]))),
    CONSTRAINT "audit_claims_verdict_check" CHECK (("verdict" = ANY (ARRAY['verified'::"text", 'context_review'::"text", 'unsupported'::"text", 'likely_fabricated'::"text", 'unverified'::"text", 'out_of_scope'::"text"])))
);


ALTER TABLE "public"."audit_claims" OWNER TO "postgres";


ALTER TABLE "public"."audit_claims" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."audit_claims_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."audit_events" (
    "id" bigint NOT NULL,
    "audit_run_id" bigint NOT NULL,
    "event_type" "text" NOT NULL,
    "event_payload" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "audit_events_event_type_check" CHECK (("event_type" = ANY (ARRAY['queued'::"text", 'running'::"text", 'complete'::"text", 'failed'::"text"])))
);


ALTER TABLE "public"."audit_events" OWNER TO "postgres";


ALTER TABLE "public"."audit_events" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."audit_events_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."audit_runs" (
    "id" bigint NOT NULL,
    "public_id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "organisation_id" bigint NOT NULL,
    "created_by" "uuid" NOT NULL,
    "input_text" "text" NOT NULL,
    "status" "text" NOT NULL,
    "corpus_version" "text" NOT NULL,
    "engine_version" "text" NOT NULL,
    "parser_mode" "text" NOT NULL,
    "processing_duration_ms" numeric(12,3),
    "summary_metrics" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "summary_counts" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "result_payload" "jsonb",
    "failure_code" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "started_at" timestamp with time zone,
    "completed_at" timestamp with time zone,
    CONSTRAINT "audit_runs_check" CHECK ((("status" <> 'complete'::"text") OR ("completed_at" IS NOT NULL))),
    CONSTRAINT "audit_runs_check1" CHECK ((("status" <> 'failed'::"text") OR ("failure_code" IS NOT NULL))),
    CONSTRAINT "audit_runs_input_text_check" CHECK ((("char_length"("input_text") >= 1) AND ("char_length"("input_text") <= 20000))),
    CONSTRAINT "audit_runs_parser_mode_check" CHECK (("parser_mode" = ANY (ARRAY['local'::"text", 'gemini'::"text"]))),
    CONSTRAINT "audit_runs_processing_duration_ms_check" CHECK (("processing_duration_ms" >= (0)::numeric)),
    CONSTRAINT "audit_runs_status_check" CHECK (("status" = ANY (ARRAY['queued'::"text", 'running'::"text", 'complete'::"text", 'failed'::"text"])))
);


ALTER TABLE "public"."audit_runs" OWNER TO "postgres";


ALTER TABLE "public"."audit_runs" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."audit_runs_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."authorities" (
    "id" bigint NOT NULL,
    "corpus_id" bigint NOT NULL,
    "canonical_citation" "text" NOT NULL,
    "normalised_citation_key" "text" NOT NULL,
    "case_name" "text" NOT NULL,
    "court" "text" NOT NULL,
    "decision_date" "date" NOT NULL,
    "official_url" "text" NOT NULL,
    "source_status" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "authorities_official_url_check" CHECK (("official_url" ~~ 'https://%'::"text")),
    CONSTRAINT "authorities_source_status_check" CHECK (("source_status" = ANY (ARRAY['research_verified'::"text", 'verification_required'::"text"])))
);


ALTER TABLE "public"."authorities" OWNER TO "postgres";


ALTER TABLE "public"."authorities" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."authorities_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."authority_corpora" (
    "id" bigint NOT NULL,
    "version" "text" NOT NULL,
    "jurisdiction" "text" NOT NULL,
    "name" "text" NOT NULL,
    "scope_statement" "text" NOT NULL,
    "content_hash" "text" NOT NULL,
    "source_status" "text" NOT NULL,
    "is_active" boolean DEFAULT false NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "authority_corpora_content_hash_check" CHECK (("length"("content_hash") = 64)),
    CONSTRAINT "authority_corpora_source_status_check" CHECK (("source_status" = ANY (ARRAY['research_verified'::"text", 'verification_required'::"text"])))
);


ALTER TABLE "public"."authority_corpora" OWNER TO "postgres";


ALTER TABLE "public"."authority_corpora" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."authority_corpora_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."authority_passages" (
    "id" bigint NOT NULL,
    "authority_id" bigint NOT NULL,
    "external_id" "text" NOT NULL,
    "paragraph_label" "text" NOT NULL,
    "passage_text" "text" NOT NULL,
    "supported_propositions" "text"[] DEFAULT '{}'::"text"[] NOT NULL,
    "limitations" "text"[] DEFAULT '{}'::"text"[] NOT NULL,
    "search_vector" "tsvector" GENERATED ALWAYS AS ("to_tsvector"('"english"'::"regconfig", ((COALESCE("passage_text", ''::"text") || ' '::"text") || COALESCE("paragraph_label", ''::"text")))) STORED,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."authority_passages" OWNER TO "postgres";


ALTER TABLE "public"."authority_passages" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."authority_passages_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."benchmark_runs" (
    "id" bigint NOT NULL,
    "organisation_id" bigint NOT NULL,
    "created_by" "uuid" NOT NULL,
    "fixture_count" bigint NOT NULL,
    "correct_count" bigint NOT NULL,
    "verdict_accuracy" numeric(6,3) NOT NULL,
    "p50_latency_ms" numeric(12,3) NOT NULL,
    "p95_latency_ms" numeric(12,3) NOT NULL,
    "cache_hit_rate" numeric(6,3),
    "engine_version" "text" NOT NULL,
    "corpus_version" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "benchmark_runs_cache_hit_rate_check" CHECK ((("cache_hit_rate" >= (0)::numeric) AND ("cache_hit_rate" <= (100)::numeric))),
    CONSTRAINT "benchmark_runs_check" CHECK ((("correct_count" >= 0) AND ("correct_count" <= "fixture_count"))),
    CONSTRAINT "benchmark_runs_fixture_count_check" CHECK (("fixture_count" > 0)),
    CONSTRAINT "benchmark_runs_p50_latency_ms_check" CHECK (("p50_latency_ms" >= (0)::numeric)),
    CONSTRAINT "benchmark_runs_p95_latency_ms_check" CHECK (("p95_latency_ms" >= (0)::numeric)),
    CONSTRAINT "benchmark_runs_verdict_accuracy_check" CHECK ((("verdict_accuracy" >= (0)::numeric) AND ("verdict_accuracy" <= (100)::numeric)))
);


ALTER TABLE "public"."benchmark_runs" OWNER TO "postgres";


ALTER TABLE "public"."benchmark_runs" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."benchmark_runs_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."citation_registry_checks" (
    "id" bigint NOT NULL,
    "corpus_id" bigint NOT NULL,
    "citation_string" "text" NOT NULL,
    "normalised_citation_key" "text" NOT NULL,
    "authority_exists" boolean NOT NULL,
    "official_source_url" "text" NOT NULL,
    "checker" "text" NOT NULL,
    "verification_note" "text",
    "checked_at" timestamp with time zone NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "citation_registry_checks_official_source_url_check" CHECK (("official_source_url" ~~ 'https://%'::"text"))
);


ALTER TABLE "public"."citation_registry_checks" OWNER TO "postgres";


ALTER TABLE "public"."citation_registry_checks" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."citation_registry_checks_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."claim_evidence" (
    "id" bigint NOT NULL,
    "audit_claim_id" bigint NOT NULL,
    "passage_external_id" "text" NOT NULL,
    "support_type" "text" NOT NULL,
    "ranking_score" numeric(6,5) NOT NULL,
    "evidence_explanation" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "claim_evidence_ranking_score_check" CHECK ((("ranking_score" >= (0)::numeric) AND ("ranking_score" <= (1)::numeric))),
    CONSTRAINT "claim_evidence_support_type_check" CHECK (("support_type" = ANY (ARRAY['supports'::"text", 'limits'::"text", 'contradicts'::"text", 'unresolved'::"text"])))
);


ALTER TABLE "public"."claim_evidence" OWNER TO "postgres";


ALTER TABLE "public"."claim_evidence" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."claim_evidence_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."handoff_briefs" (
    "id" bigint NOT NULL,
    "audit_run_id" bigint NOT NULL,
    "issue" "text" NOT NULL,
    "established_facts" "text"[] DEFAULT '{}'::"text"[] NOT NULL,
    "relevant_authorities" "text"[] DEFAULT '{}'::"text"[] NOT NULL,
    "unresolved_questions" "text"[] DEFAULT '{}'::"text"[] NOT NULL,
    "review_status" "text" NOT NULL,
    "reviewed_by" "uuid",
    "reviewed_at" timestamp with time zone,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "handoff_briefs_review_status_check" CHECK (("review_status" = ANY (ARRAY['lawyer_review_required'::"text", 'ready'::"text", 'reviewed'::"text"])))
);


ALTER TABLE "public"."handoff_briefs" OWNER TO "postgres";


ALTER TABLE "public"."handoff_briefs" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."handoff_briefs_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."organisation_members" (
    "id" bigint NOT NULL,
    "organisation_id" bigint NOT NULL,
    "user_id" "uuid" NOT NULL,
    "role" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "organisation_members_role_check" CHECK (("role" = ANY (ARRAY['owner'::"text", 'reviewer'::"text", 'member'::"text"])))
);


ALTER TABLE "public"."organisation_members" OWNER TO "postgres";


ALTER TABLE "public"."organisation_members" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."organisation_members_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."organisations" (
    "id" bigint NOT NULL,
    "name" "text" NOT NULL,
    "slug" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "organisations_slug_check" CHECK (("slug" = "lower"("slug")))
);


ALTER TABLE "public"."organisations" OWNER TO "postgres";


ALTER TABLE "public"."organisations" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."organisations_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



ALTER TABLE ONLY "public"."audit_claims"
    ADD CONSTRAINT "audit_claims_audit_run_id_claim_order_key" UNIQUE ("audit_run_id", "claim_order");



ALTER TABLE ONLY "public"."audit_claims"
    ADD CONSTRAINT "audit_claims_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."audit_events"
    ADD CONSTRAINT "audit_events_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."audit_runs"
    ADD CONSTRAINT "audit_runs_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."audit_runs"
    ADD CONSTRAINT "audit_runs_public_id_key" UNIQUE ("public_id");



ALTER TABLE ONLY "public"."authorities"
    ADD CONSTRAINT "authorities_corpus_id_normalised_citation_key_key" UNIQUE ("corpus_id", "normalised_citation_key");



ALTER TABLE ONLY "public"."authorities"
    ADD CONSTRAINT "authorities_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."authority_corpora"
    ADD CONSTRAINT "authority_corpora_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."authority_corpora"
    ADD CONSTRAINT "authority_corpora_version_key" UNIQUE ("version");



ALTER TABLE ONLY "public"."authority_passages"
    ADD CONSTRAINT "authority_passages_authority_id_paragraph_label_key" UNIQUE ("authority_id", "paragraph_label");



ALTER TABLE ONLY "public"."authority_passages"
    ADD CONSTRAINT "authority_passages_external_id_key" UNIQUE ("external_id");



ALTER TABLE ONLY "public"."authority_passages"
    ADD CONSTRAINT "authority_passages_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."benchmark_runs"
    ADD CONSTRAINT "benchmark_runs_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."citation_registry_checks"
    ADD CONSTRAINT "citation_registry_checks_corpus_id_normalised_citation_key__key" UNIQUE ("corpus_id", "normalised_citation_key", "checked_at");



ALTER TABLE ONLY "public"."citation_registry_checks"
    ADD CONSTRAINT "citation_registry_checks_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."claim_evidence"
    ADD CONSTRAINT "claim_evidence_audit_claim_id_passage_external_id_support_t_key" UNIQUE ("audit_claim_id", "passage_external_id", "support_type");



ALTER TABLE ONLY "public"."claim_evidence"
    ADD CONSTRAINT "claim_evidence_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."handoff_briefs"
    ADD CONSTRAINT "handoff_briefs_audit_run_id_key" UNIQUE ("audit_run_id");



ALTER TABLE ONLY "public"."handoff_briefs"
    ADD CONSTRAINT "handoff_briefs_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."organisation_members"
    ADD CONSTRAINT "organisation_members_organisation_id_user_id_key" UNIQUE ("organisation_id", "user_id");



ALTER TABLE ONLY "public"."organisation_members"
    ADD CONSTRAINT "organisation_members_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."organisations"
    ADD CONSTRAINT "organisations_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."organisations"
    ADD CONSTRAINT "organisations_slug_key" UNIQUE ("slug");



CREATE INDEX "audit_claims_run_order_idx" ON "public"."audit_claims" USING "btree" ("audit_run_id", "claim_order");



CREATE INDEX "audit_events_run_created_idx" ON "public"."audit_events" USING "btree" ("audit_run_id", "created_at");



CREATE INDEX "audit_runs_active_idx" ON "public"."audit_runs" USING "btree" ("created_at") WHERE ("status" = ANY (ARRAY['queued'::"text", 'running'::"text"]));



CREATE INDEX "audit_runs_created_by_idx" ON "public"."audit_runs" USING "btree" ("created_by");



CREATE INDEX "audit_runs_org_created_idx" ON "public"."audit_runs" USING "btree" ("organisation_id", "created_at" DESC);



CREATE INDEX "authorities_corpus_id_idx" ON "public"."authorities" USING "btree" ("corpus_id");



CREATE UNIQUE INDEX "authority_corpora_one_active_idx" ON "public"."authority_corpora" USING "btree" ("is_active") WHERE "is_active";



CREATE INDEX "authority_passages_authority_id_idx" ON "public"."authority_passages" USING "btree" ("authority_id");



CREATE INDEX "authority_passages_search_idx" ON "public"."authority_passages" USING "gin" ("search_vector");



CREATE INDEX "benchmark_runs_created_by_idx" ON "public"."benchmark_runs" USING "btree" ("created_by");



CREATE INDEX "benchmark_runs_org_created_idx" ON "public"."benchmark_runs" USING "btree" ("organisation_id", "created_at" DESC);



CREATE INDEX "citation_registry_checks_corpus_id_idx" ON "public"."citation_registry_checks" USING "btree" ("corpus_id");



CREATE INDEX "claim_evidence_claim_idx" ON "public"."claim_evidence" USING "btree" ("audit_claim_id");



CREATE INDEX "claim_evidence_passage_idx" ON "public"."claim_evidence" USING "btree" ("passage_external_id");



CREATE INDEX "handoff_briefs_reviewed_by_idx" ON "public"."handoff_briefs" USING "btree" ("reviewed_by") WHERE ("reviewed_by" IS NOT NULL);



CREATE INDEX "organisation_members_organisation_id_idx" ON "public"."organisation_members" USING "btree" ("organisation_id");



CREATE INDEX "organisation_members_user_id_idx" ON "public"."organisation_members" USING "btree" ("user_id");



ALTER TABLE ONLY "public"."audit_claims"
    ADD CONSTRAINT "audit_claims_audit_run_id_fkey" FOREIGN KEY ("audit_run_id") REFERENCES "public"."audit_runs"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."audit_events"
    ADD CONSTRAINT "audit_events_audit_run_id_fkey" FOREIGN KEY ("audit_run_id") REFERENCES "public"."audit_runs"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."audit_runs"
    ADD CONSTRAINT "audit_runs_created_by_fkey" FOREIGN KEY ("created_by") REFERENCES "auth"."users"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."audit_runs"
    ADD CONSTRAINT "audit_runs_organisation_id_fkey" FOREIGN KEY ("organisation_id") REFERENCES "public"."organisations"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."authorities"
    ADD CONSTRAINT "authorities_corpus_id_fkey" FOREIGN KEY ("corpus_id") REFERENCES "public"."authority_corpora"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."authority_passages"
    ADD CONSTRAINT "authority_passages_authority_id_fkey" FOREIGN KEY ("authority_id") REFERENCES "public"."authorities"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."benchmark_runs"
    ADD CONSTRAINT "benchmark_runs_created_by_fkey" FOREIGN KEY ("created_by") REFERENCES "auth"."users"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."benchmark_runs"
    ADD CONSTRAINT "benchmark_runs_organisation_id_fkey" FOREIGN KEY ("organisation_id") REFERENCES "public"."organisations"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."citation_registry_checks"
    ADD CONSTRAINT "citation_registry_checks_corpus_id_fkey" FOREIGN KEY ("corpus_id") REFERENCES "public"."authority_corpora"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."claim_evidence"
    ADD CONSTRAINT "claim_evidence_audit_claim_id_fkey" FOREIGN KEY ("audit_claim_id") REFERENCES "public"."audit_claims"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."claim_evidence"
    ADD CONSTRAINT "claim_evidence_passage_external_id_fkey" FOREIGN KEY ("passage_external_id") REFERENCES "public"."authority_passages"("external_id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."handoff_briefs"
    ADD CONSTRAINT "handoff_briefs_audit_run_id_fkey" FOREIGN KEY ("audit_run_id") REFERENCES "public"."audit_runs"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."handoff_briefs"
    ADD CONSTRAINT "handoff_briefs_reviewed_by_fkey" FOREIGN KEY ("reviewed_by") REFERENCES "auth"."users"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."organisation_members"
    ADD CONSTRAINT "organisation_members_organisation_id_fkey" FOREIGN KEY ("organisation_id") REFERENCES "public"."organisations"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."organisation_members"
    ADD CONSTRAINT "organisation_members_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id") ON DELETE CASCADE;



ALTER TABLE "public"."audit_claims" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "audit_claims_member_read" ON "public"."audit_claims" FOR SELECT TO "authenticated" USING ((EXISTS ( SELECT 1
   FROM ("public"."audit_runs" "run"
     JOIN "public"."organisation_members" "membership" ON (("membership"."organisation_id" = "run"."organisation_id")))
  WHERE (("run"."id" = "audit_claims"."audit_run_id") AND ("membership"."user_id" = ( SELECT "auth"."uid"() AS "uid"))))));



ALTER TABLE "public"."audit_events" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "audit_events_member_read" ON "public"."audit_events" FOR SELECT TO "authenticated" USING ((EXISTS ( SELECT 1
   FROM ("public"."audit_runs" "run"
     JOIN "public"."organisation_members" "membership" ON (("membership"."organisation_id" = "run"."organisation_id")))
  WHERE (("run"."id" = "audit_events"."audit_run_id") AND ("membership"."user_id" = ( SELECT "auth"."uid"() AS "uid"))))));



ALTER TABLE "public"."audit_runs" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "audit_runs_member_read" ON "public"."audit_runs" FOR SELECT TO "authenticated" USING ((EXISTS ( SELECT 1
   FROM "public"."organisation_members" "membership"
  WHERE (("membership"."organisation_id" = "audit_runs"."organisation_id") AND ("membership"."user_id" = ( SELECT "auth"."uid"() AS "uid"))))));



ALTER TABLE "public"."authorities" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "authorities_authenticated_read" ON "public"."authorities" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."authority_corpora" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "authority_corpora_authenticated_read" ON "public"."authority_corpora" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."authority_passages" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "authority_passages_authenticated_read" ON "public"."authority_passages" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."benchmark_runs" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "benchmark_runs_member_read" ON "public"."benchmark_runs" FOR SELECT TO "authenticated" USING ((EXISTS ( SELECT 1
   FROM "public"."organisation_members" "membership"
  WHERE (("membership"."organisation_id" = "benchmark_runs"."organisation_id") AND ("membership"."user_id" = ( SELECT "auth"."uid"() AS "uid"))))));



CREATE POLICY "citation_checks_authenticated_read" ON "public"."citation_registry_checks" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."citation_registry_checks" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."claim_evidence" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "claim_evidence_member_read" ON "public"."claim_evidence" FOR SELECT TO "authenticated" USING ((EXISTS ( SELECT 1
   FROM (("public"."audit_claims" "claim"
     JOIN "public"."audit_runs" "run" ON (("run"."id" = "claim"."audit_run_id")))
     JOIN "public"."organisation_members" "membership" ON (("membership"."organisation_id" = "run"."organisation_id")))
  WHERE (("claim"."id" = "claim_evidence"."audit_claim_id") AND ("membership"."user_id" = ( SELECT "auth"."uid"() AS "uid"))))));



ALTER TABLE "public"."handoff_briefs" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "handoff_briefs_member_read" ON "public"."handoff_briefs" FOR SELECT TO "authenticated" USING ((EXISTS ( SELECT 1
   FROM ("public"."audit_runs" "run"
     JOIN "public"."organisation_members" "membership" ON (("membership"."organisation_id" = "run"."organisation_id")))
  WHERE (("run"."id" = "handoff_briefs"."audit_run_id") AND ("membership"."user_id" = ( SELECT "auth"."uid"() AS "uid"))))));



ALTER TABLE "public"."organisation_members" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "organisation_members_self_read" ON "public"."organisation_members" FOR SELECT TO "authenticated" USING (("user_id" = ( SELECT "auth"."uid"() AS "uid")));



ALTER TABLE "public"."organisations" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "organisations_member_read" ON "public"."organisations" FOR SELECT TO "authenticated" USING ((EXISTS ( SELECT 1
   FROM "public"."organisation_members" "membership"
  WHERE (("membership"."organisation_id" = "organisations"."id") AND ("membership"."user_id" = ( SELECT "auth"."uid"() AS "uid"))))));



GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";



GRANT ALL ON TABLE "public"."audit_claims" TO "service_role";
GRANT SELECT ON TABLE "public"."audit_claims" TO "authenticated";



GRANT ALL ON SEQUENCE "public"."audit_claims_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."audit_claims_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."audit_claims_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."audit_events" TO "service_role";
GRANT SELECT ON TABLE "public"."audit_events" TO "authenticated";



GRANT ALL ON SEQUENCE "public"."audit_events_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."audit_events_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."audit_events_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."audit_runs" TO "service_role";
GRANT SELECT ON TABLE "public"."audit_runs" TO "authenticated";



GRANT ALL ON SEQUENCE "public"."audit_runs_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."audit_runs_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."audit_runs_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."authorities" TO "service_role";
GRANT SELECT ON TABLE "public"."authorities" TO "authenticated";



GRANT ALL ON SEQUENCE "public"."authorities_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."authorities_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."authorities_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."authority_corpora" TO "service_role";
GRANT SELECT ON TABLE "public"."authority_corpora" TO "authenticated";



GRANT ALL ON SEQUENCE "public"."authority_corpora_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."authority_corpora_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."authority_corpora_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."authority_passages" TO "service_role";
GRANT SELECT ON TABLE "public"."authority_passages" TO "authenticated";



GRANT ALL ON SEQUENCE "public"."authority_passages_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."authority_passages_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."authority_passages_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."benchmark_runs" TO "service_role";
GRANT SELECT ON TABLE "public"."benchmark_runs" TO "authenticated";



GRANT ALL ON SEQUENCE "public"."benchmark_runs_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."benchmark_runs_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."benchmark_runs_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."citation_registry_checks" TO "service_role";
GRANT SELECT ON TABLE "public"."citation_registry_checks" TO "authenticated";



GRANT ALL ON SEQUENCE "public"."citation_registry_checks_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."citation_registry_checks_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."citation_registry_checks_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."claim_evidence" TO "service_role";
GRANT SELECT ON TABLE "public"."claim_evidence" TO "authenticated";



GRANT ALL ON SEQUENCE "public"."claim_evidence_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."claim_evidence_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."claim_evidence_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."handoff_briefs" TO "service_role";
GRANT SELECT ON TABLE "public"."handoff_briefs" TO "authenticated";



GRANT ALL ON SEQUENCE "public"."handoff_briefs_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."handoff_briefs_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."handoff_briefs_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."organisation_members" TO "service_role";
GRANT SELECT ON TABLE "public"."organisation_members" TO "authenticated";



GRANT ALL ON SEQUENCE "public"."organisation_members_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."organisation_members_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."organisation_members_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."organisations" TO "service_role";
GRANT SELECT ON TABLE "public"."organisations" TO "authenticated";



GRANT ALL ON SEQUENCE "public"."organisations_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."organisations_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."organisations_id_seq" TO "service_role";



ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "service_role";







