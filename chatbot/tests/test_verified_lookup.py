from original_paths import project_path
import sys
sys.path.insert(0, project_path('chatbot/scripts'))
from chatbot.scripts.verified_lookup import get_verified_clause, get_source_link

clause = get_verified_clause(
    ministry="Social Welfare",
    doc_id="SW_DEPR_Bede, Dalit, AND Harijan_2013_00_Policy_v3",
    clause_id="SW_DEPR_Bede, Dalit, AND Harijan_2013_00_Policy_v3_C0033",
)

print("clause found:", clause is not None)
if clause:
    print("text:", clause["text"][:200])

link = get_source_link(
    doc_id="SW_DEPR_Bede, Dalit, AND Harijan_2013_00_Policy_v3",
    ministry="Social Welfare",
    source_url=clause.get("source_url", "") if clause else "",
)
print("source link:", link)