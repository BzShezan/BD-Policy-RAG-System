from original_paths import project_path
import sys
sys.path.insert(0, project_path('chatbot/scripts'))
from chatbot.scripts.ner import extract_document_requirements

text = "(ঘ) ট্রেড লাইসেন্সের সত্যায়িত কপি; (৬) টি, আই, এন, সনদপত্র (TIN Certificate) এর সত্যায়িত কপি; (চ) মূল্য সংযোজন কর রেজিস্ট্রেশন সার্টিফিকেটের সত্যায়িত কপি; (ছ) আর্থিক স্বচ্ছলতার প্রমাণস্বরূপ ব্যাংকের সনদপত্র"

matches, confidence = extract_document_requirements(text)
print(f"found: {matches}")
print(f"confidence: {confidence}")