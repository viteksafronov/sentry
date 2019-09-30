from __future__ import absolute_import

# import mock

# from django.conf import settings
from django.core.urlresolvers import reverse

# from sentry import tagstore
# from sentry.tagstore import TagKeyStatus
from sentry.testutils import APITestCase, SnubaTestCase
from sentry.testutils.helpers.datetime import iso_format, before_now


class ProjectTagKeyDetailsTest(APITestCase, SnubaTestCase):
    def test_simple(self):
        project = self.create_project()

        def make_event(i):
            self.store_event(
                data={
                    "tags": {"foo": "val{}".format(i)},
                    "timestamp": iso_format(before_now(seconds=1)),
                },
                project_id=project.id,
            )

        for i in xrange(0, 16):
            make_event(i)

        self.login_as(user=self.user)

        url = reverse(
            "sentry-api-0-project-tagkey-details",
            kwargs={
                "organization_slug": project.organization.slug,
                "project_slug": project.slug,
                "key": "foo",
            },
        )

        response = self.client.get(url)

        assert response.status_code == 200
        assert response.data["uniqueValues"] == 16


# class ProjectTagKeyDeleteTest(APITestCase):
#     @mock.patch("sentry.eventstream")
#     @mock.patch("sentry.tagstore.tasks.delete_tag_key")
#     def test_simple(self, mock_delete_tag_key, mock_eventstream):
#         project = self.create_project()
#         tagkey = tagstore.create_tag_key(project_id=project.id, environment_id=None, key="foo")

#         self.login_as(user=self.user)

#         eventstream_state = object()
#         mock_eventstream.start_delete_tag = mock.Mock(return_value=eventstream_state)

#         url = reverse(
#             "sentry-api-0-project-tagkey-details",
#             kwargs={
#                 "organization_slug": project.organization.slug,
#                 "project_slug": project.slug,
#                 "key": tagkey.key,
#             },
#         )

#         response = self.client.delete(url)

#         assert response.status_code == 204

#         if settings.SENTRY_TAGSTORE.startswith("sentry.tagstore.multi"):
#             backend_count = len(settings.SENTRY_TAGSTORE_OPTIONS.get("backends", []))
#             assert mock_delete_tag_key.delay.call_count == backend_count
#         else:
#             from sentry.tagstore.models import TagKey

#             mock_delete_tag_key.delay.assert_called_once_with(object_id=tagkey.id, model=TagKey)

#         assert (
#             tagstore.get_tag_key(
#                 project.id, None, tagkey.key, status=TagKeyStatus.PENDING_DELETION  # environment_id
#             ).status
#             == TagKeyStatus.PENDING_DELETION
#         )

#         mock_eventstream.start_delete_tag.assert_called_once_with(project.id, "foo")
#         mock_eventstream.end_delete_tag.assert_called_once_with(eventstream_state)

#     @mock.patch("sentry.tagstore.tasks.delete_tag_key")
#     def test_protected(self, mock_delete_tag_key):
#         project = self.create_project()
#         tagkey = tagstore.create_tag_key(
#             project_id=project.id, environment_id=None, key="environment"
#         )

#         self.login_as(user=self.user)

#         url = reverse(
#             "sentry-api-0-project-tagkey-details",
#             kwargs={
#                 "organization_slug": project.organization.slug,
#                 "project_slug": project.slug,
#                 "key": tagkey.key,
#             },
#         )

#         response = self.client.delete(url)

#         assert response.status_code == 403
#         assert mock_delete_tag_key.delay.call_count == 0

#         assert (
#             tagstore.get_tag_key(
#                 project.id, None, tagkey.key, status=TagKeyStatus.VISIBLE  # environment_id
#             ).status
#             == TagKeyStatus.VISIBLE
#         )
