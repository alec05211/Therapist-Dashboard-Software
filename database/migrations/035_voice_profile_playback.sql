ALTER TABLE app.account_voice_profiles
    ADD COLUMN sample_audio bytea,
    ADD COLUMN sample_mime text;
ALTER TABLE app.account_voice_profiles ADD CONSTRAINT voice_sample_size
    CHECK (sample_audio IS NULL OR octet_length(sample_audio) <= 4194304);
