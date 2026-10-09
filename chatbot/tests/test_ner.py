from original_paths import project_path
import sys
sys.path.insert(0, project_path('chatbot/scripts'))
from chatbot.scripts.ner import extract_entities

text = "প্রার্থীর বার্ষিক গড় আয় অনূর্ধ্ব ৩৬,০০০ (ছত্রিশ হাজার) টাকা হতে হবে"
print(extract_entities(text))