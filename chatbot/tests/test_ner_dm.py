from original_paths import project_path
import sys
sys.path.insert(0, project_path('chatbot/scripts'))
from chatbot.scripts.ner import extract_district_allocations

text = "১. রংপুর ১,০০,০০০/- (একলক্ষ) টাকা ১১. নাটোর ১,০০,০০০/- (একলক্ষ) টাকা."
matches, conf = extract_district_allocations(text)
print(matches)
print(conf)