import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

/**
 * Sidebar única da documentação da disciplina, organizada pelas fases do
 * trabalho: as regras da disciplina, o que é o produto, como a equipe se
 * organiza, o que foi feito em cada sprint e como o resultado é medido.
 */
const sidebars: SidebarsConfig = {
  docsSidebar: [
    'intro',
    {
      type: 'category',
      label: 'A disciplina',
      collapsed: false,
      items: [
        'disciplina/disciplina',
        'disciplina/avaliacao',
        'disciplina/cronograma',
        'disciplina/politica-ia',
      ],
    },
    {
      type: 'category',
      label: 'Produto',
      collapsed: false,
      items: [
        'produto/visao-do-produto',
        'produto/arquitetura',
        'produto/repositorios',
      ],
    },
    {
      type: 'category',
      label: 'Lean Inception',
      collapsed: false,
      items: [
        'LeanInception/atv1',
        'LeanInception/atv2',
        'LeanInception/atv3',
        'LeanInception/atv4',
        'LeanInception/atv5',
        'LeanInception/atv6',
        'LeanInception/atv7',
        'LeanInception/atv8',
        'LeanInception/atv9',
        'LeanInception/atv10',
        'LeanInception/board',
      ],
    },
    {
      type: 'category',
      label: 'Diagnóstico',
      collapsed: false,
      items: ['diagnostico/diagnostico', 'diagnostico/backlog-tecnico'],
    },
    {
      type: 'category',
      label: 'Planejamento',
      items: [
        'planejamento/metodologia',
        'planejamento/backlog',
        'planejamento/eap',
        'planejamento/roadmap',
        'planejamento/riscos',
        'planejamento/custos',
        'planejamento/agile-evm',
        'planejamento/decisoes',
        'planejamento/squads',
      ],
    },
    {
      type: 'category',
      label: 'Sprints',
      items: ['sprints/sprints'],
    },
    {
      type: 'category',
      label: 'Reuniões',
      items: [
        'reunioes/reunioes',
        'reunioes/pauta-po-02-09',
        'reunioes/ata-po-02-09',
        'reunioes/ata-po-23-09',
      ],
    },
    {
      type: 'category',
      label: 'Métricas',
      items: ['metricas/guia-dashboard', 'metricas/metricas', 'metricas/modelo-de-gestao', 'metricas/velocity-zenhub'],
    },
    {
      type: 'category',
      label: 'Equipe',
      items: ['equipe/equipe', 'equipe/politicas', 'equipe/links'],
    },
  ],
};

export default sidebars;
