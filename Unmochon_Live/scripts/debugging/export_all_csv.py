from original_paths import project_path
import json
import csv
import os

FILES = {
    "Social_Welfare": project_path('data/processed_jsonl/Social_Welfare_clauses.jsonl'),
    # "Agriculture": r"G:\BD-Policy-RAG-System\data\processed_jsonl\Agriculture_clauses.jsonl",
    # "Disaster_Management": r"G:\BD-Policy-RAG-System\data\processed_jsonl\Disaster_Management_clauses.jsonl",
}

OUTPUT_DIR = project_path('data/csv')
os.makedirs(OUTPUT_DIR, exist_ok=True)

for ministry_name, input_path in FILES.items():
    if not os.path.exists(input_path):
        print(f"NOT FOUND, skipping: {input_path}")
        continue

    with open(input_path, encoding="utf-8") as f:
        clauses = [json.loads(l) for l in f if l.strip()]

    output_path = os.path.join(OUTPUT_DIR, f"{ministry_name}_clauses.csv")

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "clause_id", "text", "doc_id", "page_number",
            "ministry", "layout_label", "circular_date",
            "source_url", "quality_score"
        ])

        for c in clauses:
            writer.writerow([
                c.get("clause_id", ""),
                c.get("text", "").replace("\n", " "),
                c.get("doc_id", ""),
                c.get("page_number", ""),
                ministry_name.replace("_", " "),
                c.get("layout_label", ""),
                c.get("circular_date", ""),
                c.get("source_url", ""),
                c.get("quality_score", ""),
            ])

    print(f"{ministry_name}: {len(clauses)} clauses -> {output_path}")

print("\nDone.")