import React from 'react';
import PropTypes from 'prop-types';
import {Flex} from 'grid-emotion';
import styled from 'react-emotion';

import SentryTypes from 'app/sentryTypes';
import space from 'app/styles/space';
import PageHeading from 'app/components/pageHeading';

import TeamMembers from './teamMembers';
import ProjectCard from './projectCard';

class TeamSection extends React.Component {
  static propTypes = {
    api: PropTypes.object,
    team: SentryTypes.Team,
    orgId: PropTypes.string,
    showBorder: PropTypes.bool,
    access: PropTypes.object,
    title: PropTypes.node,
  };

  state = {
    loading: true,
    projects: [],
  };

  componentDidMount() {
    this.fetchData();
  }

  async fetchData() {
    const {api, team, orgId} = this.props;

    this.setState({loading: true});

    try {
      const projects = await api.requestPromise(`/teams/${orgId}/${team.slug}/projects/`);

      this.setState({loading: false, projects});
    } catch (err) {
      console.error(err);
    }
  }

  render() {
    const {team, title, showBorder, orgId, access} = this.props;
    const {projects} = this.state;

    const hasTeamAccess = access.has('team:read');
    const hasProjectAccess = access.has('project:read');

    return (
      <TeamSectionWrapper data-test-id="team" showBorder={showBorder}>
        <TeamTitleBar justify="space-between" align="center">
          <TeamName>{title}</TeamName>
          {hasTeamAccess && team && <TeamMembers teamId={team.slug} orgId={orgId} />}
        </TeamTitleBar>
        <ProjectCards>
          {projects.map(project => (
            <ProjectCard
              data-test-id={project.slug}
              key={project.slug}
              project={project}
              hasProjectAccess={hasProjectAccess}
            />
          ))}
        </ProjectCards>
      </TeamSectionWrapper>
    );
  }
}

const ProjectCards = styled(Flex)`
  flex-wrap: wrap;
  padding: 0 ${space(3)} ${space(3)};
`;

const TeamSectionWrapper = styled('div')`
  border-bottom: ${p => (p.showBorder ? '1px solid ' + p.theme.borderLight : 0)};

  /* stylelint-disable no-duplicate-selectors */
  &:last-child {
    ${ProjectCards} {
      padding-bottom: 0;
    }
  }
  /* stylelint-enable */
`;

const TeamTitleBar = styled(Flex)`
  padding: ${space(3)} ${space(4)} 10px;
`;

const TeamName = styled(PageHeading)`
  font-size: 20px;
  line-height: 24px; /* We need this so that header doesn't flicker when lazy loading because avatarList height > this */
`;

export default TeamSection;
