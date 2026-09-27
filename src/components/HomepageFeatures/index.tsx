import type {ReactNode} from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import Heading from '@theme/Heading';
import styles from './styles.module.css';

type FeatureItem = {
  title: string;
  Svg: React.ComponentType<React.ComponentProps<'svg'>>;
  to: string;
  description: ReactNode;
};

const FeatureList: FeatureItem[] = [
  {
    title: 'O produto',
    Svg: require('@site/static/img/feature-medir.svg').default,
    to: '/docs/produto/visao-do-produto',
    description: (
      <>
        Visão do produto, arquitetura do sistema e os repositórios que compõem o
        MeasureSoftGram.
      </>
    ),
  },
  {
    title: 'O processo',
    Svg: require('@site/static/img/feature-modular.svg').default,
    to: '/docs/planejamento/metodologia',
    description: (
      <>
        Metodologia adotada pela equipe, roadmap do semestre, gestão de riscos e o
        registro de cada sprint.
      </>
    ),
  },
  {
    title: 'A equipe',
    Svg: require('@site/static/img/feature-contribuir.svg').default,
    to: '/docs/equipe',
    description: (
      <>
        Integrantes e papéis, políticas de branch, commit e code review adotadas
        no semestre.
      </>
    ),
  },
];

function Feature({title, Svg, description, to}: FeatureItem) {
  return (
    <div className={clsx('col col--4')}>
      <div className="text--center">
        <Svg className={styles.featureSvg} role="img" />
      </div>
      <div className="text--center padding-horiz--md">
        <Heading as="h3">
          <Link to={to}>{title}</Link>
        </Heading>
        <p>{description}</p>
      </div>
    </div>
  );
}

export default function HomepageFeatures(): ReactNode {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
