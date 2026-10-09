"""Check what detect_intents returns for each demo question. An empty
intent list means the extractor pipeline never runs - a common cause
of FAIL that has nothing to do with retrieval quality."""

import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "chatbot", "scripts"))

from chatbot.scripts.intent import detect_intents

QUESTIONS = [
    "বয়স্ক ভাতা পেতে সর্বনিম্ন বয়স কত হতে হবে?",
    "বেদে, দলিত ও হরিজন ভাতার জন্য সর্বনিম্ন বয়স কত?",
    "চা-শ্রমিক কল্যাণে সর্বনিম্ন বয়স কত?",
    "বেদে, দলিত ও হরিজন সম্প্রদায়ের ভাতার জন্য প্রার্থীর বার্ষিক আয়সীমা কত?",
    "বিধবা ভাতা পেতে প্রার্থীর বার্ষিক আয়সীমা কত?",
    "চা-শ্রমিক ভাতার নীতিমালা অনুযায়ী প্রার্থীর বার্ষিক আয়সীমা কত?",
    "চা-শ্রমিক ভাতার ওয়েবপেজ অনুযায়ী প্রার্থীর বার্ষিক আয়সীমা কত?",
    "সার উৎপাদনকারী হিসেবে নিবন্ধনের জন্য কী কী কাগজপত্র প্রয়োজন?",
    "সার ডিলার নিয়োগের জন্য কোন কাগজপত্র লাগে?",
    "বীজ ডিলার নিবন্ধনের জন্য কী প্রয়োজন?",
    "পিতা-মাতা পরিচর্যা কেন্দ্র প্রতিষ্ঠার জন্য কী কাগজপত্র প্রয়োজন?",
    "সার ব্যবস্থাপনা সংশোধন বিধিমালা ২০২১ অনুযায়ী নিবন্ধনের কাগজপত্র কী?",
]

for q in QUESTIONS:
    intents = detect_intents(q)
    marker = "  " if intents else "!!"
    print(f"{marker} {intents}   {q[:70]}")