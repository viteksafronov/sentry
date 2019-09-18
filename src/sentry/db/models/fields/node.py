from __future__ import absolute_import, print_function

from base64 import b64encode
import collections
import logging
import six
import warnings
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete

from sentry import nodestore
from sentry.utils.cache import memoize
from sentry.utils.compat import pickle
from sentry.utils.strings import decompress, compress
from sentry.utils.canonical import CANONICAL_TYPES, CanonicalKeyDict

from .gzippeddict import GzippedDictField

__all__ = ("NodeField", "NodeData")

logger = logging.getLogger("sentry")


class NodeIntegrityFailure(Exception):
    pass


class NodeData(collections.MutableMapping):
    """
        A wrapper for nodestore data that fetches the underlying data
        from nodestore.

        Initializing with:
        data=None means, this is a node that needs to be fetched from nodestore.
        data={...} means, this is an object that should be saved to nodestore.
    """

    def __init__(self, field, id, data=None, wrapper=None):
        self.field = field
        self.id = id
        self.ref = None
        # ref version is used to discredit a previous ref
        # (this does not mean the Event is mutable, it just removes ref checking
        #  in the case of something changing on the data model)
        self.ref_version = None
        self.wrapper = wrapper
        if data is not None and self.wrapper is not None:
            data = self.wrapper(data)
        self._node_data = data

    def __getstate__(self):
        data = dict(self.__dict__)
        # downgrade this into a normal dict in case it's a shim dict.
        # This is needed as older workers might not know about newer
        # collection types.  For isntance we have events where this is a
        # CanonicalKeyDict
        data.pop("data", None)
        data["_node_data_CANONICAL"] = isinstance(data["_node_data"], CANONICAL_TYPES)
        data["_node_data"] = dict(data["_node_data"].items())
        return data

    def __setstate__(self, state):
        # If there is a legacy pickled version that used to have data as a
        # duplicate, reject it.
        state.pop("data", None)
        if state.pop("_node_data_CANONICAL", False):
            state["_node_data"] = CanonicalKeyDict(state["_node_data"])
        self.__dict__ = state

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def __delitem__(self, key):
        del self.data[key]

    def __iter__(self):
        return iter(self.data)

    def __len__(self):
        return len(self.data)

    def __repr__(self):
        cls_name = type(self).__name__
        if self._node_data:
            return "<%s: id=%s data=%r>" % (cls_name, self.id, repr(self._node_data))
        return "<%s: id=%s>" % (cls_name, self.id)

    def get_ref(self, instance):
        if not self.field or not self.field.ref_func:
            return
        return self.field.ref_func(instance)

    def copy(self):
        return self.data.copy()

    @memoize
    def data(self):
        """
        Get the current data object, fetching from nodestore if necessary.
        """

        if self._node_data is not None:
            return self._node_data

        elif self.id:
            warnings.warn("You should populate node data before accessing it.")
            self.bind_data(nodestore.get(self.id) or {})
            return self._node_data

        rv = {}
        if self.field is not None and self.field.wrapper is not None:
            rv = self.field.wrapper(rv)
        return rv

    def bind_data(self, data, ref=None):
        self.ref = data.pop("_ref", ref)
        self.ref_version = data.pop("_ref_version", None)
        if (
            self.field is not None
            and self.ref_version == self.field.ref_version
            and ref is not None
            and self.ref != ref
        ):
            raise NodeIntegrityFailure(
                "Node reference for %s is invalid: %s != %s" % (self.id, ref, self.ref)
            )
        if self.wrapper is not None:
            data = self.wrapper(data)
        self._node_data = data

    # def bind_ref(self, instance):
    #     ref = self.get_ref(instance)
    #     if ref:
    #         self.data["_ref"] = ref
    #         self.data["_ref_version"] = self.field.ref_version

    def save(self):
        """
        Write current data back to nodestore.
        """

        # We never loaded any data for reading or writing, so there
        # is nothing to save.
        if self._node_data is None:
            return

        # We can't put our wrappers into the nodestore, so we need to
        # ensure that the data is converted into a plain old dict
        to_write = self._node_data
        if isinstance(to_write, CANONICAL_TYPES):
            to_write = dict(to_write.items())

        nodestore.set(self.id, to_write)


class NodeField(GzippedDictField):
    """
    Similar to the gzippedictfield except that it stores a reference
    to an external node.
    """

    def __init__(self, *args, **kwargs):
        self.ref_func = kwargs.pop("ref_func", None)
        self.ref_version = kwargs.pop("ref_version", None)
        self.wrapper = kwargs.pop("wrapper", None)
        self.id_func = kwargs.pop("id_func", lambda: b64encode(uuid4().bytes))
        super(NodeField, self).__init__(*args, **kwargs)

    def contribute_to_class(self, cls, name):
        super(NodeField, self).contribute_to_class(cls, name)
        post_delete.connect(self.on_delete, sender=self.model, weak=False)

    def on_delete(self, instance, **kwargs):
        value = getattr(instance, self.name)
        if not value.id:
            return

        nodestore.delete(value.id)

    def to_python(self, value):
        node_id = None
        # If value is a string, we assume this is a value we've loaded from the
        # database, it should be decompressed/unpickled, and we should end up
        # with a dict.
        if value and isinstance(value, six.string_types):
            try:
                value = pickle.loads(decompress(value))
            except Exception as e:
                # TODO this is a bit dangerous as a failure to read/decode the
                # node_id will end up with this record being replaced with an
                # empty value under a new key, potentially orphaning an
                # original value in nodestore. OTOH if we can't decode the info
                # here, the node was already effectively orphaned.
                logger.exception(e)
                value = None

        if value:
            if "node_id" in value:
                node_id = value.pop("node_id")
                # If the value is now empty, that means that it only had the
                # node_id in it, which means that we should be looking to *load*
                # the event body from nodestore. If it does have other stuff in
                # it, that means we got an event body with a precomputed id in
                # it, and we want to *save* the rest of the body to nodestore.
                if value == {}:
                    value = None
        else:
            # Either we were passed a null/empty value in the constructor, or
            # we failed to decode the value from the database so we have no id
            # to load data from, and no data to save.
            value = None

        return NodeData(self, node_id, value, wrapper=self.wrapper)

    def get_prep_value(self, value):
        """
            Prepares the NodeData to be written in a Model.save() call.

            Makes sure the event body is written to nodestore and
            returns the node_id reference to be written to rowstore.
        """
        if not value and self.null:
            # save ourselves some storage
            return None

        if value.id is None:
            value.id = self.id_func()

        value.save()
        return compress(pickle.dumps({"node_id": value.id}))


if hasattr(models, "SubfieldBase"):
    NodeField = six.add_metaclass(models.SubfieldBase)(NodeField)

if "south" in settings.INSTALLED_APPS:
    from south.modelsinspector import add_introspection_rules

    add_introspection_rules([], ["^sentry\.db\.models\.fields\.node\.NodeField"])
