# 2026.2-MeasureSoftGram-DOC

Documentação da equipe de **Engenharia de Produto de Software (EPS)** do semestre
2026.2 no projeto **MeasureSoftGram**. 

O site é publicado via GitHub Pages em:
https://fga-eps-mds.github.io/2026.2-MeasureSoftGram-DOC/

> A documentação **do produto** (como usar, referência da CLI, componentes) fica
> em repositório próprio:
> [MeasureSoftGram-Docs](https://github.com/fga-eps-mds/MeasureSoftGram-Docs).

## Estrutura

```
docs/
  intro.mdx              Página inicial da documentação
  produto/               Visão do produto, arquitetura, repositórios
  planejamento/          Metodologia, roadmap, riscos
  sprints/               Registro de cada sprint
  metricas/              Métricas de processo e de produto
  equipe/                Integrantes, políticas de trabalho, links e acessos
```

## Rodando localmente

Requer Node 20 ou superior.

```bash
npm install
npm start
```

O site fica disponível em http://localhost:3000.

## Build

```bash
npm run build    # gera o site estático em build/
npm run serve    # serve o build localmente
```

## Publicação

Todo push na branch `main` dispara o workflow
[`deploy.yml`](.github/workflows/deploy.yml), que faz o build e publica no
GitHub Pages. Não é necessário rodar deploy manualmente.

## Como contribuir

1. Crie uma branch a partir de `main` (`docs/<assunto>`).
2. Edite os arquivos `.mdx` em `docs/`.
3. Rode `npm run build` para garantir que não há links quebrados.
4. Abra um Pull Request.

Cada página publicada tem um link **Edit this page** no rodapé que leva direto ao
arquivo correspondente no GitHub.

## Licença

AGPL-3.0 - veja [LICENSE](LICENSE).
