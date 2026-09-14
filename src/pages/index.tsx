import type {ReactNode} from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import HomepageFeatures from '@site/src/components/HomepageFeatures';
import Heading from '@theme/Heading';

import styles from './index.module.css';

function HomepageHeader() {
  const {siteConfig} = useDocusaurusContext();
  return (
    <header className={clsx('hero hero--primary', styles.heroBanner)}>
      <div className="container">
        <Heading as="h1" className="hero__title">
          {siteConfig.title}
        </Heading>
        <p className="hero__subtitle">{siteConfig.tagline}</p>

        <div className={styles.buttons}>
          <Link className="button button--secondary button--lg" to="/docs/intro">
            Comece por aqui
          </Link>
          <Link
            className="button button--outline button--secondary button--lg"
            href="https://github.com/fga-eps-mds/2026.2-MeasureSoftGram-DOC">
            Ver no GitHub
          </Link>
        </div>
      </div>
    </header>
  );
}

function SobreDisciplina() {
  return (
    <section className={styles.whoUses}>
      <div className="container text--center">
        <Heading as="h2">Sobre a disciplina</Heading>
        <p className={styles.whoUsesText}>
          O MeasureSoftGram é desenvolvido e evoluído a cada semestre por turmas
          das disciplinas de Engenharia de Produto de Software (EPS) e Métodos de
          Desenvolvimento de Software (MDS) da Universidade de Brasília (FGA), sob
          a organização{' '}
          <a href="https://github.com/fga-eps-mds" target="_blank" rel="noopener noreferrer">
            fga-eps-mds
          </a>
          . Este site documenta o trabalho da equipe de EPS no semestre 2026.2. A
          documentação do produto em si fica em{' '}
          <a
            href="https://fga-eps-mds.github.io/MeasureSoftGram-Docs/"
            target="_blank"
            rel="noopener noreferrer">
            MeasureSoftGram-Docs
          </a>
          .
        </p>
      </div>
    </section>
  );
}

export default function Home(): ReactNode {
  const {siteConfig} = useDocusaurusContext();
  return (
    <Layout
      title={siteConfig.title}
      description="Documentação da equipe de EPS 2026.2 no projeto MeasureSoftGram.">
      <HomepageHeader />
      <main>
        <HomepageFeatures />
        <SobreDisciplina />
      </main>
    </Layout>
  );
}
