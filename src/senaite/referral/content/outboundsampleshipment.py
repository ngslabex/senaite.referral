# -*- coding: utf-8 -*-
from plone.dexterity.content import Item
from plone.supermodel import model
from senaite.referral import messageFactory as _
from senaite.referral.interfaces import IExternalLaboratory
from senaite.referral.interfaces import IInboundSampleShipment
from senaite.referral.utils import get_action_date
from zope import schema
from zope.interface import implementer
from zope.interface import invariant

from bika.lims import api


def check_reference_laboratory(thing):
    """Checks if the reference laboratory passed in is valid
    """
    obj = api.get_object(thing, default=None)
    if not IExternalLaboratory.providedBy(obj):
        raise ValueError("Type is not supported: {}".format(repr(obj)))

    if not obj.get_reference():
        # The external laboratory must be enabled as reference laboratory
        raise ValueError("The external laboratory cannot act as a "
                         "reference laboratory")

    return True


class IOutboundSampleShipmentSchema(model.Schema):
    """OutboundSampleShipment content schema
    """

    reference_laboratory = schema.Choice(
        title=_(u"label_outboundsampleshipment_reference_laboratory",
                default=u"Destination reference laboratory"),
        description=_(u"The external reference laboratory where the shipment "
                      u"has to be sent"),
        vocabulary="senaite.referral.vocabularies.referencelaboratories",
        required=True,
    )

    comments = schema.TextLine(
        title=_(u"label_outboundsampleshipment_comments",
                default=u"Comments"),
        required=False,
    )

    shipment_id = schema.TextLine(
        title=_(u"label_outboundsampleshipment_shipment_id",
                default=u"Shipment ID"),
        # Automatically set, see property
        readonly=True,
    )

    @invariant
    def validate_reference_laboratory(data):
        """Checks if the value for field referring_laboratory is valid
        """
        val = data.reference_laboratory
        if not val:
            return
        check_reference_laboratory(val)


@implementer(IInboundSampleShipment, IOutboundSampleShipmentSchema)
class OutboundSampleShipment(Item):
    """Single physical package containing one or more samples to be sent to an
    external reference laboratory
    """
    _catalogs = ["portal_catalog", ]
    exclude_from_nav = True

    @property
    def shipment_id(self):
        """The unique ID of this outbound shipment object
        """
        return api.get_id(self)

    def get_reference_laboratory(self):
        lab = self.reference_laboratory
        if not lab:
            return u""
        return lab

    def set_reference_laboratory(self, value):
        if api.is_object(value):
            value = api.get_uid(value)

        value = value.strip()
        if self.reference_laboratory == value:
            # nothing changed
            return

        if check_reference_laboratory(value):
            self.reference_laboratory = value

    def get_comments(self):
        comments = self.comments
        if not comments:
            return u""
        return comments

    def set_comments(self, value):
        value = value.strip()
        if self.comments == value:
            # nothing changed
            return
        self.comments = value

    def get_shipment_id(self):
        return self.shipment_id

    def get_created_datetime(self):
        """Returns the datetime when this shipment was created in the system
        """
        return api.get_creation_date(self)

    def get_dispatched_datetime(self):
        """Returns the datetime when this shipment was dispatched to the
        destination reference laboratory
        """
        return get_action_date(self, "dispatch", default=None)

    def get_delivered_datetime(self):
        """Returns the datetime when this shipment was delivered on the
        destination reference laboratory
        """
        return get_action_date(self, "deliver", default=None)

    def get_lost_datetime(self):
        """Returns the datetime when this shipment was labeled as lost
        """
        return get_action_date(self, "lose", default=None)

    def get_rejected_datetime(self):
        """Returns the datetime when this shipment was rejected or None
        """
        return get_action_date(self, "reject", default=None)

    def get_cancelled_datetime(self):
        """Returns the datetime when this shipment was rejected or None
        """
        return get_action_date(self, "cancel", default=None)
