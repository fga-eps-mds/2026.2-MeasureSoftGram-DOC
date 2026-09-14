import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'MeasureSoftGram - EPS 2026.2',
  tagline: 'Documentação da equipe na disciplina de Engenharia de Produto de Software',
  favicon: 'img/favicon.png',

  // Fontes da IDV: Roboto (texto/títulos) + Quattrocento (wordmark do logo).
  stylesheets: [
    'https://fonts.googleapis.com/css2?family=Quattrocento:wght@400;700&family=Roboto:wght@400;500;700&display=swap',
  ],

  future: {
    v4: true,
  },

  url: 'https://fga-eps-mds.github.io',
  baseUrl: '/2026.2-MeasureSoftGram-DOC/',
  trailingSlash: true,

  organizationName: 'fga-eps-mds',
  projectName: '2026.2-MeasureSoftGram-DOC',

  onBrokenLinks: 'throw',

  markdown: {
    mermaid: true,
    hooks: {
      onBrokenMarkdownLinks: 'throw',
    },
  },

  themes: [
    '@docusaurus/theme-mermaid',
    [
      // Busca full-text client-side, autocontida (sem serviço externo).
      require.resolve('@easyops-cn/docusaurus-search-local'),
      {
        hashed: true,
        language: ['pt', 'en'],
        indexBlog: false,
        docsRouteBasePath: '/docs',
      },
    ],
  ],

  i18n: {
    defaultLocale: 'pt-BR',
    locales: ['pt-BR'],
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          editUrl:
            'https://github.com/fga-eps-mds/2026.2-MeasureSoftGram-DOC/tree/main/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    image: 'img/docusaurus-social-card.jpg',
    colorMode: {
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'MeasureSoftGram EPS',
      logo: {
        alt: 'Logo do MeasureSoftGram',
        src: 'img/logo.svg',
        srcDark: 'img/logo-dark.svg',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'docsSidebar',
          position: 'left',
          label: 'Documentação',
        },
        {
          href: 'https://github.com/fga-eps-mds/2026.2-MeasureSoftGram-DOC',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Projeto',
          items: [
            {label: 'Visão do produto', to: '/docs/produto/visao-do-produto'},
            {label: 'Arquitetura', to: '/docs/produto/arquitetura'},
            {label: 'Equipe', to: '/docs/equipe'},
          ],
        },
        {
          title: 'Processo',
          items: [
            {label: 'Planejamento', to: '/docs/planejamento'},
            {label: 'Sprints', to: '/docs/sprints'},
            {label: 'Métricas', to: '/docs/metricas'},
          ],
        },
        {
          title: 'Links',
          items: [
            {
              label: 'Organização no GitHub',
              href: 'https://github.com/fga-eps-mds',
            },
            {
              label: 'Documentação do produto',
              href: 'https://fga-eps-mds.github.io/MeasureSoftGram-Docs/',
            },
          ],
        },
      ],
      copyright: `MeasureSoftGram - EPS 2026.2 - fga-eps-mds. Construído com Docusaurus.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
