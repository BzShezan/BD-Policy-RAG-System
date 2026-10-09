import re
import unicodedata

STOP = set("কি কী কত কিভাবে কীভাবে করতে করার পেতে পাবো হবে আছে জন্য আমি আমার আমাকে এর এবং বা the a an is are how what to for of do get need required requirements documents new".split())

def normalize(text):
    return unicodedata.normalize("NFC", text.lower()).replace("বয়", "বয়")

def tokens(text):
    words = re.findall(r"[a-z0-9]+|[\u0980-\u09ff]+", normalize(text))
    words = [w for w in words if w not in STOP and len(w) > 1]
    aliases = {"ভাতার": "ভাতা", "বয়সের": "বয়স", "বয়স": "বয়স", "age": "বয়স",
               "elderly": "বয়স্ক", "allowance": "ভাতা", "old": "বয়স্ক", "বৃদ্ধ": "বয়স্ক"}
    return [aliases.get(w, w) for w in words]

def freshness_requested(q):
    q = normalize(q)
    return any(w in q for w in ("latest", "current", "today", "updated", "নতুন নিয়ম", "সর্বশেষ", "বর্তমান", "এখন", "আজ"))
