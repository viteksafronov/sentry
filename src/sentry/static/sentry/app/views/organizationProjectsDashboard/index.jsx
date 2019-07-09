import {Flex} from 'grid-emotion';
import {Link, browserHistory} from 'react-router';
import LazyLoad from 'react-lazyload';
import PropTypes from 'prop-types';
import React from 'react';
import styled from 'react-emotion';

// import {sortProjects} from 'app/utils';
import {t} from 'app/locale';
import Button from 'app/components/button';
// import ConfigStore from 'app/stores/configStore';
import IdBadge from 'app/components/idBadge';
import NoProjectMessage from 'app/components/noProjectMessage';
import PageHeading from 'app/components/pageHeading';
import ProjectsStatsStore from 'app/stores/projectsStatsStore';
import SentryTypes from 'app/sentryTypes';
import getRouteStringFromRoutes from 'app/utils/getRouteStringFromRoutes';
import space from 'app/styles/space';
import withApi from 'app/utils/withApi';
import withOrganization from 'app/utils/withOrganization';

// import Resources from './resources';
import TeamSection from './teamSection';

class Teams extends React.Component {
  static propTypes = {
    api: PropTypes.object.isRequired,
    orgId: PropTypes.string.isRequired,
  };

  state = {
    teams: null,
    initiallyLoaded: false,
    fetching: false,
    hasMore: null,
  };

  componentDidMount() {
    this.fetchData();
  }

  async fetchData() {
    const {api, orgId} = this.props;

    this.setState({fetching: true});

    try {
      const teams = await api.requestPromise(`/organizations/${orgId}/teams/`, {
        query: {lite: '1'},
      });

      this.setState({initiallyLoaded: true, fetching: false, teams});
    } catch (err) {
      console.error(err);
    }
  }

  render() {
    return this.props.children({
      teams: this.state.teams,
      initiallyLoaded: this.state.initiallyLoaded,
      fetching: this.state.fetching,
      hasMore: this.state.hasMore,
    });
  }
}

class Dashboard extends React.Component {
  static propTypes = {
    api: PropTypes.object.isRequired,
    routes: PropTypes.array,
    organization: SentryTypes.Organization,
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
    const {api, params, organization} = this.props;
    // const sortedProjects = sortProjects(projects);

    // const {isSuperuser} = ConfigStore.get('user');

    // const {projectsByTeam} = getProjectsByTeams(teams, sortedProjects, isSuperuser);
    // const teamSlugs = Object.keys(projectsByTeam).sort();
    const favorites = [];
    // const favorites = projects.filter(project => project.isBookmarked);
    const access = new Set(organization.access);
    const canCreateProjects = access.has('project:admin');
    // const teamsMap = new Map(teams.map(teamObj => [teamObj.slug, teamObj]));

    const hasTeamAdminAccess = access.has('team:admin');
    const projects = [];

    // if (projects.length === 1 && !projects[0].firstEvent) {
    // return <Resources org={organization} project={projects[0]} />;
    // }

    return (
      <Flex flex="1" direction="column">
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
            >
              {t('Create Project')}
            </Button>
          </ProjectsHeader>
        )}

        <Teams api={api} orgId={organization.slug}>
          {({initiallyLoaded, fetching, teams}) => {
            if (!initiallyLoaded || fetching) {
              return null;
            }

            if (teams.length === 0 && favorites.length === 0) {
              return (
                <NoProjectMessage organization={organization}>{null}</NoProjectMessage>
              );
            }

            return teams.map((team, index) => {
              const showBorder = index !== teams.length - 1;
              // const team = teamsMap.get(slug);
              return (
                <LazyLoad key={team.slug} once debounce={50} height={300} offset={300}>
                  <TeamSection
                    api={api}
                    orgId={params.orgId}
                    team={team}
                    showBorder={showBorder}
                    title={
                      hasTeamAdminAccess ? (
                        <TeamLink
                          to={`/settings/${organization.slug}/teams/${team.slug}/`}
                        >
                          <IdBadge team={team} avatarSize={22} />
                        </TeamLink>
                      ) : (
                        <IdBadge team={team} avatarSize={22} />
                      )
                    }
                    projects={[]}
                    access={access}
                  />
                </LazyLoad>
              );
            });
          }}
        </Teams>
      </Flex>
    );
  }
}

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
export default withApi(withOrganization(Dashboard));
