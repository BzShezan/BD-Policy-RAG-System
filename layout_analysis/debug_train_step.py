import faulthandler
faulthandler.enable()

import torch
print("1. torch ok", flush=True)

from transformers import AutoConfig, AutoModelForTokenClassification
config = AutoConfig.from_pretrained("nielsr/lilt-xlm-roberta-base")
print("2. config ok", flush=True)

model = AutoModelForTokenClassification.from_config(config)
print("3. model built from config, random weights", flush=True)

model = model.cuda()
print("4. random-weight model on GPU - ok", flush=True)

print("5. now loading real pretrained weights on top...", flush=True)
from transformers import AutoModelForTokenClassification as AMC
pretrained = AMC.from_pretrained(
    "nielsr/lilt-xlm-roberta-base",
    num_labels=14,
    ignore_mismatched_sizes=True,
)
print("6. pretrained weights loaded on CPU - ok", flush=True)

print("7. moving pretrained model to GPU...", flush=True)
pretrained = pretrained.cuda()
print("8. SUCCESS - pretrained model on GPU", flush=True)