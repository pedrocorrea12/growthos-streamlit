# GrowthOS | Marketing Analytics

Dashboard de marketing analytics para um e-commerce multicanal, construído em Python (Streamlit + Plotly).
Todos os dados são **sintéticos** (seed fixa, 2024–2025).

## O que ele responde

- **Visão geral:** receita, margem, investimento, ROAS e CAC com variação vs. período anterior; realizado vs. meta; receita por praça e categoria.
- **Canais:** economia por canal (ROAS e CAC só para mídia paga, margem após mídia), funil de mídia e mix de receita.
- **Clientes:** retenção por coorte, receita de novos vs. recorrentes e receita por cliente por canal, faixa etária e renda.
- **Experimentos:** diferença-em-diferenças com intervalo de confiança de 95%. A leitura é "Inconclusivo" quando o intervalo inclui zero.
- **Metodologia:** definições das métricas e limites da análise.

## Decisões de método

- Pedidos cancelados ficam fora de pedidos, receita e CAC. Devolvidos reconhecem 25% da receita.
- ROAS e CAC não são calculados para canais próprios e orgânicos, onde o investimento é quase zero e a razão distorce a leitura.
- Lift de experimento é reportado com intervalo de confiança, não como número isolado.

## Como rodar

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Dados

`data/` contém as tabelas da base sintética em modelo estrela (canais, praças, produtos, clientes, pedidos, itens, mídia diária, metas e experimentos).
