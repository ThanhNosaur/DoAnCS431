# CS431 Training Experiment: Direction A (Learned Selector) & Direction B (LoRA)

## Mean F1 @ 5cm on 5 Held-out Scenes
| Condition | Base+Def | Base+Comb (v2) | Base+A (Learned) | LoRA+Def (B) | LoRA+Comb (B+v2) | LoRA+AB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| default_json | 0.342 | 0.4067 | 0.3111 | 0.3566 | 0.4183 | 0.3271 |
| varyexp_mixed | 0.3347 | 0.4184 | 0.3178 | 0.346 | 0.4236 | 0.3238 |
| uniform_mid | 0.2884 | 0.3321 | 0.3223 | 0.2926 | 0.3387 | 0.3251 |

## Mean AUC@10 on 5 Held-out Scenes
| Condition | Base+Def | Base+Comb (v2) | Base+A (Learned) | LoRA+Def (B) | LoRA+Comb (B+v2) | LoRA+AB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| default_json | 0.8639 | 0.8283 | 0.8711 | 0.8668 | 0.832 | 0.8726 |
| varyexp_mixed | 0.849 | 0.8568 | 0.8272 | 0.8527 | 0.8613 | 0.8313 |
| uniform_mid | 0.8433 | 0.858 | 0.8322 | 0.8451 | 0.8615 | 0.8385 |
