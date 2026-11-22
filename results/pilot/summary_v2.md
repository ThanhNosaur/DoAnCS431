# CS431 Experiment Results v2 (coordinate_mode=colmap_sparse + c2w)

## Per-scene results
| Scene | Condition | Default F1 | Exposure F1 | Bridge F1 | Overlap F1 | Combined F1 | Oracle F1 | Span F1 | Default AUC10 | Combined AUC10 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Ujikintoki | default_json | 0.4379 | 0.188 | 0.4186 | 0.4379 | 0.4379 | 0.5177 | 0.3296 | 0.9088 | 0.9076 |
| Ujikintoki | varyexp_mixed | 0.3864 | 0.6494 | 0.5876 | 0.5876 | 0.5876 | 0.6494 | 0.263 | 0.9242 | 0.9164 |
| Ujikintoki | uniform_mid | 0.1659 | 0.1659 | 0.1659 | 0.3681 | 0.3681 | 0.3681 | 0.2021 | 0.8336 | 0.8924 |
| BlueHawaii | default_json | 0.5555 | 0.5539 | 0.5539 | 0.4974 | 0.5555 | 0.5555 | 0.2027 | 0.8466 | 0.8433 |
| BlueHawaii | varyexp_mixed | 0.3161 | 0.2854 | 0.2978 | 0.2978 | 0.2978 | 0.4284 | 0.143 | 0.886 | 0.8893 |
| BlueHawaii | uniform_mid | 0.4488 | 0.3896 | 0.3896 | 0.3896 | 0.3896 | 0.4488 | 0.137 | 0.893 | 0.8231 |
| Chocolate | default_json | 0.7 | 0.7 | 0.7 | 0.7 | 0.7 | 0.7 | 0.2682 | 0.8048 | 0.7888 |
| Chocolate | varyexp_mixed | 0.6221 | 0.5045 | 0.5388 | 0.5045 | 0.5045 | 0.6221 | 0.1176 | 0.73 | 0.7055 |
| Chocolate | uniform_mid | 0.5398 | 0.6649 | 0.6649 | 0.6649 | 0.6649 | 0.685 | 0.1851 | 0.7954 | 0.7996 |
| Cupcake | default_json | 0.449 | 0.4542 | 0.4353 | 0.4788 | 0.4788 | 0.4788 | 0.0435 | 0.8138 | 0.8937 |
| Cupcake | varyexp_mixed | 0.4688 | 0.4038 | 0.4813 | 0.4203 | 0.4813 | 0.4813 | 0.0775 | 0.8973 | 0.8471 |
| Cupcake | uniform_mid | 0.4557 | 0.4557 | 0.4557 | 0.4471 | 0.4557 | 0.4557 | 0.0298 | 0.9063 | 0.9063 |

## Mean by condition
| Condition | Default F1 | Exposure F1 | Bridge F1 | Overlap F1 | Combined F1 | Δ(Comb-Def) F1 | Oracle F1 | Span F1 | Default AUC10 | Combined AUC10 | Δ(Comb-Def) AUC10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| default_json | 0.5356 | 0.474 | 0.527 | 0.5285 | 0.5431 | 0.0075 | 0.563 | 0.211 | 0.8435 | 0.8583 | 0.0148 |
| varyexp_mixed | 0.4484 | 0.4608 | 0.4764 | 0.4526 | 0.4678 | 0.0194 | 0.5453 | 0.1503 | 0.8594 | 0.8396 | -0.0198 |
| uniform_mid | 0.4026 | 0.419 | 0.419 | 0.4674 | 0.4696 | 0.067 | 0.4894 | 0.1385 | 0.8571 | 0.8553 | -0.0018 |
