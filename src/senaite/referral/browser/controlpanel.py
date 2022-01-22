# -*- coding: utf-8 -*-

from plone.app.registry.browser.controlpanel import ControlPanelFormWrapper
from plone.app.registry.browser.controlpanel import RegistryEditForm
from plone.z3cform import layout
from senaite.referral import messageFactory as _
from zope import schema
from zope.interface import Interface


class IReferralControlPanel(Interface):
    """Control panel Settings for senaite.referral
    """

    code = schema.TextLine(
        title=_(u"label_referral_code", default=u"Code"),
        description=_(
            u"Unique code of current instance's laboratory. This unique code "
            u"is used by reference laboratories to identify this laboratory as "
            u"a valid sample referrer."
        ),
        required=True,
    )


class ReferralControlPanelForm(RegistryEditForm):
    schema = IReferralControlPanel
    schema_prefix = "senaite.referral"
    label = _("Referral Settings")


ReferralControlPanelView = layout.wrap_form(ReferralControlPanelForm,
                                            ControlPanelFormWrapper)
