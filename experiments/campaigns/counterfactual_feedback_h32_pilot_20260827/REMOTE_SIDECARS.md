# Exact-state sidecars

Локально синхронизированы manifests, configs, logs и полные raw tables для
48/48 states. Большие MuJoCo NPZ sidecars (48 файлов, около 124 МБ) сохранены
на ML Space:

```text
/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/experiments/campaigns/counterfactual_feedback_h32_pilot_20260827/runs/*__snapshots/*.npz
```

Они нужны только для повторной endpoint-разметки. Текущие dense labels и весь
анализ уже синхронизированы локально в соседней campaign
`counterfactual_feedback_h32_dense_relabel_20260827`.

Полный перенос при необходимости:

```bash
ssh mlspace-sr006 \
  'cd /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP && \
   tar -cf - experiments/campaigns/counterfactual_feedback_h32_pilot_20260827/runs/*__snapshots' \
  | tar -xf -
```
