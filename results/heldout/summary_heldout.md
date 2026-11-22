# CS431 Held-out Evaluation Results (5 scenes, colmap_sparse + c2w)

## Per-scene results
| Scene | Condition | Default F1 | Exposure F1 | Bridge F1 | Overlap F1 | Combined F1 | Oracle F1 | Span F1 | Default AUC10 | Combined AUC10 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GearWorks | default_json | 0.2507 | 0.2507 | 0.2507 | 0.3376 | 0.4276 | 0.4276 | 0.1768 | 0.7348 | 0.7919 |
| GearWorks | varyexp_mixed | 0.2407 | 0.2407 | 0.4127 | 0.3401 | 0.4127 | 0.5676 | 0.3269 | 0.7605 | 0.8059 |
| GearWorks | uniform_mid | 0.2497 | 0.2874 | 0.2874 | 0.2497 | 0.3118 | 0.3118 | 0.0621 | 0.808 | 0.7878 |
| Laboratory | default_json | 0.4492 | 0.3886 | 0.4492 | 0.4492 | 0.4492 | 0.4948 | 0.286 | 0.9019 | 0.8993 |
| Laboratory | varyexp_mixed | 0.2887 | 0.4971 | 0.1687 | 0.423 | 0.4971 | 0.4971 | 0.3283 | 0.8942 | 0.9101 |
| Laboratory | uniform_mid | 0.1489 | 0.2893 | 0.2893 | 0.2893 | 0.2893 | 0.2893 | 0.1404 | 0.8684 | 0.917 |
| MilkCookie | default_json | 0.4621 | 0.4906 | 0.4915 | 0.4906 | 0.4906 | 0.4915 | 0.2484 | 0.8812 | 0.77 |
| MilkCookie | varyexp_mixed | 0.5409 | 0.4392 | 0.5107 | 0.5409 | 0.5107 | 0.5409 | 0.1017 | 0.9093 | 0.895 |
| MilkCookie | uniform_mid | 0.5279 | 0.5413 | 0.5431 | 0.5413 | 0.5413 | 0.5431 | 0.084 | 0.8746 | 0.9027 |
| Popcorn | default_json | 0.4614 | 0.5467 | 0.5747 | 0.5467 | 0.5747 | 0.5747 | 0.1133 | 0.9032 | 0.8546 |
| Popcorn | varyexp_mixed | 0.5154 | 0.5154 | 0.561 | 0.5109 | 0.561 | 0.561 | 0.1367 | 0.8185 | 0.8737 |
| Popcorn | uniform_mid | 0.4348 | 0.4348 | 0.4348 | 0.3867 | 0.4348 | 0.4348 | 0.1323 | 0.8448 | 0.8448 |
| Sculpture | default_json | 0.0864 | 0.0914 | 0.0774 | 0.0914 | 0.0914 | 0.0914 | 0.014 | 0.8985 | 0.8255 |
| Sculpture | varyexp_mixed | 0.088 | 0.1107 | 0.088 | 0.0906 | 0.1107 | 0.1107 | 0.0227 | 0.8625 | 0.7991 |
| Sculpture | uniform_mid | 0.0807 | 0.0851 | 0.0851 | 0.0833 | 0.0833 | 0.1042 | 0.0235 | 0.8209 | 0.8376 |

## Mean by condition (5 held-out scenes)
| Condition | Default F1 | Exposure F1 | Bridge F1 | Overlap F1 | Combined F1 | Δ(Comb-Def) F1 | Oracle F1 | Span F1 | Default AUC10 | Combined AUC10 | Δ(Comb-Def) AUC10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| default_json | 0.342 | 0.3536 | 0.3687 | 0.3831 | 0.4067 | 0.0647 | 0.416 | 0.1677 | 0.8639 | 0.8283 | -0.0356 |
| varyexp_mixed | 0.3347 | 0.3606 | 0.3482 | 0.3811 | 0.4184 | 0.0837 | 0.4555 | 0.1833 | 0.849 | 0.8568 | 0.0078 |
| uniform_mid | 0.2884 | 0.3276 | 0.3279 | 0.3101 | 0.3321 | 0.0437 | 0.3366 | 0.0885 | 0.8433 | 0.858 | 0.0147 |
