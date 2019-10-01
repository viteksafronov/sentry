import {Flex} from 'grid-emotion';
import {Link, browserHistory} from 'react-router';
import LazyLoad from 'react-lazyload';
import PropTypes from 'prop-types';
import React from 'react';
import styled from 'react-emotion';
import _ from 'lodash';

import {t} from 'app/locale';
import Alert from 'app/components/alert';
import Button from 'app/components/button';
import IdBadge from 'app/components/idBadge';
import NoProjectMessage from 'app/components/noProjectMessage';
import PageHeading from 'app/components/pageHeading';
import ProjectsStatsStore from 'app/stores/projectsStatsStore';
import SentryTypes from 'app/sentryTypes';
import getRouteStringFromRoutes from 'app/utils/getRouteStringFromRoutes';
import space from 'app/styles/space';
import {sortProjects} from 'app/utils';
import LoadingIndicator from 'app/components/loadingIndicator';
import withApi from 'app/utils/withApi';
import withOrganization from 'app/utils/withOrganization';
import withTeamsForUser from 'app/utils/withTeamsForUser';

import Resources from './resources';
import TeamSection from './teamSection';

class Dashboard extends React.Component {
  static propTypes = {
    routes: PropTypes.array,
    teams: PropTypes.array,
    organization: SentryTypes.Organization,
    loadingTeams: PropTypes.bool,
    error: PropTypes.instanceOf(Error),
  };

  componentDidMount() {
    const {organization, routes} = this.props;
    const isOldRoute = getRouteStringFromRoutes(routes) === '/:orgId/';

    if (isOldRoute) {
      browserHistory.replace(`/organizations/${organization.slug}/`);
    }
  }
  componentWillUnmount() {
    ProjectsStatsStore.reset();
  }

  render() {
    const {teams, params, organization, loadingTeams, error} = this.props;

    if (loadingTeams) {
      return <LoadingIndicator />;
    }

    if (error) {
      return (
        <Alert type="error">{t('An error occurred while fetching your projects')}</Alert>
      );
    }

    const projectsByTeam = Object.fromEntries(
      teams.map(teamObj => [teamObj.slug, sortProjects(teamObj.projects)])
    );
    const projects = _.uniq(_.flatten(teams.map(teamObj => teamObj.projects)), 'id');
    const teamSlugs = Object.keys(projectsByTeam).sort();
    const favorites = projects.filter(project => project.isBookmarked);

    const access = new Set(organization.access);
    const canCreateProjects = access.has('project:admin');
    const teamsMap = new Map(teams.map(teamObj => [teamObj.slug, teamObj]));
    const hasTeamAdminAccess = access.has('team:admin');

    const showEmptyMessage = projects.length === 0 && favorites.length === 0;
    const showResources = projects.length === 1 && !projects[0].firstEvent;

    if (showEmptyMessage) {
      return (
        <NoProjectMessage organization={organization} projects={projects} detailed={0}>
          {null}
        </NoProjectMessage>
      );
    }

    return (
      <React.Fragment>
        {projects.length > 0 && (
          <ProjectsHeader>
            <PageHeading>Projects</PageHeading>
            <Button
              size="small"
              disabled={!canCreateProjects}
              title={
                !canCreateProjects
                  ? t('You do not have permission to create projects')
                  : undefined
              }
              to={`/organizations/${organization.slug}/projects/new/`}
              icon="icon-circle-add"
              data-test-id="create-project"
            >
              {t('Create Project')}
            </Button>
          </ProjectsHeader>
        )}

        {teamSlugs.map((slug, index) => {
          const showBorder = index !== teamSlugs.length - 1;
          const team = teamsMap.get(slug);
          return (
            <LazyLoad key={slug} once debounce={50} height={300} offset={300}>
              <TeamSection
                orgId={params.orgId}
                team={team}
                showBorder={showBorder}
                title={
                  hasTeamAdminAccess ? (
                    <TeamLink to={`/settings/${organization.slug}/teams/${team.slug}/`}>
                      <IdBadge team={team} avatarSize={22} />
                    </TeamLink>
                  ) : (
                    <IdBadge team={team} avatarSize={22} />
                  )
                }
                projects={projectsByTeam[slug]}
                access={access}
              />
            </LazyLoad>
          );
        })}

        {showResources && <Resources />}
      </React.Fragment>
    );
  }
}

const OrganizationDashboard = props => {
  return (
    <Flex flex="1" direction="column">
      <Dashboard {...props} />
    </Flex>
  );
};

const TeamLink = styled(Link)`
  display: flex;
  align-items: center;
`;

const ProjectsHeader = styled('div')`
  padding: ${space(3)} ${space(4)} 0 ${space(4)};
  display: flex;
  align-items: center;
  justify-content: space-between;
`;

export {Dashboard};
export default withApi(withOrganization(withTeamsForUser(OrganizationDashboard)));
