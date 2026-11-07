# Fase 3 — Relatório da interface (MVP)

Data: 07/11/2026. **229 testes passando** (20 do app); cobertura do núcleo 98%.

## Telas

| Tela | Conteúdo |
|---|---|
| 1 · Dados | Upload do Mapa (PDF) e do Runflow (XLSX), obrigatórios, e do `.toml` das colunas internas, opcional. Chave para usar as amostras fictícias. Situação de cada arquivo (data da posição, lotes, posições, papéis, colunas ausentes). Data da coleta dos dados públicos, com alerta acima de 3 dias úteis. Tabela editável das linhas com erro, revalidadas ao aplicar. |
| 2 · Parâmetros | Modo interno/cliente, PF/PJ, investidor qualificado, horizonte, cenário (Focus ou do usuário), banda de duration, tolerância de rating, aceitar papéis sem rating, mesma tributação, modo amplo, inclusão de papéis sem PU Mercado, limites por emissor e setor, b por classe de liquidez, limiares de classificação e botão de restaurar padrões. |
| 3 · Carteira | Posições com taxa de mercado e duration (fonte e natureza: dado, estimativa ou aproximação), marcação vs curva e alertas. Editor para informar cupom, amortização, duration ou taxa por posição. No modo interno: spread estimado da mesa e marca de revisão. |
| 4 · Trocas | Contagem por classificação, ganho anual estimado, carteira antes e depois e alertas. Por posição: até 3 candidatos com cenários A e B, justificativa filtro a filtro e reprovações por filtro. Export Excel no modo ativo, gerado no navegador. |
| 5 · Metodologia | Resumo dos cálculos, limitações e aviso de não recomendação. O documento de pesquisa completo aparece só no modo interno, porque descreve o run da instituição. |

## Privacidade na interface

- Arquivos, correções e sobrescritas ficam só em `st.session_state`, a memória da aba. O
  download do Excel é gerado no navegador.
- **Modo cliente:**
  - sem colunas internas, sem lastro, sem spread da mesa e sem marca de revisão;
  - "Runflow" vira "oferta disponível" em todos os textos;
  - sem menção ao fee;
  - a Metodologia mostra só o resumo.
  
  Os testes leem todo o texto renderizado das telas 3, 4 e 5 para conferir isso, e o Excel é
  conferido célula a célula.
- Os parâmetros persistem ao trocar de tela; os arquivos ficam guardados em memória.

## Verificação

- **Local** (`AppTest` do Streamlit):
  - as 5 telas sobem com e sem dados;
  - a tela 4 produz trocas e o botão de export;
  - os modos interno e cliente se comportam como descrito acima;
  - um parâmetro alterado na tela 2 muda o resultado da tela 4;
  - a sobrescrita na Carteira vira "informado pelo usuário".
- **Navegador** (stlite 1.12.0, servidor local), com as amostras:
  - as 5 telas abrem sem erro;
  - carga inicial de ~20 s, com o painel em segundo plano;
  - Dados e Trocas desenham em ~2–3 s.
  
  A leitura do PDF de amostra não ficou lenta, então o pdf.js não foi necessário.

## Falta para publicar

1. Criar o repositório público `credito-privado-sim` no GitHub (vazio) e, em Settings → Pages,
   escolher a origem "GitHub Actions".
2. Com o seu OK: `git remote add`, `git push`, conferir os workflows (Testes; Dados públicos e
   site) e abrir o site publicado.
3. Testar no site publicado com os arquivos reais (só sintomas).
