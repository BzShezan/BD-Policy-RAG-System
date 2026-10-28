# Reserved KG + contradiction port — teammate owned

Do NOT implement KG/contradiction here. Existing authoritative plug-in: `stage6.versions.source_versions(question, proposals, groups, mapping, retrieved, hook=...)` and `examples.teammate_adapter.TeammateAdapter(kg, contradiction, extension)` implementing `annotate(bundle) -> dict`. No plug-in is autodiscovered/imported by the live app. Stage 6 result already exposes `teammate_annotations` to the UI, which is presentation-only. Preserve all document editions, dates, quotes and no-automatic-winner behavior.

When teammate delivers code, review and test hook separately with immutable source lists; never grant index-write privileges to the hook. A later explicit integration patch must connect their hook inside the verified Stage 6 query worker. Keep accepted generation unchanged until its benchmark gate is passed.
