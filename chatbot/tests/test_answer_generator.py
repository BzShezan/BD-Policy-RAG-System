from original_paths import project_path
import sys
sys.path.insert(0, project_path('chatbot/scripts'))
from chatbot.scripts.intent import detect_intents
from chatbot.scripts.answer_generator import generate_answer

query = "বেদে দলিত হরিজন সম্প্রদায়ের আয়সীমা কত?"
clause_text = "৫. প্রার্থীর বার্ষিক গড় আয় অনূর্ধ্ব ৩৬,০০০ (ছত্রিশ হাজার) টাকা হতে হবে;"

intents = detect_intents(query)
print("detected intents:", intents)

responses = generate_answer(
    clause_text=clause_text,
    doc_id="SW_DEPR_Bede, Dalit, AND Harijan_2013_00_Policy_v3",
    page=11,
    source_url="",
    intents=intents,
)

for r in responses:
    print(f"\ntier: {r['tier']} | confidence: {r['confidence']}")
    print(r['answer'])