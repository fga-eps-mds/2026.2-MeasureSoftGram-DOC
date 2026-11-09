import type { SidebarsConfig } from "@docusaurus/plugin-content-docs";

/**
 * Sidebar única da documentação da disciplina, organizada pelas fases do
 * trabalho: as regras da disciplina, o que é o produto, como a equipe se
 * organiza, o que foi feito em cada sprint e como o resultado é medido.
 */
const sidebars: SidebarsConfig = {
  docsSidebar: [
    "intro",
    "disciplina/disciplina",
    {
      type: "category",
      label: "Releases",
      collapsed: false,
      items: ["releases/release-1", "releases/release-2", "releases/release-3"],
    },
    {
      type: "category",
      label: "Produto",
      items: [
        "produto/visao-do-produto",
        "produto/arquitetura",
        "produto/repositorios",
      ],
    },
    {
      type: "category",
      label: "Lean Inception",
      items: [
        "lean-inception/visao-geral",
        "lean-inception/visao-do-produto",
        "lean-inception/e-nao-e-faz-nao-faz",
        "lean-inception/objetivos",
        "lean-inception/personas",
        "lean-inception/jornadas",
        "lean-inception/brainstorming",
        "lean-inception/revisao-tecnica-negocio-ux",
        "lean-inception/dimensionamento",
        "lean-inception/sequenciador",
        "lean-inception/canvas-mvp",
      ],
    },
    {
      type: "category",
      label: "Templates e fluxos",
      items: [
        "processo/templates",
        "processo/fluxo-de-trabalho",
        "processo/historia-de-usuario",
        "processo/pauta-reuniao-diaria",
      ],
    },
    {
      type: "category",
      label: "Diagnóstico",
      items: ["diagnostico/diagnostico", "diagnostico/backlog-tecnico"],
    },
    {
      type: "category",
      label: "Planejamento",
      items: [
        "planejamento/metodologia",
        "planejamento/backlog",
        "planejamento/eap",
        "planejamento/roadmap",
        "planejamento/squads",
        "planejamento/selecaometricas",
        "planejamento/metas",
        "planejamento/riscos",
        "planejamento/custos",
        "planejamento/agile-evm",
        "planejamento/decisoes",
      ],
    },
    {
      type: "category",
      label: "Sprints",
      items: [
        "sprints/sprints",
        "sprints/sprint-1",
        "sprints/sprint-2",
        "sprints/sprint-3",
        "sprints/sprint-4",
        "sprints/sprint-5",
        "sprints/sprint-6",
        "sprints/sprint-7",
      ],
    },
    {
      type: "category",
      label: "Reuniões",
      collapsed: false,
      items: [
        "reunioes/reunioes",
        {
          type: "category",
          label: "Reuniões com o PO",
          collapsed: false,
          items: [
            "reunioes/reunioes-po/reuniao-po-1",
            "reunioes/reunioes-po/pauta-po-02-09",
            "reunioes/reunioes-po/ata-po-02-09",
            "reunioes/reunioes-po/ata-po-23-09",
            "reunioes/reunioes-po/ata-po-07-10",
            "reunioes/reunioes-po/ata-po-14-10",
            "reunioes/reunioes-po/ata-po-21-10",
            "reunioes/reunioes-po/ata-po-04-11",
          ],
        },
        {
          type: "category",
          label: "Feedback de Release",
          collapsed: false,
          items: ["reunioes/feedback-release/ata-feedback-r2"],
        },
        {
          type: "category",
          label: "Reuniões do Time",
          collapsed: false,
          items: ["reunioes/reunioes-time/ata-planning-sprint-8"],
        },
      ],
    },
    {
      type: "category",
      label: "Métricas",
      items: [
        "metricas/metricas",
        "metricas/guia-dashboard",
        "metricas/modelo-de-gestao",
      ],
    },
    {
      type: "category",
      label: "Equipe",
      items: [
        "equipe/equipe",
        "equipe/politicas",
        "equipe/uso-de-ia",
        "equipe/guia-documentacao",
        "equipe/links",
      ],
    },
  ],
};

export default sidebars;
