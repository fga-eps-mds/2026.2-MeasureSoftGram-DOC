# Guia de contribuição

Este repositório reúne a documentação da equipe de EPS 2026.2 do **MeasureSoftGram**
(site em Docusaurus). A documentação do produto fica em
[MeasureSoftGram-Docs](https://github.com/fga-eps-mds/MeasureSoftGram-Docs).

Antes de contribuir, leia o [Código de Conduta](CODE_OF_CONDUCT.md) e as
[políticas de trabalho da equipe](https://fga-eps-mds.github.io/2026.2-MeasureSoftGram-DOC/docs/equipe/politicas/).

## 1. Abra ou escolha uma issue

Toda alteração parte de uma issue. Se ainda não existir, crie uma usando o template
adequado:

| Template | Quando usar |
| --- | --- |
| Tarefa | Criar ou atualizar uma página, ata, relatório ou configuração |
| História de usuário | Registrar uma história do backlog |
| Épico | Agrupar histórias relacionadas |
| Defeito | Link quebrado, conteúdo incorreto, erro de build ou de exibição |

## 2. Crie uma branch a partir da `main`

Neste repositório as branches saem da `main` e voltam para ela. Use nomes em minúsculas,
com palavras separadas por hífen:

```bash
git checkout main
git pull
git checkout -b docs/ata-po-30-09
```

| Prefixo | Uso |
| --- | --- |
| `docs/` | Conteúdo da documentação |
| `fix/` | Correção de link, build ou conteúdo |
| `chore/` | Configuração, dependências e CI |

## 3. Escreva e rode localmente

Requer Node 20 ou superior.

```bash
npm install
npm start        # servidor local em http://localhost:3000
npm run build    # obrigatório antes de abrir o PR
```

Cuidados com o conteúdo:

- As páginas ficam em `docs/`, em `.mdx`. Cada página precisa do front matter com `id`,
  `title` e `sidebar_position`.
- O build **falha com links quebrados** (`onBrokenLinks: 'throw'`). Para links internos, use
  o caminho relativo do arquivo, como `../diagnostico/diagnostico.mdx`.
- Em MDX, `{`, `}` e `<` fora de blocos de código são interpretados como JSX. Coloque-os
  entre crases ou em blocos de código.
- Diagramas devem usar blocos ` ```mermaid `. O build não valida a sintaxe do Mermaid, então
  confira a renderização no `npm start`.
- Imagens vão em `static/img/`.
- Os arquivos em `Analytics/` e `analytics-raw-data/` são gerados pelos pipelines de métricas
  dos repositórios do produto. Não os edite manualmente.

## 4. Faça commits no padrão Conventional Commits

```
<tipo>(<escopo opcional>): <descrição no imperativo>
```

Exemplos:

```
docs(produto): adiciona visão do produto
fix(arquitetura): corrige link para o backlog técnico
chore: atualiza dependências do Docusaurus
```

Os tipos aceitos estão nas [políticas de trabalho](https://fga-eps-mds.github.io/2026.2-MeasureSoftGram-DOC/docs/equipe/politicas/#política-de-commits).
Commits com mais de um autor usam `Co-authored-by:`.

## 5. Abra o pull request

- Base: `main`. Compare: a sua branch.
- Preencha o template do PR: descrição, issue relacionada (`Closes #N`), como testar e
  critérios de aceitação.
- O Netlify comenta no PR com a URL do **Deploy Preview**. Use-a para conferir o resultado
  visual antes da revisão.
- Se houve uso relevante de IA na contribuição, registre no seu `MD_Template.md`.

## 6. Revisão e merge

- O PR precisa da aprovação de ao menos um outro integrante e da CI verde.
- O autor não faz merge do próprio PR sem aprovação.
- Se forem pedidas mudanças, corrija na mesma branch e solicite nova revisão.
- Após o merge na `main`, o workflow [`deploy.yml`](.github/workflows/deploy.yml) publica o
  site no GitHub Pages automaticamente.

**Obrigado por contribuir!**
