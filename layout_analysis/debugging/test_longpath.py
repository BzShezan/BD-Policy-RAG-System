from original_paths import project_path
import fitz
import os

p = project_path('data/raw_pdfs/social_welfare/2026.01.19-63-২০২৫-২৬ অর্থবছরে ০৮ (আট) টি প্রাতিষ্ঠানিক গ্রুপের অধীন ১৮৩ (একশত তিরাশি) টি কার্যালয়_প্রতিষ্ঠান_কেন্দ্রসমূহে ৩২৫৬১০৬-পোষাক, ৩২৫২১০১-বিছানাপত্র এবং ৩২১১১৩০-যাতায়াত ব্যয় উপখাতে বাজেটের অর্থ বরাদ্দ ও মঞ্জুরি প্রদান.pdf')

long_p = "\\\\?\\" + os.path.abspath(p)
print(repr(long_p))
print(len(long_p))

doc = fitz.open(long_p)
print("opened OK", len(doc))