from original_paths import project_path
import sys
sys.path.insert(0, project_path('chatbot/scripts'))
from chatbot.scripts.intent import detect_intents

print(detect_intents("বয়স্ক ভাতার বয়সসীমা ও আয়সীমা কত?"))
print(detect_intents("What documents are required to apply?"))
print(detect_intents("widow allowance eligibility"))