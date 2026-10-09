import torch
print("step 1: import ok", flush=True)

x = torch.randn(1000, 1000).cuda()
print("step 2: small tensor on GPU ok", flush=True)

# simulate something closer to a real forward pass - matrix multiply
y = torch.randn(1000, 1000).cuda()
z = x @ y
print("step 3: matrix multiply on GPU ok", flush=True)
print(z.sum().item())
print("step 4: read result back - SUCCESS", flush=True)