# CS431 Training Experiment: Direction A (Learned Selector) & Direction B (LoRA)

## Mean F1 @ 5cm on 5 Held-out Scenes
| Condition | Base+Def | Base+Combined | Base+A (Learned) | LoRA+Def (B) | LoRA+Combined | LoRA+AB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| default_json | 0.342 | 0.4067 | 0.3111 | 0.3566 | 0.4183 | 0.3271 |
| varyexp_mixed | 0.3347 | 0.4184 | 0.3178 | 0.346 | 0.4236 | 0.3238 |
| uniform_mid | 0.2884 | 0.3321 | 0.3223 | 0.2926 | 0.3387 | 0.3251 |

## Mean AUC@10 on 5 Held-out Scenes
| Condition | Base+Def | Base+Combined | Base+A (Learned) | LoRA+Def (B) | LoRA+Combined | LoRA+AB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| default_json | 0.8609 | 0.8298 | 0.8768 | 0.8643 | 0.8331 | 0.8785 |
| varyexp_mixed | 0.8526 | 0.8573 | 0.8325 | 0.8553 | 0.8615 | 0.8367 |
| uniform_mid | 0.8469 | 0.8584 | 0.8321 | 0.8486 | 0.8615 | 0.8384 |
