"""Maps intent names -> which extractors can answer that intent.

Keeping this outside two_stage.py so the retrieval logic doesn't
import from chatbot/scripts, which would create circular imports
if the extractors ever need retrieval later.
"""

import sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "chatbot", "scripts"))

from chatbot.scripts.ner import (
    extract_age,
    extract_income_limit,
    extract_benefit_amount,
    extract_document_requirements,
    extract_district_allocations,
    extract_office_authority,
    extract_deadline_date, 
    extract_frequency, 
    extract_duration_period, 
    extract_penalty_fine,
)


EXTRACTORS_FOR_INTENT = {
    "age":                  [extract_age],
    "income_limit":         [extract_income_limit],
    "benefit_amount":       [extract_benefit_amount],
    "required_documents":   [extract_document_requirements],
    "district_allocation":  [extract_district_allocations],
    "office_authority":     [extract_office_authority],
    "deadline_date":        [extract_deadline_date],
    "frequency":            [extract_frequency],
    "duration_period":      [extract_duration_period],
    "penalty_fine":         [extract_penalty_fine],
}